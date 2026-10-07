# Tableau Dashboard Plan: ShopCo Profit Growth

A build plan for an interactive Tableau dashboard that shows the problem from [`Case_Study_Profit_Growth.ipynb`](Case_Study_Profit_Growth.ipynb): **revenue looks flat and stable, but that hides a collapse in new customers and profit lost to discounts that don't change behavior and to failed payments.** It's designed for five audiences: Sales, Finance, Growth, Product and Marketing.

---

## 1. Goals and design principles

**The one-sentence story the dashboard must tell:**
> "ShopCo has been flat for five years because it stopped acquiring customers, and it gives away about \$2.8M a year in discounts that don't change what customers buy."

**Principles**
1. **One shared story, then team views.** An Executive Overview everyone starts from, then one page per problem area. Pages are organized by *problem*, not by team, so teams that share a problem (e.g. Finance and Marketing on discounts) look at the same numbers.
2. **One definition per metric.** Every page uses the same calculated fields (Section 4). No page computes "profit" differently.
3. **Each page answers questions, not just shows data.** Every page has a title that states the finding ("Discounts under 23% don't move volume"), not a label ("Discount analysis").
4. **Caveats sit next to the numbers.** Known data issues are footnoted on the page where they matter (Section 8).

---

## 2. Audience and requirements

| Team | Questions they need answered | Primary pages | Key metrics |
|---|---|---|---|
| **Finance** | Are we on track for +20% profit? Where is margin leaking? What is each lever worth? | Overview, Pricing, Leakage, Scenario Planner | Merchandise profit, margin, discount \$, lost profit, lever value vs. target |
| **Sales** | Which categories, channels and markets drive revenue? Do promotions lift volume? | Overview, Pricing, Channels & Markets | Revenue, orders, AOV, units per line |
| **Growth** | Are we adding customers? Are they staying? What's a customer worth vs. what they cost? | Overview, Customer Growth, Scenario Planner | New customers, active customers, retention, profit per customer, CAC |
| **Product** | Where do customers fail to complete a purchase or have a bad experience? | Leakage | Payment failure rate, late delivery rate, rating, return reasons |
| **Marketing** | Which channels and campaigns acquire customers? Are loyalty discounts working? | Customer Growth, Pricing, Channels & Markets | New customers by channel, discount by segment, campaign orders |

---

## 3. Data model

### Source files
| File | Grain | Rows | Use |
|---|---|---|---|
| `order_items.csv` | One row per order line | 397,569 | Quantity, unit price, discount %, discount \$, product cost |
| `ecommerce_sales_customer_analytics_150k.csv` | One row per order | 138,116 | Date, status, payment, channel, campaign, segment, delivery, rating |
| `product_catalog.csv` | One row per product | 1,175 | Category, subcategory, brand |
| `customer_master.csv` | One row per customer | 25,000 | Acquisition cost (CAC), age, country |

### Recommended setup
Use Tableau **relationships** (the "noodles"), not joins, because the tables have different grains. Joining orders to lines would duplicate order-level fields like rating and shipping cost.

```
order_items ──(order_id)── orders ──(customer_id)── customer_master
     │
 (product_id)
     │
product_catalog
```

### Pre-built extract (recommended)
Two things are much easier to prepare in Python than in Tableau. Export them as extra CSVs and relate them on `customer_id`:
1. **`customer_year.csv`**: one row per customer per year they were active, with `cohort_year` (year of first order) and `active_prior_year` (true/false). Drives the cohort and retention views.
2. **`order_items_enriched.csv`** (optional): lines with `revenue`, `merch_profit` and `discount_band` precomputed. Speeds up the workbook and guarantees the numbers match the notebook.

---

## 4. Calculated fields

Create these once, in a folder called **"Core metrics"**, and use them everywhere.

### Money
| Field | Formula |
|---|---|
| Revenue | `[Gross Sales] - [Discount Amount]` |
| Merch Profit | `[Revenue] - [Product Cost]` |
| Merch Margin | `SUM([Merch Profit]) / SUM([Revenue])` |
| Discount Rate | `SUM([Discount Amount]) / SUM([Gross Sales])` |
| AOV | `SUM([Revenue]) / COUNTD([Order Id])` |

> Don't use the dataset's own `profit` column. It doesn't match revenue minus cost on any line.

### Discounts
| Field | Formula |
|---|---|
| Discount Band | `IF [Discount Percentage] = 0 THEN "0%" ELSEIF [Discount Percentage] < 0.23 THEN "1–22% · no lift" ELSEIF [Discount Percentage] < 0.27 THEN "23–26% · threshold" ELSEIF [Discount Percentage] <= 0.30 THEN "27–30% · sweet spot" ELSE "30%+ · over-discount" END` |
| Discount Bin (2 pt) | Create a bin on `[Discount Percentage]` with size 0.02 |
| Units per Line | `AVG([Quantity])` |
| No-Lift Discount \$ | `SUM(IF [Discount Percentage] > 0 AND [Discount Percentage] < 0.23 THEN [Discount Amount] END)` |

### Customers
| Field | Formula |
|---|---|
| First Order Date | `{ FIXED [Customer Id] : MIN([Order Date]) }` |
| Cohort Year | `YEAR([First Order Date])` |
| New Customers | `COUNTD(IF YEAR([Order Date]) = [Cohort Year] THEN [Customer Id] END)` |
| Active Customers | `COUNTD([Customer Id])` |
| Profit per Active Customer | `SUM([Merch Profit]) / COUNTD([Customer Id])` |
| Retention (from `customer_year`) | `SUM(INT([Active Prior Year])) / LOOKUP(COUNTD([Customer Id]), -1)` *(table calculation along Year)* |
| Avg CAC | `AVG([Customer Acquisition Cost])` |

### Leakage and experience
| Field | Formula |
|---|---|
| Payment Failure Rate | `COUNTD(IF [Order Status] = "Cancelled" THEN [Order Id] END) / COUNTD([Order Id])` |
| Return Rate | `COUNTD(IF [Order Status] = "Returned" THEN [Order Id] END) / COUNTD([Order Id])` |
| Lost Profit · Cancelled | `SUM(IF [Order Status] = "Cancelled" THEN [Merch Profit] END)` |
| Lost Profit · Returned | `SUM(IF [Order Status] = "Returned" THEN [Merch Profit] END)` |
| Late Delivery Rate | `COUNTD(IF [Delivery Status] = "Delayed" THEN [Order Id] END) / COUNTD(IF [Delivery Status] IN ("Early","On Time","Delayed") THEN [Order Id] END)` |

### Scenario planner (parameters + fields)
| Parameter | Type | Default | Range |
|---|---|---|---|
| `p_Discount Floor` | Float | 0.23 | 0–0.30, step 0.01 |
| `p_Discount Cap` | Float | 0.30 | 0.25–0.60, step 0.01 |
| `p_Payment Recovery %` | Float | 0.30 | 0–0.60 |
| `p_Return Reduction %` | Float | 0.20 | 0–0.50 |
| `p_New Customers per Year` | Integer | 1,000 | 0–5,000 |
| `p_Confidence · Pricing` / `· Acquisition` / `· Leakage` | Float | 0.5 / 0.5 / 0.7 | 0–1 |

| Field | Formula |
|---|---|
| Scenario Discount | `IF [Discount Percentage] < [p_Discount Floor] THEN 0 ELSEIF [Discount Percentage] > [p_Discount Cap] THEN [p_Discount Cap] ELSE [Discount Percentage] END` |
| Scenario Qty | `IF [Discount Percentage] >= 0.27 AND [Scenario Discount] < 0.23 THEN [Quantity] * 1.88 / 3.31 ELSEIF [Discount Percentage] < 0.23 AND [Scenario Discount] >= 0.27 THEN [Quantity] * 3.31 / 1.88 ELSE [Quantity] END` |
| Scenario Profit | `[Scenario Qty] * [Unit Price] * (1 - [Scenario Discount]) - [Scenario Qty] * [Product Cost] / [Quantity]` |
| Pricing Lever (per yr) | `(SUM([Scenario Profit]) - SUM([Merch Profit])) / 5` |
| Payment Lever (per yr) | `[Lost Profit · Cancelled] / 5 * [p_Payment Recovery %]` |
| Returns Lever (per yr) | `[Lost Profit · Returned] / 5 * [p_Return Reduction %]` |
| Acquisition Lever (yr 3) | `[p_New Customers per Year] * (1 + 0.67 + 0.67^2) * [Profit per Active Customer]` |

The 1.88 and 3.31 are the average units per line below and above the discount threshold, from the notebook.

---

## 5. Dashboard pages

Fixed size **1366 × 768**, so it fits a laptop screen and Tableau Public's default embed. Every page has the same frame:

```
┌───────────────────────────────────────────────────────────────┐
│ Page title = the finding                    [nav buttons ▸]   │
│ Filters: Year · Category · Segment · Country · Sales Channel  │
├───────────────────────────────────────────────────────────────┤
│                                                               │
│                         Charts                                │
│                                                               │
├───────────────────────────────────────────────────────────────┤
│ Footnotes: definitions and data caveats                       │
└───────────────────────────────────────────────────────────────┘
```

### Page 0 · Executive Overview *(all teams)*
**Title:** "Flat for five years: the customer pipeline has dried up"

| Sheet | Chart type | What it shows |
|---|---|---|
| KPI tiles ×5 | Big number + small trend line | Revenue (\$33.8M), Merch Profit (\$12.8M), Margin (37.8%), Active Customers (16.7k), **New Customers (204, −96% vs 2022)** |
| Revenue & profit trend | Two small line charts, stacked, shared X axis | Both flat 2021–2025. *Two charts, not a dual-axis chart.* |
| New customers by year | Bar chart, 2022–2025 | The reveal: 5,631 → 204 |
| Opportunity vs. target | Waterfall (Gantt bars) | The four levers adding up to \$3.1M against the \$2.6M target, linked to Page 5 |

Clicking a KPI tile goes to the page that explains it.

### Page 1 · Pricing & Discounts *(Finance, Sales, Marketing)*
**Title:** "Discounts under 23% cost \$2.8M a year and don't change what customers buy"

| Sheet | Chart type | What it shows |
|---|---|---|
| Demand curve | Line: units per line by 2-pt discount bin, threshold zone shaded | Flat at 1.88 → jump at about 25% → flat at 3.31 |
| Revenue & profit per line by band | Side-by-side bars (2 measures, one \$ axis) | Profit falls with every discount band; 50–60% off loses money |
| Where the discount \$ goes | Horizontal bar: discount \$ per year by Discount Band | \$2.8M a year spent in the "no lift" band |
| Category × band heatmap | Highlight table, sequential blue | Same pattern in all 15 categories (supports the "synthetic data" caveat) |
| Discount rate by segment | Bars | Premium/VIP get 17.6% vs 13.8%, with no higher order frequency |

**Interaction:** clicking a discount band filters the heatmap and segment chart. Hovering over a point on the demand curve shows a mini chart (viz in tooltip) of units per line by category.

### Page 2 · Customer Growth *(Growth, Marketing)*
**Title:** "New customers fell 96% since 2022; we're living off the 2021 base"

| Sheet | Chart type | What it shows |
|---|---|---|
| New vs. returning active customers | Stacked bars by year (new / returning) | The active base is almost entirely pre-2023 customers |
| Cohort retention | Highlight table: cohort year × activity year, % of cohort active | About 67% year-over-year retention, the same for every cohort |
| Customer value vs. cost | Two KPI tiles + bar | Profit per active customer (\$768/yr) vs. CAC (\$42) |
| First orders by marketing channel | Bars, sorted | Where the few remaining new customers come from |
| Campaign table | Text table with bars inside the cells | Orders, revenue and profit per campaign |

**Interaction:** clicking a cohort row highlights those customers across every sheet on the page (set action).

### Page 3 · Revenue Leakage *(Finance, Product)*
**Title:** "Every cancelled order is a failed payment: \$1.0M of profit lost a year"

| Sheet | Chart type | What it shows |
|---|---|---|
| Lost profit tiles | KPI tiles | Cancelled (failed payment) \$1.04M/yr · Returned \$1.20M/yr |
| Payment failure rate | Bars by payment method and sales channel | Where checkout fails most |
| Order status flow | 100% stacked bar or Sankey-style bar | Completed / Pending / Returned / Cancelled by year |
| Return reasons | Sorted horizontal bars, colored as operational vs. customer reasons | Wrong / damaged / defective items = 37% of returns (fixable in the warehouse) |
| Late delivery | Bars by warehouse and shipping method + rating comparison | 15% late everywhere, including Same Day; late orders rated 3.2 vs 3.7 |

### Page 4 · Channels & Markets *(Sales, Marketing)*
**Title:** "Channel and market mix isn't the problem: profit per order varies less than 3%"

| Sheet | Chart type | What it shows |
|---|---|---|
| Profit per order by dimension | Dot plot with an overall-average reference line; switch between dimensions with a parameter (Sales channel / Marketing channel / Country / Shipping / Payment) | All dots sit near the average line |
| Revenue mix | Treemap or sorted bars by the chosen dimension | Where volume comes from |
| Country map | Filled map, sequential blue on revenue | Geographic spread (7 countries) |

This page exists to **close a hypothesis**. The title says so, which stops teams spending time on it.

### Page 5 · Scenario Planner *(Finance, Growth, leadership)*
**Title:** "Four levers can deliver +\$3.1M a year against a \$2.6M target"

| Element | Detail |
|---|---|
| Parameter controls (left rail) | Discount floor, discount cap, payment recovery %, return reduction %, new customers per year, confidence per lever |
| Waterfall | Each lever's risk-adjusted value adding up to the total, with the target as a dashed reference line |
| Lever table | Full potential, confidence, risk-adjusted value, time to impact, owner |
| Gap to target tile | Positive/negative, using status colors + an icon (✓ / ⚠) |

### Page 6 · About the Data *(everyone)*
Metric definitions, data sources, refresh date, and the caveats in Section 8.

---

## 6. Interactivity

| Feature | Where | How to build |
|---|---|---|
| **Global filters** | All pages except Scenario Planner | Year range, Category, Segment, Country, Sales Channel. Set each to *Apply to → All using this data source*. Put them in one horizontal container under the title. |
| **Navigation** | Every page | Navigation buttons in the header; KPI tiles on the Overview link to their detail page (go-to-sheet action) |
| **Click to filter** | Pricing, Growth, Channels | Dashboard → Actions → Filter, run on *Select* |
| **Highlight** | Pricing (discount band), Growth (cohort) | Highlight actions on the shared field |
| **Set action** | Growth: selected cohort | Create a set on Cohort Year; a set action on *Select* updates it; color sheets by "in set / not in set" |
| **Parameter action** | Channels: dimension picker; Pricing: click a band to set `p_Discount Floor` | Dashboard → Actions → Change Parameter |
| **Viz in tooltip** | Demand curve, payment failure bars | Insert a hidden sheet into the tooltip with `<Sheet name>` |
| **Drill down** | Any time axis | Year → Quarter → Month date hierarchy |
| **Reset** | Every page | A "Reset filters" button (link to the same page with default filters) |

---

## 7. Visual standards

**Colors**: by role, not by series rank:

| Role | Color | Use |
|---|---|---|
| Primary measure | `#2a78d6` blue | Default bar and line color |
| Comparison / target | `#eb6834` orange | Second measure, target lines, "you are here" markers |
| Context | `#b4b2ab` gray | Non-selected marks, prior periods |
| Sequential (heatmaps, map) | `#cde2fb` → `#0d366b` (one blue, light → dark) | Magnitude only |
| Status | green ✓ / amber ⚠ / red ✕ | **Only** for good/bad KPI states, always with an icon and label |

Add a custom palette to `My Tableau Repository/Preferences.tps`:
```xml
<?xml version='1.0'?>
<workbook>
  <preferences>
    <color-palette name="ShopCo Categorical" type="regular">
      <color>#2a78d6</color><color>#eb6834</color><color>#1baf7a</color><color>#eda100</color>
      <color>#e87ba4</color><color>#008300</color><color>#4a3aa7</color><color>#e34948</color>
    </color-palette>
    <color-palette name="ShopCo Sequential Blue" type="ordered-sequential">
      <color>#cde2fb</color><color>#86b6ef</color><color>#3987e5</color><color>#1c5cab</color><color>#0d366b</color>
    </color-palette>
  </preferences>
</workbook>
```

**Rules**
- **No dual-axis charts.** Two measures on different scales get two charts with a shared X axis.
- **Use categorical colors in the order above, never cycling.** More than 8 categories → group into "Other" or use small multiples.
- **Use a legend whenever there are 2 or more series**, and label lines directly where there are 4 or fewer.
- **Keep gridlines light and remove unnecessary borders.** Use number formats like `$#,##0.0,,"M"` for millions.
- **Write titles as findings, keep tooltips in full sentences.** For example: "<Category>: <Units per Line> units per line at <Discount Band>".

---

## 8. Data caveats to show on the dashboard

| Issue | Where it matters | How to handle it |
|---|---|---|
| Returned lines show a 0% discount (refunds likely wipe the field) | Pricing page | Exclude Returned orders from discount-response sheets; footnote it |
| 2021 is the first year of data, so every customer's first order looks "new" | Overview, Growth | Start new-customer charts at 2022; footnote it |
| The dataset's `profit` column doesn't reconcile | Everywhere | Use `Merch Profit` only; define it on the About page |
| Active base stays flat despite almost no new customers and 67% retention | Growth | Footnote: "Implies heavy reactivation of lapsed customers; definition to be confirmed" |
| Uniform behavior across every category and segment | Pricing, Channels | About page: "Data appears synthetic; patterns are directional" |

---

## 9. Build plan

| Phase | Tasks | Done when |
|---|---|---|
| **1. Data prep** (½ day) | Run `download_data.py`; build `customer_year.csv` (and optionally the enriched lines file) in Python | Files load in Tableau without errors |
| **2. Data model & fields** (½ day) | Set up relationships; create the Core metrics folder; create parameters | Validation table below matches |
| **3. Worksheets** (1–2 days) | Build each sheet in Section 5 on its own worksheet, named `P1 · Demand curve` etc. | Every sheet answers its question on its own |
| **4. Dashboards** (1 day) | Assemble pages with tiled containers; apply the standard frame | Nothing overlaps at 1366 × 768 |
| **5. Interactivity** (½–1 day) | Filters, actions, navigation, tooltips | Every action in Section 6 works; reset returns to defaults |
| **6. QA** (½ day) | Re-check validation numbers with filters cleared; test each filter on each page; check the colorblind view (Tableau's *Color Blind* palette preview) | Checklist passes |
| **7. Review & publish** (½ day) | Walk through it as each team; publish to Tableau Public; add the link and a screenshot to the README | Live link works when not signed in |

### Validation checklist
With all filters cleared, the workbook must match the notebooks:

| Check | Expected |
|---|---|
| Order lines / orders / customers | 397,569 / 138,116 / 24,911 |
| 2025 Revenue | \$33.8M |
| 2025 Merch Profit | \$12.79M |
| Merch Margin 2025 | 37.8% |
| New customers 2022 → 2025 | 5,631 → 1,858 → 583 → 204 |
| Units per line, 0–20% / 30–60% | 1.88 / 3.31 |
| Discount \$ in "no lift" band (per year) | \$2.79M (\$2.77M with Returned excluded) |
| Lost profit per year: cancelled / returned | \$1.04M / \$1.20M |
| Scenario Planner at defaults: total risk-adjusted | ≈ \$3.1M per year |

---

## 10. Presenting it

For the portfolio (or an interview), add a **Tableau Story** with five story points that walk through the case:

1. "Revenue has been flat for five years" (Overview trends)
2. "…because new customers have almost stopped" (Growth)
3. "Meanwhile, \$2.8M a year in discounts buys nothing" (Pricing)
4. "…and every cancelled order is a failed payment" (Leakage)
5. "Four levers get us to +20%" (Scenario Planner)

That turns the dashboard into a 3-minute case presentation with a clear opening question and an answer at the end.
