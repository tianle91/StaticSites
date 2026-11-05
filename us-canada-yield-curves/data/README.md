# Official history snapshot

curves.json is one reproducible snapshot of the official data used for offline
builds. Run make data to rebuild it from US Treasury, Bank of Canada, SOFR and
CORRA history. Each successful refresh replaces the dataset with the source
responses. Source corrections, missing values and removed dates are reflected
directly. A failed required source leaves the previous complete snapshot intact.
Unchanged content preserves the retrieval timestamp and file mtime.

The history object maps each country id to ISO trading dates and yield arrays,
in the order defined by tenors. Unavailable maturities are null. Each country's
trading calendar is retained independently. The top-level date and series show
the latest common complete curve and are validated against history.

overnight_history maps country → effective observation date → annual percentage
rate. US rates are SOFR from the New York Fed, and Canadian rates are CORRA from
the Bank of Canada. Their links live in overnight_sources. The builder uses only
the overnight observation matching the displayed curve date.

The coverage object records actual first/last observation dates and counts for
each country/tenor and overnight rate. The default requested history starts in
1990. Sources and individual terms have different coverage. Set --start-date
when invoking src/fetch_data.py to request a shorter replacement snapshot.

The 30Y* position uses Canada's long-term benchmark, with its approximation
explained on the page. The official history is embedded in the HTML for offline date comparison.
