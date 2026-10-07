"""Build Tableau-ready CSVs for the ShopCo profit-growth dashboard.

Reads the raw Kaggle files in ./data (run download_data.py first) and writes
five tables to ./data/tableau, matching Tableau_Dashboard_Plan.md:

    order_lines.csv    one row per order line   (relate to orders on order_id, products on product_id)
    products.csv       one row per product
    orders.csv         one row per order        (relate to customers on customer_id)
    customers.csv      one row per customer
    customer_year.csv  one row per customer per active year (relate to customers on customer_id)
    lever_summary.csv  the four profit levers from the case study, at default assumptions

Metric definitions follow the notebooks: revenue = gross sales - discount,
merch_profit = revenue - product cost. The dataset's own `profit` column is dropped
because it does not reconcile.

Usage:
    python prepare_tableau_data.py
"""

from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
RAW = HERE / "data"
OUT = RAW / "tableau"
YEARS = 5

# Demand-curve plateaus from Price_Sensitivity_Analysis.ipynb (units per line below / above the threshold)
LOW_Q, HIGH_Q = 1.88, 3.31


def discount_band(pct: pd.Series) -> pd.Series:
    bands = np.select(
        [pct == 0, pct < 0.23, pct < 0.27, pct <= 0.30],
        ["0%", "1–22% · no lift", "23–26% · threshold", "27–30% · sweet spot"],
        default="30%+ · over-discount",
    )
    return pd.Series(bands, index=pct.index)


def build_order_lines(items: pd.DataFrame, products: pd.DataFrame, orders: pd.DataFrame) -> pd.DataFrame:
    # Category fields sit on the line for fast filtering; names and suppliers live in products.csv
    lines = items.merge(
        products[["product_id", "product_category", "product_subcategory", "brand"]], on="product_id", how="left"
    )
    lines.insert(0, "line_id", lines.order_id + "-" + (lines.groupby("order_id").cumcount() + 1).astype(str))
    lines["discount_pct"] = lines.discount_percentage.round(4)
    lines["discount_band"] = discount_band(lines.discount_percentage)
    lines["revenue"] = (lines.gross_sales - lines.discount_amount).round(2)
    lines["merch_profit"] = (lines.revenue - lines.product_cost).round(2)
    lines["unit_cost"] = (lines.product_cost / lines.quantity).round(4)
    status = lines.order_id.map(orders.set_index("order_id").order_status)
    # Returned lines carry a 0% discount (likely wiped by the refund), so keep them out of the demand curve
    lines["in_discount_analysis"] = status.ne("Returned")
    return lines[[
        "line_id", "order_id", "product_id", "product_category", "product_subcategory", "brand", "quantity", "unit_price", "unit_cost", "discount_pct", "discount_band", "gross_sales",
        "discount_amount", "revenue", "product_cost", "merch_profit", "tax_amount", "shipping_cost",
        "in_discount_analysis",
    ]]


def build_orders(orders: pd.DataFrame, lines: pd.DataFrame) -> pd.DataFrame:
    totals = lines.groupby("order_id").agg(
        order_lines=("line_id", "size"),
        order_units=("quantity", "sum"),
        order_gross_sales=("gross_sales", "sum"),
        order_discount=("discount_amount", "sum"),
        order_revenue=("revenue", "sum"),
        order_merch_profit=("merch_profit", "sum"),
    ).round(2)
    o = orders.join(totals, on="order_id")
    o["order_date"] = pd.to_datetime(o.order_date)
    o["order_year"] = o.order_date.dt.year
    o["order_discount_rate"] = (o.order_discount / o.order_gross_sales).round(4)
    first = o.groupby("customer_id").order_date.transform("min")
    o["is_first_order"] = o.order_date.eq(first) & ~o.duplicated(["customer_id", "order_date"])
    o["is_payment_failure"] = o.order_status.eq("Cancelled")
    o["is_returned"] = o.order_status.eq("Returned")
    o["is_late"] = o.delivery_status.eq("Delayed")
    o["is_delivered"] = o.delivery_status.isin(["Early", "On Time", "Delayed"])
    o["coupon_used"] = o.coupon_code.notna()
    keep = [
        "order_id", "order_date", "order_time", "order_year", "customer_id", "customer_segment", "customer_type",
        "customer_country", "region", "sales_channel", "marketing_channel", "campaign_name", "coupon_code",
        "coupon_used", "payment_method", "payment_status", "order_status", "shipping_method", "warehouse",
        "delivery_days", "estimated_delivery_days", "delivery_status", "return_reason", "customer_rating",
        "review_sentiment", "loyalty_points_earned", "loyalty_points_redeemed", "order_lines", "order_units",
        "order_gross_sales", "order_discount", "order_discount_rate", "order_revenue", "order_merch_profit",
        "is_first_order", "is_payment_failure", "is_returned", "is_late", "is_delivered",
    ]
    return o[keep]


def build_customers(orders: pd.DataFrame, customers: pd.DataFrame) -> pd.DataFrame:
    agg = orders.groupby("customer_id").agg(
        first_order_date=("order_date", "min"),
        last_order_date=("order_date", "max"),
        lifetime_orders=("order_id", "size"),
        lifetime_revenue=("order_revenue", "sum"),
        lifetime_merch_profit=("order_merch_profit", "sum"),
    )
    agg[["lifetime_revenue", "lifetime_merch_profit"]] = agg[["lifetime_revenue", "lifetime_merch_profit"]].round(2)
    agg["cohort_year"] = agg.first_order_date.dt.year
    c = customers.drop(columns=["customer_name", "customer_postal_code", "customer_city"]).join(agg, on="customer_id")
    c["has_ordered"] = c.lifetime_orders.notna()
    return c


def build_customer_year(orders: pd.DataFrame, customers: pd.DataFrame) -> pd.DataFrame:
    cy = orders.groupby(["customer_id", "order_year"]).agg(
        orders=("order_id", "size"),
        revenue=("order_revenue", "sum"),
        merch_profit=("order_merch_profit", "sum"),
    ).round(2).reset_index().rename(columns={"order_year": "year"})
    cy["cohort_year"] = cy.customer_id.map(customers.set_index("customer_id").cohort_year).astype(int)
    cy["years_since_first"] = cy.year - cy.cohort_year
    cy["is_new"] = cy.year.eq(cy.cohort_year)
    active = set(zip(cy.customer_id, cy.year))
    cy["active_prior_year"] = [(c, y - 1) in active for c, y in zip(cy.customer_id, cy.year)]
    return cy


def build_levers(lines: pd.DataFrame, orders: pd.DataFrame, customer_year: pd.DataFrame) -> pd.DataFrame:
    d = lines.discount_pct
    new_d = d.where(d >= 0.23, 0).clip(upper=0.30)
    qty = lines.quantity.astype(float)
    qty = qty.where(~((d >= 0.27) & (new_d < 0.23)), qty * LOW_Q / HIGH_Q)
    qty = qty.where(~((d < 0.23) & (new_d >= 0.27)), qty * HIGH_Q / LOW_Q)
    scenario_profit = (qty * lines.unit_price * (1 - new_d) - qty * lines.unit_cost).sum()
    pricing = (scenario_profit - lines.merch_profit.sum()) / YEARS

    lost = orders.groupby("order_status").order_merch_profit.sum() / YEARS
    profit_per_customer = customer_year.groupby("year").merch_profit.mean().mean()
    acquisition = 1000 * (1 + 0.67 + 0.67**2) * profit_per_customer

    levers = pd.DataFrame([
        ["Discount redesign", "Stop discounts under 23%, cap at 30%", pricing, 0.5, "3–6 months", "Pricing"],
        ["Restart acquisition", "1,000 new customers a year, 67% retention, value at year 3", acquisition, 0.5, "12–36 months", "Marketing / Growth"],
        ["Payment recovery", "Recover 30% of failed-payment orders", lost["Cancelled"] * 0.30, 0.8, "1–3 months", "Product / Payments"],
        ["Return reduction", "Cut returns by 20%", lost["Returned"] * 0.20, 0.6, "6–12 months", "Operations"],
    ], columns=["lever", "assumption", "full_potential", "confidence", "time_to_impact", "owner"])
    levers["risk_adjusted"] = levers.full_potential * levers.confidence
    levers["sort_order"] = range(1, len(levers) + 1)
    return levers.round({"full_potential": 0, "risk_adjusted": 0})


def main() -> None:
    if not (RAW / "order_items.csv").exists():
        raise SystemExit("Raw data not found. Run `python download_data.py` first.")
    OUT.mkdir(parents=True, exist_ok=True)

    items = pd.read_csv(RAW / "order_items.csv")
    products = pd.read_csv(RAW / "product_catalog.csv")
    raw_orders = pd.read_csv(RAW / "ecommerce_sales_customer_analytics_150k.csv")
    raw_customers = pd.read_csv(RAW / "customer_master.csv")

    lines = build_order_lines(items, products, raw_orders)
    orders = build_orders(raw_orders, lines)
    customers = build_customers(orders, raw_customers)
    customer_year = build_customer_year(orders, customers)
    levers = build_levers(lines, orders, customer_year)

    products_out = products.rename(columns={"unit_price": "list_price", "product_cost": "list_unit_cost"})
    products_out = products_out.drop(columns=["product_category", "product_subcategory", "brand"])

    tables = {
        "order_lines": lines, "products": products_out, "orders": orders, "customers": customers,
        "customer_year": customer_year, "lever_summary": levers,
    }
    for name, table in tables.items():
        path = OUT / f"{name}.csv"
        table.to_csv(path, index=False, date_format="%Y-%m-%d")
        print(f"{path.name:<20} {len(table):>9,} rows  {path.stat().st_size / 1e6:6.1f} MB")


if __name__ == "__main__":
    main()
