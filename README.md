# bankcap

`bankcap` is the Project 5 workspace for the TDC thesis extension:
bank balance-sheet capacity, Treasury absorption, SLR/duration constraints, and
bank-group mechanism evidence.

The first build should stay narrow. Start with Federal Reserve H.8 bank groups
before moving to Call Reports or FR Y-9C.

## Research Question

Which banks can absorb Treasury debt, and do their deposits, loans, funding, and
liquidity buffers respond differently when Treasury financing is bill-heavy,
coupon-heavy, or concentrated in TGA rebuild/QT episodes?

## First Milestone

Build an H.8 bank-group screen:

- large domestically chartered banks;
- small domestically chartered banks;
- foreign-related institutions;
- outcomes: securities, deposits, loans, cash assets, and ratios to deposits or
  assets;
- treatments/context: bill share, WAM, gross issuance, liquidity-weighted
  Treasury supply, TGA changes, high-rate/QT regimes, and large rebuild
  episodes.

The first deliverable is a go/no-go report on whether heavier Call Report or
FR Y-9C data engineering is worth doing.

## Reuse First

Do not duplicate upstream work at the start.

- Use `buycurve` for issuance composition, bill share, auction maturity panels,
  and H.8 context.
- Use `tdcladder` for WAM, bill share, liquidity-weighted Treasury supply, and
  episode-design surfaces.
- Use `liqsub` for H.8/H.4.1/OFR plumbing panels and evidence-gate context.
- Use `tdcest`/`tdcpass` only for TDC anchors and pass-through comparison if the
  bank-group screen needs them.

## Claim Boundary

H.8 bank-group evidence is mechanism context, not bank-level identification.
Bank-level claims require Call Report or FR Y-9C identifier, merger, MDRM-code,
pre-trend, and fixed-effect discipline. Public aggregates may mix Treasury and
agency securities; label the measure honestly.
