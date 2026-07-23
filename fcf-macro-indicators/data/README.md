# data/

`series.csv` is the committed quarterly grid the build renders from: columns
`m2`, `sp500`, `dgs3mo`, `dgs2`, `dgs10`, `dgs30`, and one `fcf_<TICKER>` per
basket member, indexed by calendar-quarter-end.

`fcf_source.txt` (when present) records where the committed FCF numbers came
from, as `label|url`, so the chart's "Data sources" footer attributes them
accurately. `generated_at.txt` records the pull date.

Refresh from upstream on a networked machine:

```sh
SEC_USER_AGENT="fcf-macro-indicators you@example.com" make data
make
```

`make data` regenerates `series.csv` from the sources listed in the project
README's "Data sources" section (SEC EDGAR for FCF, FRED for M2 and yields,
Yahoo Finance for the S&P 500).
