"""
Generate a synthetic airline-loyalty dataset for the member segmentation project.

The real project used confidential partner data, so this script simulates data with
the same shape: a member table, flight transactions, points purchases, and a
marketing contact history. Each member is assigned a hidden "persona" that drives
their behaviour; the persona is NOT written to the output files, so the clustering
has to rediscover the structure on its own.

Usage:
    python generate_data.py            # writes CSVs to ./data
    python generate_data.py --n 50000  # change the number of members
"""
import argparse
from pathlib import Path

import numpy as np
import pandas as pd

SNAPSHOT_DATE = pd.Timestamp("2025-12-31")
WINDOW_START = pd.Timestamp("2024-01-01")  # 24 months of activity

HUBS = ["YYZ", "YUL", "YVR", "YYC"]
DOMESTIC = ["YYZ", "YUL", "YVR", "YYC", "YOW", "YHZ", "YEG", "YWG", "YQB", "YYJ"]
TRANSBORDER = ["LAX", "JFK", "SFO", "MCO", "LAS", "ORD", "MIA", "BOS", "SEA", "FLL"]
INTERNATIONAL = ["LHR", "CDG", "FRA", "NRT", "HKG", "FCO", "CUN", "PVR", "SYD", "DEL"]
TIERS = ["Base", "Silver", "Gold", "Platinum", "Elite"]

# Hidden personas and the parameters that drive their behaviour.
#   share          - fraction of the member base
#   flights        - mean flights over 24 months (Poisson)
#   intl / trans   - probability a flight is international / transborder
#   cabin          - probabilities for Economy, Premium Economy, Business
#   award          - probability a flight is booked with points (an award ticket)
#   buy_rate       - mean points purchases over 24 months (Poisson)
#   buy_size       - mean points per purchase
#   tier_p         - probabilities for each status tier
#   email_contact  - probability the member has already been in a points campaign
PERSONAS = {
    "road_warrior": dict(share=0.08, flights=26, intl=0.20, trans=0.35,
                         cabin=[0.45, 0.20, 0.35], award=0.08, buy_rate=0.25,
                         buy_size=15000, tier_p=[0.05, 0.15, 0.30, 0.30, 0.20],
                         email_contact=0.55),
    "points_enthusiast": dict(share=0.10, flights=9, intl=0.40, trans=0.35,
                              cabin=[0.60, 0.20, 0.20], award=0.55, buy_rate=3.2,
                              buy_size=30000, tier_p=[0.25, 0.35, 0.25, 0.12, 0.03],
                              email_contact=0.45),
    "leisure_saver": dict(share=0.17, flights=5, intl=0.30, trans=0.40,
                          cabin=[0.85, 0.12, 0.03], award=0.12, buy_rate=0.35,
                          buy_size=10000, tier_p=[0.70, 0.22, 0.07, 0.01, 0.00],
                          email_contact=0.35),
    "occasional": dict(share=0.35, flights=1.6, intl=0.15, trans=0.30,
                       cabin=[0.95, 0.04, 0.01], award=0.05, buy_rate=0.06,
                       buy_size=6000, tier_p=[0.95, 0.05, 0.0, 0.0, 0.0],
                       email_contact=0.30),
    "dormant": dict(share=0.30, flights=0.25, intl=0.10, trans=0.25,
                    cabin=[0.97, 0.03, 0.0], award=0.03, buy_rate=0.01,
                    buy_size=5000, tier_p=[1.0, 0.0, 0.0, 0.0, 0.0],
                    email_contact=0.25),
}

CABIN_FARE_MULT = {"Economy": 1.0, "Premium Economy": 1.9, "Business": 3.8}
CABIN_EARN_MULT = {"Economy": 1.0, "Premium Economy": 1.5, "Business": 2.5}
ROUTE_BASE_FARE = {"Domestic": 380, "Transborder": 520, "International": 1150}
ROUTE_BASE_POINTS = {"Domestic": 15000, "Transborder": 22500, "International": 55000}


def random_dates(rng, n, start, end):
    span = (end - start).days
    return start + pd.to_timedelta(rng.integers(0, span + 1, n), unit="D")


def make_members(rng, n):
    names = list(PERSONAS)
    shares = np.array([PERSONAS[p]["share"] for p in names])
    persona = rng.choice(names, size=n, p=shares / shares.sum())

    tier = np.empty(n, dtype=object)
    for p in names:
        idx = persona == p
        tier[idx] = rng.choice(TIERS, size=idx.sum(), p=PERSONAS[p]["tier_p"])

    members = pd.DataFrame({
        "member_id": [f"M{i:07d}" for i in range(1, n + 1)],
        "enrol_date": random_dates(rng, n, pd.Timestamp("2008-01-01"), pd.Timestamp("2023-12-31")),
        "tier": tier,
        "age_band": rng.choice(["18-24", "25-34", "35-44", "45-54", "55-64", "65+"], n,
                               p=[0.07, 0.20, 0.23, 0.21, 0.17, 0.12]),
        "home_airport": rng.choice(HUBS + ["YOW", "YHZ", "YEG", "YWG"], n,
                                   p=[0.32, 0.18, 0.18, 0.10, 0.06, 0.05, 0.06, 0.05]),
        "email_opt_in": rng.random(n) < 0.78,
    })
    return members, persona


def make_flights(rng, members, persona):
    rows = []
    for p, cfg in PERSONAS.items():
        ids = members.loc[persona == p, "member_id"].to_numpy()
        # Gamma-Poisson mixture so counts are over-dispersed like real data
        lam = rng.gamma(shape=2.0, scale=cfg["flights"] / 2.0, size=len(ids))
        counts = rng.poisson(lam)
        member_col = np.repeat(ids, counts)
        k = len(member_col)
        if k == 0:
            continue

        u = rng.random(k)
        route = np.where(u < cfg["intl"], "International",
                         np.where(u < cfg["intl"] + cfg["trans"], "Transborder", "Domestic"))
        dest = np.where(route == "International", rng.choice(INTERNATIONAL, k),
                        np.where(route == "Transborder", rng.choice(TRANSBORDER, k),
                                 rng.choice(DOMESTIC, k)))
        cabin = rng.choice(list(CABIN_FARE_MULT), k, p=cfg["cabin"])
        is_award = rng.random(k) < cfg["award"]

        booking = random_dates(rng, k, WINDOW_START, SNAPSHOT_DATE - pd.Timedelta(days=1))
        lead = rng.gamma(2.0, 20 if p == "road_warrior" else 35, k).astype(int) + 1
        departure = booking + pd.to_timedelta(lead, unit="D")
        round_trip = rng.random(k) < 0.8
        stay = np.where(route == "International", rng.integers(5, 21, k), rng.integers(2, 10, k))
        ret = pd.Series(departure + pd.to_timedelta(stay, unit="D")).where(round_trip)

        base_fare = pd.Series(route).map(ROUTE_BASE_FARE).to_numpy()
        cab_mult = pd.Series(cabin).map(CABIN_FARE_MULT).to_numpy()
        trip_mult = np.where(round_trip, 1.8, 1.0)
        fare_cad = (base_fare * cab_mult * trip_mult * rng.lognormal(0, 0.25, k)).round(2)
        fare_points = (pd.Series(route).map(ROUTE_BASE_POINTS).to_numpy() * cab_mult * trip_mult
                       * rng.lognormal(0, 0.15, k)).round(-2)

        earn_mult = pd.Series(cabin).map(CABIN_EARN_MULT).to_numpy()
        points_earned = np.where(is_award, 0, (fare_cad * 2 * earn_mult).round()).astype(int)

        rows.append(pd.DataFrame({
            "member_id": member_col,
            "booking_date": booking,
            "departure_date": departure,
            "return_date": ret,
            "origin": members.set_index("member_id").loc[member_col, "home_airport"].to_numpy(),
            "destination": dest,
            "route_type": route,
            "cabin_class": cabin,
            "payment_type": np.where(is_award, "Points", "Cash"),
            "fare_cad": np.where(is_award, 0.0, fare_cad),
            "fare_points": np.where(is_award, fare_points, 0).astype(int),
            "taxes_fees_cad": np.where(is_award, (fare_cad * 0.18).round(2), 0.0),
            "points_earned": points_earned,
        }))

    flights = pd.concat(rows, ignore_index=True)
    flights = flights[flights["departure_date"] <= SNAPSHOT_DATE + pd.Timedelta(days=330)]
    flights = flights.sort_values(["member_id", "booking_date"]).reset_index(drop=True)
    flights.insert(0, "booking_id", [f"B{i:08d}" for i in range(1, len(flights) + 1)])
    return flights


def make_points_purchases(rng, members, persona, flights):
    # Members who redeem a lot are more likely to top up -> link purchases to award activity
    awards = flights[flights["payment_type"] == "Points"].groupby("member_id").size()
    rows = []
    for p, cfg in PERSONAS.items():
        ids = members.loc[persona == p, "member_id"]
        boost = 1 + 0.1 * np.minimum(awards.reindex(ids).fillna(0).to_numpy(), 10)
        lam = rng.gamma(1.5, cfg["buy_rate"] / 1.5, len(ids)) * boost
        counts = rng.poisson(lam)
        member_col = np.repeat(ids.to_numpy(), counts)
        k = len(member_col)
        if k == 0:
            continue
        pts = np.clip(rng.lognormal(np.log(cfg["buy_size"]), 0.6, k), 1000, 150000)
        pts = (pts / 1000).round() * 1000
        promo = rng.random(k) < 0.45  # bought during a bonus promotion
        price_per_pt = np.where(promo, 0.0225, 0.0295) * rng.uniform(0.95, 1.05, k)
        rows.append(pd.DataFrame({
            "member_id": member_col,
            "purchase_date": random_dates(rng, k, WINDOW_START, SNAPSHOT_DATE),
            "points_purchased": pts.astype(int),
            "bonus_points": np.where(promo, (pts * rng.choice([0.3, 0.5, 0.7], k)).round(), 0).astype(int),
            "amount_usd": (pts * price_per_pt).round(2),
            "promo_flag": promo,
        }))
    purchases = pd.concat(rows, ignore_index=True).sort_values(["member_id", "purchase_date"])
    purchases.insert(0, "transaction_id", [f"T{i:07d}" for i in range(1, len(purchases) + 1)])
    return purchases.reset_index(drop=True)


def make_marketing(rng, members, persona):
    campaigns = pd.DataFrame({
        "campaign_id": [f"C{i:03d}" for i in range(1, 9)],
        "campaign_name": ["Spring Bonus 30%", "Summer Top-Up", "Fall Flash Sale", "Holiday 50% Bonus",
                          "Winter Getaway Bonus", "Spring Bonus 40%", "Summer Top-Up 2", "Fall Bonus 70%"],
        "send_date": pd.to_datetime(["2024-03-12", "2024-06-18", "2024-09-24", "2024-12-03",
                                     "2025-02-11", "2025-04-15", "2025-07-08", "2025-10-21"]),
    })
    rows = []
    for p, cfg in PERSONAS.items():
        m = members.loc[persona == p]
        m = m[m["email_opt_in"]]
        contacted = m.loc[rng.random(len(m)) < cfg["email_contact"], "member_id"].to_numpy()
        n_camp = rng.integers(1, 5, len(contacted))
        member_col = np.repeat(contacted, n_camp)
        k = len(member_col)
        camp = campaigns.sample(n=k, replace=True, random_state=int(rng.integers(1e9)))
        opened = rng.random(k) < (0.45 if p == "points_enthusiast" else 0.22)
        rows.append(pd.DataFrame({
            "member_id": member_col,
            "campaign_id": camp["campaign_id"].to_numpy(),
            "send_date": camp["send_date"].to_numpy(),
            "channel": "Email",
            "opened": opened,
            "clicked": opened & (rng.random(k) < 0.25),
        }))
    contacts = (pd.concat(rows, ignore_index=True)
                .drop_duplicates(["member_id", "campaign_id"])
                .sort_values(["member_id", "send_date"]).reset_index(drop=True))
    return contacts, campaigns


def add_points_balance(rng, members, flights, purchases):
    earned = flights.groupby("member_id")["points_earned"].sum()
    redeemed = flights.groupby("member_id")["fare_points"].sum()
    bought = purchases.assign(t=purchases["points_purchased"] + purchases["bonus_points"]) \
        .groupby("member_id")["t"].sum()
    starting = rng.gamma(1.2, 9000, len(members))
    bal = (starting
           + earned.reindex(members["member_id"]).fillna(0).to_numpy()
           + bought.reindex(members["member_id"]).fillna(0).to_numpy()
           - redeemed.reindex(members["member_id"]).fillna(0).to_numpy())
    members["points_balance"] = np.clip(bal, 0, None).round().astype(int)
    return members


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--n", type=int, default=40000, help="number of members")
    parser.add_argument("--seed", type=int, default=2025)
    parser.add_argument("--out", type=Path, default=Path(__file__).parent / "data")
    args = parser.parse_args()

    rng = np.random.default_rng(args.seed)
    members, persona = make_members(rng, args.n)
    flights = make_flights(rng, members, persona)
    purchases = make_points_purchases(rng, members, persona, flights)
    contacts, campaigns = make_marketing(rng, members, persona)
    members = add_points_balance(rng, members, flights, purchases)

    args.out.mkdir(parents=True, exist_ok=True)
    members.to_csv(args.out / "members.csv", index=False)
    flights.to_csv(args.out / "flights.csv.gz", index=False, compression="gzip")
    purchases.to_csv(args.out / "points_purchases.csv", index=False)
    contacts.to_csv(args.out / "marketing_contacts.csv.gz", index=False, compression="gzip")
    campaigns.to_csv(args.out / "campaigns.csv", index=False)

    print(f"members:          {len(members):>8,}")
    print(f"flights:          {len(flights):>8,}")
    print(f"points purchases: {len(purchases):>8,}")
    print(f"marketing sends:  {len(contacts):>8,}")


if __name__ == "__main__":
    main()
