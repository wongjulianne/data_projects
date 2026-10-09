# Overview
This project segments the members of an airline loyalty program by their **points-purchase activity** and **flight activity**. It then finds the members most likely to buy points who **have not been marketed to yet**.

It recreates a project I completed as an analyst at a company that sells loyalty-program solutions (such as points sales) to major airline partners. The original used confidential partner data, so this version runs on a **synthetic dataset** with the same structure (see [`generate_data.py`](generate_data.py)).

**Notebook:** [Member_Segmentation.ipynb](Member_Segmentation.ipynb)

## Business question
> Who are our most engaged members, and which of them should we target with a points-purchase campaign that has not reached them yet?

## Data
Four tables covering 24 months of activity (Jan 2024 to Dec 2025) for 40,000 members:

| Table | Grain | Key fields |
|---|---|---|
| `members.csv` | 1 row per member | tier, enrolment date, home airport, email opt-in, points balance |
| `flights.csv.gz` | 1 row per booking | booking / departure / return dates, route type, cabin class, cash fare (CAD), fare in points, points earned |
| `points_purchases.csv` | 1 row per points purchase | points bought, bonus points, amount (USD), promo flag |
| `marketing_contacts.csv.gz` | 1 row per member per campaign | campaign, send date, opened, clicked |

The generator gives each member a hidden "persona" that drives their behaviour. The persona is **not** saved, so the clustering has to find the structure from behaviour alone. Rebuild the data with `python generate_data.py`.

## Method
1. **Data quality checks:** duplicates, orphaned keys, impossible dates, award-fare consistency.
2. **Feature engineering:** one row per member: flight volume, cash spend, points earned and redeemed, award-flight share, premium-cabin and international share, booking recency, purchase count, points bought, purchase recency, balance, tier.
3. **Preprocessing:** `log1p` on skewed activity metrics, then standard scaling.
4. **K-Means clustering:** *k* chosen from the elbow plot, silhouette scores and how actionable the segments are (k = 5). PCA is used for the 2-D view.
5. **Segment ranking:** segments ranked by buyer rate and points revenue per member.
6. **Propensity model:** logistic regression trained on a **time split**. Features as of June 30, 2025 predict a purchase from July to December 2025. It is used to rank members inside the top segment.
7. **Target list:** top segment, email opt-in, and never received a points campaign, ranked by propensity.

## Results
| Segment | % of members | Buyer rate | Points revenue / member |
|---|---|---|---|
| **Engaged Points Buyers** | 11% | 100% | $4,126 |
| Frequent Premium Flyers | 7% | 19% | $99 |
| Award Redeemers | 9% | 7% | $27 |
| Light Leisure Flyers | 37% | 9% | $29 |
| Dormant | 36% | 4% | $31 |

- **Engaged Points Buyers** are 11% of members but generate **93% of points revenue**. They fly regularly, book about half their trips with points (often international or premium cabin), and top up their balances repeatedly.
- The propensity model reaches a hold-out **ROC-AUC of 0.89**. Its top decile buys at **6.5x** the average rate. Past buying and award-redemption share are the strongest drivers.
- **1,890 members** in the top segment are opted in and have **never received a points campaign**. They are split into High / Medium / Low propensity tiers in [`output/target_list.csv`](output/target_list.csv).
- *Award Redeemers* have drained their balances (average about 340 points) and are a natural second wave for "top up for your next trip" offers.

## Recommendations
- Launch a points campaign to the never-contacted top-segment list, starting with the High propensity tier.
- Keep a randomized holdout within each tier. Many of these members already buy without being emailed, so the campaign should be judged on incremental purchases.
- Lead with redemption messaging. Test Award Redeemers as the next audience.

## Repo contents
```
generate_data.py            synthetic data generator (seeded, reproducible)
Member_Segmentation.ipynb   full analysis
data/                       generated input tables
output/target_list.csv      final campaign target list
output/member_segments.csv  segment + propensity score for every member
```

## Run it
```bash
pip install -r requirements.txt
python generate_data.py          # optional: the notebook regenerates data if missing
jupyter notebook Member_Segmentation.ipynb
```
