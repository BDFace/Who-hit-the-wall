# How the numbers are made

This is the exact code behind the paper's numbers, cut down to the lines that matter and explained step by step. The full script is [public/analysis/analysis.py](public/analysis/analysis.py), and every snippet below is copied from it unchanged. Line numbers refer to that file.

## Where the data came from

The script was run in the cloud computer this project runs on, not on your Mac. I downloaded the two public datasets there with `git clone`, which copies a GitHub repository onto the machine running the command:

```
git clone https://github.com/AndrewMillerOnline/marathon-results.git
git clone https://github.com/llimllib/bostonmarathon.git
```

That gave about 530 MB of CSV files on the cloud machine, which is where the script read them. The files were downloaded; they just weren't downloaded to your Mac. They're too big for the shared project folder, and nothing needed them on your Mac. To check the work yourself, download them to your Mac the same way (see the end of this file).

## Step 1: read every CSV (lines 19–33)

```python
for city, pat in [('Berlin', 'Berlin/*.csv'), ('Chicago', 'Chicago/*.csv'),
                  ('London', 'London/*.csv')]:
    for f in sorted(glob.glob(f'{D}/{pat}')):
        df = pd.read_csv(f, dtype=str, low_memory=False)
        if city == 'London' and 'division' in df:
            # 2015-2018 rows are shifted one column to the right in the source file
            sh = df.time_full.isna()
            df.loc[sh, 'time_full'] = df.loc[sh, 'time_half']
            df.loc[sh, 'time_half'] = df.loc[sh, 'division']
        df = df[[c for c in ('time_half', 'time_full', 'gender', 'year') if c in df]].copy()
        df['city'] = city
        frames.append(df)
d = pd.concat(frames, ignore_index=True)
```

- This opens each city's CSV files (one per year; London has two files covering several years) and reads every column as text.
- **The London fix.** In the London file, rows for 2015–2018 are one column out of place: the half-way time sits under `division` and the finish time under `time_half`, which leaves `time_full` empty. When `time_full` is empty, the code moves the two times back into the right columns. You can see the problem by opening `London/results-2014-2018.csv` and looking at any 2016 row.
- Only four columns are kept: half-way time, finish time, gender and year. Every file is then stacked into one big table, `d`.

## Step 2: turn "h:mm:ss" into seconds (lines 13–17)

```python
def sec(s):
    p = s.astype(str).str.strip().str.split(':', expand=True)
    if p.shape[1] < 3: return pd.Series(np.nan, index=s.index)
    return (pd.to_numeric(p[0], errors='coerce')*3600 + pd.to_numeric(p[1], errors='coerce')*60
            + pd.to_numeric(p[2], errors='coerce'))
```

For example, "01:49:31" becomes 1×3600 + 49×60 + 31 = 6,571 seconds. Anything that isn't a valid time becomes blank, and is dropped in step 4.

## Step 3: leave out broken race-years (lines 38–44)

```python
excl = (((d.city == 'London') & (d.year <= 2013)) |
        ((d.city == 'Berlin') & (d.year == 2003)) |
        ((d.city == 'Chicago') & d.year.isin([2012, 2013])))
d = d[~excl].copy()
```

These are the three exclusions explained in the paper. That leaves 42 races.

## Step 4: clean individual rows (lines 47–55)

```python
d['g'] = d.gender.str.upper().str[0].map({'M': 'M', 'F': 'W', 'W': 'W'})
d['half'] = sec(d.time_half); d['full'] = sec(d.time_full)
ok = d.g.notna() & (d.half > 0) & (d.full > d.half)
d = d[ok].copy()
d['slow'] = (d.full - d.half) / d.half - 1          # second half vs first half
ok = (d.full >= 2*3600) & (d.full < 8*3600) & (d.slow > -0.5) & (d.slow < 3)
d = d[ok].copy()
```

- **Gender.** The files write gender in different ways ("M", "Male", "F", "Female", "W"). The code keeps only the first letter, so every row ends up as M or W.
- **The key number: `slow`.** The second half takes (finish − half-way) seconds and the first half takes half-way seconds, so `slow` is how much longer the second half took, as a fraction. For the Berlin runner Martin Rusam: half-way 6,571 s and finish 14,794 s give a second half of 8,223 s. 8,223 / 6,571 − 1 = 0.251, so his second half was 25.1% slower.
- **Dropped rows:** 3,575 had a time or gender missing, or a finish time before the half-way time. Another 434 had impossible values (a finish under 2 hours or over 8 hours, or a second half more than 50% faster or 300% slower than the first).

## Step 5: who hit the wall (line 59)

```python
d['wall'] = d.slow >= 0.20
```

Each runner gets True if their second half was at least 20% slower than their first, and False otherwise.

## Step 6: the "averages" (lines 66–80)

```python
def rate_ci(s):
    k, n = int(s.sum()), int(s.size)
    lo, hi = proportion_confint(k, n, method='wilson')
    return {'k': k, 'n': n, 'p': k/n, 'lo': lo, 'hi': hi}

def two_by_two(sub):
    m, w = sub[sub.g == 'M'].wall, sub[sub.g == 'W'].wall
    tab = np.array([[m.sum(), (~m).sum()], [w.sum(), (~w).sum()]])
    chi2, p, _, _ = stats.chi2_contingency(tab, correction=False)
    pm, pw = m.mean(), w.mean()
```

The percentages in the paper aren't averages of times. They're **shares**: the number of runners who hit the wall divided by the number of runners. Python counts True as 1 and False as 0, so the average of the True/False `wall` column is exactly that share. For all men, that's 226,284 ÷ 950,329 = 23.8%.

`tab` is the 2 × 2 table (men and women, hit the wall or not) that the chi-squared test, risk ratio and odds ratio are all calculated from. The confidence interval uses the standard Wilson method from the `statsmodels` library.

The race-by-race figures run the same function once per race. The "middle of the pack" figures run it on runners with finish times from 3:30 to 4:30.

## Step 7: same race, same finishing time (lines 112–136)

Runners are put into groups by race and by 10-minute finish-time band, for example "Chicago 2010, 4:00–4:10". The Mantel–Haenszel method then combines the man-versus-woman comparisons from all 1,287 of these groups into a single odds ratio (3.83). A logistic regression does the same job a second way and gets 3.78. Both use standard functions from `statsmodels`.

## Run it yourself on your Mac

1. Open Terminal and install the tools (one time only): `pip3 install pandas scipy statsmodels`
2. Download the data: run the two `git clone` lines from the top of this file. This needs about 600 MB of free space.
3. Run the script: `python3 analysis.py marathon-results bostonmarathon/results/2014/results.csv .`

It prints every number and writes `results.json` and `race_by_race.csv`. They should match the copies in `public/analysis/`. It takes a minute or two.

## Quick checks you can do by hand

- Run the R notebook [public/analysis/wall-spot-check.Rmd](public/analysis/wall-spot-check.Rmd) in RStudio: it downloads four raw files and checks 20 headline numbers.
- In `race_by_race.csv`, check that the `men` column is higher than the `women` column in all 42 rows.
- Pick one race in a spreadsheet: count the rows where (finish − half) / half − 1 is at least 0.20, separately for men and women, and compare with `race_by_race.csv`.
