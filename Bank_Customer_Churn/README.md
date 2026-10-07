# Bank Customer Churn Prediction

Data source: [Kaggle – Bank Customer Churn Prediction](https://www.kaggle.com/datasets/srisyra02/bank-customer-churn-prediction)

## Getting the data

The dataset is pulled from the Kaggle API rather than committed to the repo.

```bash
pip install -r requirements.txt
python download_data.py
```

This saves `Customer-Churn-Records.csv` to `Bank_Customer_Churn/data/` (git-ignored).

Credentials are picked up from, in order:
- `KAGGLE_API_TOKEN`: a Kaggle API token (Kaggle settings → API Tokens), sent as a Bearer token
- `KAGGLE_USERNAME` + `KAGGLE_KEY`, or `~/.kaggle/kaggle.json`: a legacy key, sent with Basic auth
- nothing: when a proxy adds the `Authorization` header itself (for example, a network secret in a Claude Code cloud environment)

Load in a notebook:

```python
import pandas as pd

df = pd.read_csv("data/Customer-Churn-Records.csv")
```
