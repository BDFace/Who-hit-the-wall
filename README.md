# Who hits the wall?

Working paper by Claude (Anthropic) and BDF, not peer reviewed: sex differences in late-race slowing among 1.4 million marathon finishers.

- `src/paper.md`: the paper text. Edit this, then run `python3 build.py` to rebuild `public/index.html` (needs pandoc).
- `src/template.html`: page layout.
- `public/`: the site Cloudflare serves, including the figures and the interactive Boston replay.
- `public/analysis/analysis.py`: reproduces every number. Run it with the two source repositories cloned locally:
  `python3 public/analysis/analysis.py marathon-results bostonmarathon/results/2014/results.csv out/`

Deploys with Cloudflare Workers Builds (static assets, `wrangler.jsonc`, no build command).
- `public/analysis/wall-spot-check.Rmd`: R notebook (tidyverse) that downloads the raw files and recomputes the headline numbers. Open in RStudio and press Knit.
