# Research design

## Goal

`bankcap` screens whether bank-group balance sheets move differently across Treasury financing regimes:
bill-heavy issuance, coupon-heavy issuance, WAM extension, TGA rebuilds, QT/QE, high-rate periods, the
2020 SLR relief window, the 2022-23 rate/duration shock, and the 2023 banking-stress window.

## First milestone: H.8 mechanism screen

The first milestone uses H.8 bank groups by week or month:

- large domestically chartered banks;
- small domestically chartered banks;
- foreign-related institutions.

Outcomes:

- securities;
- deposits;
- loans;
- cash assets;
- securities/deposits;
- cash assets/deposits;
- loans/deposits;
- level changes and ratio changes.

Treasury context:

- bill share and coupon-heavy/bill-heavy buckets;
- WAM;
- gross issuance;
- liquidity-weighted Treasury supply;
- TGA changes and large rebuild windows;
- QT/QE and high-rate regimes;
- 2020 SLR relief, 2022-23 rate/duration shock, and 2023 banking-stress windows.

## Diagnostics

The seed implements descriptive diagnostics only:

1. bank-group trend summaries;
2. bill-heavy versus coupon-heavy response tables;
3. simple correlations;
4. guarded descriptive OLS screens;
5. event-window tables around selected calendar and plumbing regimes;
6. a go/no-go report on whether bank-level data are worth the cost.

## Interpretation

A promising H.8 result means the mechanism is worth studying with better data. It does not identify
individual-bank absorption, bank-level duration constraints, or causal effects. The first report should
ask whether the pattern is stable enough to justify Call Reports or FR Y-9C, not whether the thesis is
already proven.
