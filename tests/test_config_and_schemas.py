from pathlib import Path

import pandas as pd

from bankcap.config import validate_project_config
from bankcap.schemas import load_table_schema, validate_dataframe

ROOT = Path(__file__).resolve().parents[1]


def test_project_config_validates():
    assert validate_project_config(ROOT / "config/project.yaml") == []


def test_h8_schema_validates_minimal_panel():
    schema = load_table_schema(ROOT / "config/schemas/h8_bank_group_outcomes.yaml")
    df = pd.DataFrame(
        {
            "period": ["2023-01"],
            "date": ["2023-01-31"],
            "frequency": ["monthly"],
            "bank_group": ["large_domestic_banks"],
            "securities_usd_millions": [1.0],
            "deposits_usd_millions": [2.0],
            "loans_usd_millions": [1.1],
            "cash_assets_usd_millions": [0.3],
            "securities_deposits_ratio": [0.5],
            "cash_deposits_ratio": [0.15],
            "loans_deposits_ratio": [0.55],
        }
    )
    assert validate_dataframe(df, schema) == []
