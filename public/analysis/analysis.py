"""Who hits the wall? Analysis for the working paper.
Usage: python3 analysis.py <marathon-results dir> <bostonmarathon 2014 results.csv> <out dir>
"""
import sys, glob, json, numpy as np, pandas as pd
from scipy import stats
import statsmodels.api as sm
from statsmodels.stats.contingency_tables import StratifiedTable
from statsmodels.stats.proportion import proportion_confint

D, BOS, OUT = sys.argv[1:4]
R = {}

def sec(s):
    p = s.astype(str).str.strip().str.split(':', expand=True)
    if p.shape[1] < 3: return pd.Series(np.nan, index=s.index)
    return (pd.to_numeric(p[0], errors='coerce')*3600 + pd.to_numeric(p[1], errors='coerce')*60
            + pd.to_numeric(p[2], errors='coerce'))

# ---------- 1. Load Berlin, Chicago, London ----------
frames = []
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
d['year'] = pd.to_numeric(d.year, errors='coerce').astype('Int64')
flow = {'rows in source files': len(d)}

# Race-years excluded as a whole
excl = (((d.city == 'London') & (d.year <= 2013)) |
        ((d.city == 'Berlin') & (d.year == 2003)) |
        ((d.city == 'Chicago') & d.year.isin([2012, 2013])))
flow['London 2010-2013 (gender labels unreliable)'] = int(((d.city == 'London') & (d.year <= 2013)).sum())
flow['Berlin 2003 (half-way times implausible)'] = int(((d.city == 'Berlin') & (d.year == 2003)).sum())
flow['Chicago 2012-2013 (no half-way times)'] = int(((d.city == 'Chicago') & d.year.isin([2012, 2013])).sum())
d = d[~excl].copy()
flow['rows in the 42 included races'] = len(d)

d['g'] = d.gender.str.upper().str[0].map({'M': 'M', 'F': 'W', 'W': 'W'})
d['half'] = sec(d.time_half); d['full'] = sec(d.time_full)
ok = d.g.notna() & (d.half > 0) & (d.full > d.half)
flow['dropped: missing gender or time'] = int((~ok).sum())
d = d[ok].copy()
d['slow'] = (d.full - d.half) / d.half - 1          # second half vs first half
ok = (d.full >= 2*3600) & (d.full < 8*3600) & (d.slow > -0.5) & (d.slow < 3)
flow['dropped: implausible times'] = int((~ok).sum())
d = d[ok].copy()
flow['finishers analysed'] = len(d)
R['flow'] = flow
d['race'] = d.city + ' ' + d.year.astype(str)
d['wall'] = d.slow >= 0.20
d['male'] = (d.g == 'M').astype(int)
d['finbin'] = (d.full // 600).astype(int)            # 10-minute finish-time bins
R['n_races'] = int(d.race.nunique())
R['n_by_gender'] = d.g.value_counts().to_dict()
R['share_women'] = float((d.g == 'W').mean())

def rate_ci(s):
    k, n = int(s.sum()), int(s.size)
    lo, hi = proportion_confint(k, n, method='wilson')
    return {'k': k, 'n': n, 'p': k/n, 'lo': lo, 'hi': hi}

def two_by_two(sub):
    m, w = sub[sub.g == 'M'].wall, sub[sub.g == 'W'].wall
    tab = np.array([[m.sum(), (~m).sum()], [w.sum(), (~w).sum()]])
    chi2, p, _, _ = stats.chi2_contingency(tab, correction=False)
    pm, pw = m.mean(), w.mean()
    rr = pm / pw
    orr = (tab[0,0]*tab[1,1]) / (tab[0,1]*tab[1,0])
    se = np.sqrt((1/tab).sum())
    phi = np.sqrt(chi2 / tab.sum())
    return {'men': rate_ci(m), 'women': rate_ci(w), 'diff_pts': (pm-pw)*100, 'rr': rr,
            'or': orr, 'or_lo': np.exp(np.log(orr)-1.96*se), 'or_hi': np.exp(np.log(orr)+1.96*se),
            'chi2': chi2, 'p': p, 'phi': phi}

# ---------- 2. Overall and middle of the pack ----------
R['overall'] = two_by_two(d)
mid = d[(d.full >= 3.5*3600) & (d.full < 4.5*3600)]
R['mid_330_430'] = two_by_two(mid)
R['mid_n'] = len(mid)
b410 = d[(d.full >= 4*3600) & (d.full < 4*3600+600)]
R['bin_400_410'] = {c: {'M': float(b410[(b410.city == c) & (b410.g == 'M')].wall.mean()),
                        'W': float(b410[(b410.city == c) & (b410.g == 'W')].wall.mean())}
                    for c in ['Berlin', 'Chicago', 'London']}

# ---------- 3. Race by race ----------
per = []
for race, sub in d.groupby('race', sort=False):
    t = two_by_two(sub)
    per.append({'race': race, 'city': sub.city.iat[0], 'year': int(sub.year.iat[0]), 'n': len(sub),
                'men': t['men']['p'], 'women': t['women']['p'], 'rr': t['rr'], 'p': t['p']})
per = pd.DataFrame(per).sort_values(['city', 'year'])
per.to_csv(f'{OUT}/race_by_race.csv', index=False)
R['races_men_higher'] = int((per.men > per.women).sum())
R['sign_test_p'] = stats.binomtest(R['races_men_higher'], len(per), 0.5, alternative='greater').pvalue
R['races_sig_bonferroni'] = int((per.p < 0.05/len(per)).sum())
R['rr_range'] = [float(per.rr.min()), float(per.rr.max())]
R['rr_median'] = float(per.rr.median())
R['wall_rate_range'] = {'min': per.loc[(per.men+per.women).idxmin(), 'race'],
                        'max': per.loc[(per.men+per.women).idxmax(), 'race']}
cl = per.assign(gap=per.men-per.women).sort_values('gap').iloc[0]
R['closest'] = {'race': cl.race, 'men': cl.men, 'women': cl.women}

# ---------- 4. Adjusted comparisons (same race, same finish time) ----------
# Mantel-Haenszel over race x 10-minute finish bin strata
tables = []
for _, sub in d.groupby(['race', 'finbin']):
    m, w = sub[sub.g == 'M'].wall, sub[sub.g == 'W'].wall
    if len(m) and len(w):
        tables.append(np.array([[m.sum(), (~m).sum()], [w.sum(), (~w).sum()]], dtype=float))
st = StratifiedTable(tables)
lo, hi = st.oddsratio_pooled_confint()
R['mh'] = {'or': st.oddsratio_pooled, 'lo': lo, 'hi': hi, 'strata': len(tables),
           'test_p': st.test_null_odds().pvalue, 'breslow_day_p': st.test_equal_odds().pvalue}
# Binomial GLM on aggregated counts: wall ~ male + race + finish bin
agg = d.groupby(['male', 'race', 'finbin']).wall.agg(['sum', 'count']).reset_index()
X = pd.get_dummies(agg[['race', 'finbin']].astype(str), drop_first=True).astype(float)
X.insert(0, 'male', agg.male.astype(float)); X = sm.add_constant(X)
y = np.column_stack([agg['sum'], agg['count'] - agg['sum']])
glm = sm.GLM(y, X, family=sm.families.Binomial()).fit()
b, se = glm.params['male'], glm.bse['male']
R['glm'] = {'or': float(np.exp(b)), 'lo': float(np.exp(b-1.96*se)), 'hi': float(np.exp(b+1.96*se)),
            'p': float(glm.pvalues['male']), 'cells': len(agg)}
# Adjusted rates: predict everyone as man, then as woman
Xm, Xw = X.copy(), X.copy(); Xm['male'] = 1.0; Xw['male'] = 0.0
wts = agg['count'].values
R['glm']['adj_men'] = float(np.average(glm.predict(Xm), weights=wts))
R['glm']['adj_women'] = float(np.average(glm.predict(Xw), weights=wts))

# ---------- 5. Sensitivity to the wall threshold ----------
sens = []
for th in [0.10, 0.15, 0.20, 0.25, 0.30]:
    w_all = d.slow >= th
    w_mid = mid.slow >= th
    sens.append({'threshold': th,
                 'men_all': float(w_all[d.g == 'M'].mean()), 'women_all': float(w_all[d.g == 'W'].mean()),
                 'men_mid': float(w_mid[mid.g == 'M'].mean()), 'women_mid': float(w_mid[mid.g == 'W'].mean()),
                 'races_men_higher': int((d.assign(w=w_all).groupby(['race', 'g']).w.mean().unstack()
                                         .pipe(lambda t: (t.M > t.W).sum())))})
R['sensitivity'] = sens
R['median_slow'] = {g: float(d[d.g == g].slow.median()) for g in ['M', 'W']}
R['mean_slow'] = {g: float(d[d.g == g].slow.mean()) for g in ['M', 'W']}

# ---------- 6. Boston 2014 ----------
bo = pd.read_csv(BOS)
for c in ['5k', '10k', '20k', '25k', '30k', '35k', '40k', 'official']:
    bo[c] = pd.to_numeric(bo[c], errors='coerce')
bflow = {'finishers in results': len(bo)}
bo = bo.dropna(subset=['5k', '10k', '20k', '25k', '30k', '35k', '40k', 'official'])
bflow['with every split'] = len(bo)
base = (bo['20k'] - bo['5k']) / 15
seg6 = (bo['40k'] - bo['35k']) / 5 / base
seg7 = (bo.official - bo['40k']) / 2.195 / base
t = (40 - 37.5) / (41.1 - 37.5)
bo['rel40'] = seg6 + (seg7 - seg6) * t        # same interpolation the replay uses at 40 km
ok = (base > 0) & bo.rel40.between(0.5, 4)
bo = bo[ok]; bflow['analysed'] = len(bo)
bo['g'] = bo.gender.map({'M': 'M', 'F': 'W'})
bo['wall'] = bo.rel40 >= 1.25
R['boston_flow'] = bflow
R['boston_all'] = two_by_two(bo)
R['boston_330_400'] = two_by_two(bo[bo.official.between(210, 240, inclusive='left')])

json.dump(R, open(f'{OUT}/results.json', 'w'), indent=1, default=float)
print(json.dumps(R, indent=1, default=lambda x: round(float(x), 4)))
