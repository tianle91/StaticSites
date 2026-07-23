# data/

`series.csv` is the committed quarterly grid the build renders from: columns
`m2`, `sp500`, `dgs3mo`, `dgs2`, `dgs10`, `dgs30`, and one `fcf_<TICKER>` per
basket member, indexed by calendar-quarter-end.

## ⚠️ The committed series.csv is SAMPLE DATA

`SAMPLE_DATA.txt` is present, which means `series.csv` holds **illustrative
placeholder values, not a real upstream pull** — it was generated in a build
environment that could not reach FRED or Yahoo Finance. Every chart rendered
from it is watermarked "SAMPLE DATA".

Replace it with real data from a networked machine:

```sh
make data      # writes a real series.csv from FRED + Yahoo and removes SAMPLE_DATA.txt
make           # re-render; the watermark disappears once the sentinel is gone
```

`make data` regenerates `series.csv` from the sources listed in the project
README's "Data sources" section.
