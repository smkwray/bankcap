# Call Report / FR Y-9C gate

Bank-level data are justified only after the H.8 go/no-go report is promising.

## Minimum evidence before bank-level ingestion

The H.8 screen should show most of the following:

1. Complete or nearly complete H.8 bank-group coverage over the intended sample.
2. Meaningful variation in bill-heavy, coupon-heavy, WAM, TGA, QT/QE, and high-rate context.
3. Group-differential patterns that are not entirely driven by one short calendar window.
4. Outcome movement in securities/deposits, cash/deposits, or loans/deposits that maps to a plausible
   bank-capacity mechanism.
5. Pre-trend or placebo diagnostics that do not immediately invalidate the mechanism.

## Required bank-level design memo

Before downloading or building bank-level panels, draft a memo covering:

- Call Report versus FR Y-9C choice;
- identifiers and merger/survivorship handling;
- MDRM code map for securities, Treasuries/agencies if available, deposits, loans, cash, capital, and
  SLR-related exposures;
- pre-period capacity measures only;
- fixed effects and pre-trend plan;
- sample restrictions and public-data limitations;
- exact claim language.

## Stop conditions

Do not proceed if H.8 only shows noisy co-movement, if Treasury context is incomplete, if securities
cannot be labeled honestly, or if the proposed bank-level claim would require variables unavailable in
public Call Reports/FR Y-9C.
