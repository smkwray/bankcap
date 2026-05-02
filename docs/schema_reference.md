# Schema reference

Schemas live in `config/schemas/`.

## H.8 bank-group outcomes

Primary key: `period`, `bank_group`.

Required columns include:

- `period`, `date`, `frequency`, `bank_group`;
- `securities_usd_millions`, `deposits_usd_millions`, `loans_usd_millions`,
  `cash_assets_usd_millions`;
- `securities_deposits_ratio`, `cash_deposits_ratio`, `loans_deposits_ratio`.

Optional but expected after build:

- level changes: `d_securities_usd_millions`, `d_deposits_usd_millions`, `d_loans_usd_millions`,
  `d_cash_assets_usd_millions`;
- ratio changes: `d_securities_deposits_ratio`, `d_cash_deposits_ratio`, `d_loans_deposits_ratio`;
- `h8_security_label`.

## Treasury context

Primary key: `period`.

Core columns:

- `bill_share`, `coupon_share`, `wam_months`, `gross_issuance_usd`,
  `liquidity_weighted_treasury_supply_usd`, `tga_change_usd_millions`;
- `qt_qe_regime`, `high_rate_regime`;
- `bill_heavy_month`, `coupon_heavy_month`;
- `slr_relief_window`, `rate_duration_shock_window`, `banking_stress_2023_window`,
  `large_tga_rebuild_window`.

## Analysis panel

Primary key: `period`, `bank_group`.

The analysis panel is the H.8 panel plus Treasury context and `is_context_complete`.

## H.8 mechanism summary

Format: JSON.

Required top-level keys:

- `package`, `recommendation`, `claim_boundary`, and `gate_checks`;
- `common_target_sample` and `bank_group_coverage`;
- `relative_stability` and `relative_cutoff_sensitivity`;
- `event_window_inventory`;
- `bank_level_ingestion`.

The summary must keep `bank_level_ingestion.status` equal to `blocked` unless a separate design memo
changes the project scope.
