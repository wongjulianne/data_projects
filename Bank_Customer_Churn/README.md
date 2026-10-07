# Bank Customer Churn Prediction

Data source: [Kaggle – Bank Customer Churn Prediction](https://www.kaggle.com/datasets/srisyra02/bank-customer-churn-prediction)

## Getting the data

The dataset is pulled from the Kaggle API rather than committed to the repo.

1. Create a Kaggle API token at <https://www.kaggle.com/settings> → **API** → **Create New Token**.
2. Provide the credentials in one of two ways:
   - **Environment variables:** `KAGGLE_USERNAME` and `KAGGLE_KEY`
   - **Config file:** save the downloaded `kaggle.json` to `~/.kaggle/kaggle.json` and run `chmod 600 ~/.kaggle/kaggle.json`
3. Install dependencies and download:

```bash
pip install -r requirements.txt
python download_data.py
```

Files land in `Bank_Customer_Churn/data/` (git-ignored).

Load in a notebook:

```python
import pandas as pd
from pathlib import Path

csv = next(Path("data").glob("*.csv"))
df = pd.read_csv(csv)
```
