# Reserve Risk Replay

A vintage-aware claims backtest that answers a simple but consequential question: how would a reserve estimate have performed using only information actually available at the time?

```sh
python replay.py --output report.json
python -m unittest -v
python make_fixture.py  # optional exact regeneration of the example ledger
```

The fixture is fictional: 15 annual cohorts, two lines of business, four development ages, late filings and revisions. The casualty tail intentionally changes so pooled historical factors can be wrong. The report compares estimates against a paid-to-date baseline and reports pooled versus segment support for each included link. It records excluded origins (missing reports, immature truth, insufficient data) rather than treating them as successes. Use `--evaluation-year` and `--minimum-support` to explore sensitivity.

## Example result

At the fictional 2022 close, 54 origin/segment cases are scoreable and 24 are excluded. Weighted absolute error is 3.0004% for prior-cohort development versus 29.6280% for the paid-to-date baseline. The developed estimate still has about $38,764 of cumulative underestimation across the scored cases. This is a diagnostic over overlapping forecast origins, not an accounting balance.

## Time model

An event's booking year tells us where it belongs. Its publication date tells us when it could be used. A movement ID has immutable cohort, line of business and booking year, while a later version can replace its amount. At a December 31 cutoff only the latest published version is used. The triangle is cumulative through consecutive observed development ages; a missing cell is not a reported zero. An observed zero can be represented with a zero movement. Amounts are signed integer cents; revisions may decrease paid totals, but negative cumulative paid is invalid.

For each historically visible origin, link ratios use only older cohorts and paired ages present in that origin snapshot. A segment is used when sufficiently supported; otherwise the test falls back to pooled eligible rows, or excludes the origin with a reason. Ratio estimates use volume weighting and exact fractions, converting to cents only at the end (ties to even). The evaluation label is paid through the declared maturity age in a separate, explicitly dated snapshot. No evaluation-date information enters origin predictors.

## Interpretation

The fixture and metrics are not a real insurer's data, an assertion of real reserve adequacy, a recommendation to book reserves, or proof of live performance. Paid-to-date is a deliberately simple baseline. The evaluation labels are assumed mature at the configured age when observed; no tail factors, inflation adjustment, calendar-year effects, claim counts or intervals are modeled. Coverage/exclusion matters as much as error. Cases can repeat a cohort across ages; they aren't independent. Use age slices to make comparison interpretable rather than presenting the blended metric as an uncertainty estimate.

Python 3.10+; standard library only.
