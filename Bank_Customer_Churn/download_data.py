"""Download the Bank Customer Churn dataset from Kaggle.

Dataset: https://www.kaggle.com/datasets/srisyra02/bank-customer-churn-prediction

Credentials are read by the Kaggle client from either:
  * environment variables KAGGLE_USERNAME and KAGGLE_KEY, or
  * ~/.kaggle/kaggle.json  ({"username": "...", "key": "..."}, chmod 600)

Create a token at https://www.kaggle.com/settings -> API -> "Create New Token".

Usage:
    python download_data.py            # downloads + unzips into ./data
    python download_data.py --force    # re-download even if files exist
"""

import argparse
import os
import sys
from pathlib import Path

DATASET = "srisyra02/bank-customer-churn-prediction"
DATA_DIR = Path(__file__).resolve().parent / "data"


def has_credentials() -> bool:
    env_ok = os.environ.get("KAGGLE_USERNAME") and os.environ.get("KAGGLE_KEY")
    config_dir = Path(os.environ.get("KAGGLE_CONFIG_DIR", Path.home() / ".kaggle"))
    return bool(env_ok) or (config_dir / "kaggle.json").is_file()


def download(force: bool = False) -> Path:
    if not has_credentials():
        sys.exit(
            "Kaggle credentials not found. Set KAGGLE_USERNAME and KAGGLE_KEY, "
            "or place kaggle.json in ~/.kaggle/ (see docstring)."
        )

    # Imported here: `import kaggle` authenticates immediately and errors without creds.
    from kaggle.api.kaggle_api_extended import KaggleApi

    api = KaggleApi()
    api.authenticate()

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    api.dataset_download_files(DATASET, path=str(DATA_DIR), unzip=True, force=force, quiet=False)

    files = sorted(p.name for p in DATA_DIR.iterdir())
    print(f"Downloaded to {DATA_DIR}: {files}")
    return DATA_DIR


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--force", action="store_true", help="re-download even if present")
    download(force=parser.parse_args().force)
