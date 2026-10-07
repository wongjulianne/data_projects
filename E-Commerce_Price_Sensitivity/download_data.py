"""Download the E-Commerce Sales & Customer Analytics dataset from Kaggle.

Dataset: https://www.kaggle.com/datasets/datascikhan/e-commerce-sales-and-customer-analytics

Authentication (first match wins):
  * KAGGLE_API_TOKEN            -> sent as "Authorization: Bearer <token>"
  * KAGGLE_USERNAME + KAGGLE_KEY, or ~/.kaggle/kaggle.json -> HTTP Basic auth
  * none of the above           -> no header sent; use this when a proxy injects
                                   the Authorization header (e.g. Claude Code
                                   cloud environment network secrets)

Usage:
    python download_data.py            # downloads + unzips into ./data
    python download_data.py --force    # re-download even if files exist
"""

import argparse
import base64
import io
import json
import os
import sys
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

DATASET = "datascikhan/e-commerce-sales-and-customer-analytics"
URL = f"https://www.kaggle.com/api/v1/datasets/download/{DATASET}"
DATA_DIR = Path(__file__).resolve().parent / "data"


def auth_header() -> dict:
    token = os.environ.get("KAGGLE_API_TOKEN")
    if token:
        return {"Authorization": f"Bearer {token}"}

    user, key = os.environ.get("KAGGLE_USERNAME"), os.environ.get("KAGGLE_KEY")
    config = Path(os.environ.get("KAGGLE_CONFIG_DIR", Path.home() / ".kaggle")) / "kaggle.json"
    if not (user and key) and config.is_file():
        creds = json.loads(config.read_text())
        user, key = creds.get("username"), creds.get("key")
    if user and key:
        encoded = base64.b64encode(f"{user}:{key}".encode()).decode()
        return {"Authorization": f"Basic {encoded}"}

    return {}


def download(force: bool = False) -> Path:
    if DATA_DIR.is_dir() and any(DATA_DIR.glob("*.csv")) and not force:
        print(f"Data already in {DATA_DIR} (use --force to re-download)")
        return DATA_DIR

    request = urllib.request.Request(URL, headers=auth_header())
    try:
        with urllib.request.urlopen(request) as response:
            payload = response.read()
    except urllib.error.HTTPError as err:
        sys.exit(f"Kaggle download failed: HTTP {err.code}. Check your Kaggle credentials.")

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        archive.extractall(DATA_DIR)

    print(f"Downloaded to {DATA_DIR}: {sorted(p.name for p in DATA_DIR.iterdir())}")
    return DATA_DIR


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--force", action="store_true", help="re-download even if present")
    download(force=parser.parse_args().force)
