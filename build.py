"""Build public/index.html from src/paper.md. Run: python3 build.py"""
import re, subprocess, pathlib, html
root = pathlib.Path(__file__).parent
md = (root / 'src/paper.md').read_text()
meta = dict(re.findall(r'^(title|author|date):\s*"?(.*?)"?\s*$', md.split('---')[1], re.M))
body_md = md.split('---', 2)[2]
body = subprocess.run(['pandoc', '-f', 'markdown+autolink_bare_uris', '-t', 'html5', '--no-highlight'],
                      input=body_md, capture_output=True, text=True, check=True).stdout

FIGS = {
 1: ('<div class="replay"><iframe src="figures/replay.html" title="Interactive race replay of the 2014 Boston Marathon" loading="lazy"></iframe></div>',
     'Interactive race replay, Boston Marathon 2014. Each dot is one finisher (random sample of 3,000 men and 3,000 women), placed by how much slower they are running than their own 5–20 km pace; red dots are at least 25% slower. Press play, or filter by finishing time.'),
 2: ('<img src="figures/fig2-every-race.png" width="1360" height="1458" alt="Scatter plot of 42 marathons, share of women who hit the wall against share of men. Every race sits above the line of equal rates.">',
     'Share of men and women hitting the wall (second half at least 20% slower than the first) in each of the 42 races. Every race lies above the diagonal of equal rates.'),
 3: ('<img src="figures/fig3-same-finish-time.png" width="1360" height="1138" alt="Line charts for Berlin, Chicago and London: share hitting the wall by finishing time. The men\'s line is above the women\'s at every time.">',
     'Share hitting the wall by 10-minute finishing-time band, men and women, for each city.'),
 4: ('<img src="figures/fig4-middle-of-pack.png" width="1360" height="1206" alt="Mirrored histogram of second-half slowing for 3:30 to 4:30 finishers, men above and women below. The tail beyond 20% is much heavier for men.">',
     'Distribution of second-half slowing among the 648,059 finishers who took 3:30 to 4:30. Men above the axis, women below; bars beyond the 20% line are coloured.'),
}
def fig(m):
    n = int(m.group(1)); inner, cap = FIGS[n]
    return f'<figure id="fig{n}" class="{"wide" if n == 1 else ""}">{inner}<figcaption><b>Figure {n}.</b> {html.escape(cap)}</figcaption></figure>'
body = re.sub(r'<p><strong>\[Figure (\d):[^\]]*\]</strong></p>', fig, body)
body = re.sub(r'<p><strong>(Table \d\.[^<]*)</strong></p>\s*<table>', r'<div class="tablewrap"><table><caption>\1</caption>', body)
body = body.replace('</table>', '</table></div>')
# Draft notice: first blockquote
body = body.replace('<blockquote>', '<aside class="draft" role="note">', 1).replace('</blockquote>', '</aside>', 1)
# Abstract box
body = re.sub(r'(<h2 id="abstract">Abstract</h2>.*?)(?=<h2)', r'<section class="abstract">\1</section>', body, flags=re.S)
tpl = (root / 'src/template.html').read_text()
out = tpl.replace('{{title}}', html.escape(meta['title'])).replace('{{author}}', html.escape(meta['author'])) \
         .replace('{{date}}', html.escape(meta['date'])).replace('{{body}}', body)
(root / 'public/index.html').write_text(out)
print('built', len(out))
