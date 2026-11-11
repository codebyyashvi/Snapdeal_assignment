"""Mock seller data.

The monthly metrics come straight from the assignment brief. Everything marked
ASSUMPTION is mock drill-down data added so the agent can reason about *why*
the numbers moved (SKU-level stock, cancellation reasons, visibility).
"""

SELLER = {
    "seller_id": "SD-48213",
    "name": "Rajesh Sharma",
    "store": "Sharma Home Essentials",
    "category": "Home & Kitchen",
    "city": "Jaipur",
    "seller_since": "2022",
    "rating_last_month": 4.3,  # ASSUMPTION
    "rating_this_month": 4.1,  # ASSUMPTION
}

# From the brief
METRICS = {
    "sales": {"label": "Sales", "last": 200000, "this": 135000, "unit": "inr"},
    "orders": {"label": "Orders", "last": 400, "this": 270, "unit": "count"},
    "cancellation_rate": {"label": "Cancellation rate", "last": 8, "this": 14, "unit": "pct"},
    "asp": {"label": "Average selling price", "last": 500, "this": 500, "unit": "inr"},
    "oos_products": {"label": "Out-of-stock products", "last": 5, "this": 18, "unit": "count"},
}

# ASSUMPTION: 60 active SKUs; 6 of the 18 out-of-stock SKUs were top sellers last month.
TOP_SKUS_OUT_OF_STOCK = [
    {"sku": "SHE-BTL-1L", "name": "Stainless Steel Water Bottle 1L", "orders_last_month": 26, "price": 450, "days_oos": 19},
    {"sku": "SHE-BED-DBL", "name": "Cotton Double Bedsheet Set", "orders_last_month": 16, "price": 650, "days_oos": 14},
    {"sku": "SHE-LNC-3C", "name": "Insulated Lunch Box 3-Container", "orders_last_month": 13, "price": 550, "days_oos": 22},
    {"sku": "SHE-KNF-5", "name": "Kitchen Knife Set of 5", "orders_last_month": 12, "price": 480, "days_oos": 11},
    {"sku": "SHE-JAR-6", "name": "Airtight Storage Jars Set of 6", "orders_last_month": 11, "price": 520, "days_oos": 17},
    {"sku": "SHE-TWL-4", "name": "Bath Towel Pack of 4", "orders_last_month": 8, "price": 400, "days_oos": 9},
]

# ASSUMPTION: breakdown of the 38 cancellations this month (14% of 270).
CANCELLATION_REASONS = [
    {"reason": "Seller cancelled - item out of stock", "count": 21},
    {"reason": "Late dispatch / SLA breach (auto-cancelled)", "count": 9},
    {"reason": "Customer changed mind", "count": 5},
    {"reason": "Address / delivery issue", "count": 3},
]

# ASSUMPTION: search visibility signals.
VISIBILITY = {
    "search_impressions_last": 120000,
    "search_impressions_this": 82000,
    "ctr_pct_last": 2.1,
    "ctr_pct_this": 2.0,
    "avg_dispatch_hours_last": 22,
    "avg_dispatch_hours_this": 41,
}

# ASSUMPTION: price benchmark vs the lowest comparable listing on the platform.
PRICE_BENCHMARK = [
    {"name": "Non-stick Tawa 28cm", "our_price": 549, "lowest_competitor": 499},
    {"name": "Steel Dinner Set 24pc", "our_price": 1299, "lowest_competitor": 1149},
    {"name": "Glass Water Jug 1.5L", "our_price": 399, "lowest_competitor": 369},
]

# ASSUMPTION: platform levers the KAM can offer.
PLATFORM_LEVERS = [
    "Snapdeal Savings Week sale event, 20-26 November - nominations close 15 November",
    "Rs 5,000 sponsored-listing credit for sellers with active KAM action plan",
    "Low-stock alerts in Seller Zone (alert at 10 units)",
    "Self-ship to Snapdeal-fulfilled warehouse to cut dispatch time",
]


def _pct(a: float, b: float) -> float:
    return round((b - a) / a * 100, 1) if a else 0.0


def diagnose() -> dict:
    """Rule-based root-cause analysis run before the call starts.

    Sales = orders x ASP. ASP is flat, so the whole drop is volume-driven; we then
    attribute lost orders to inventory, cancellations and visibility.
    """
    m = METRICS
    sales_drop = m["sales"]["last"] - m["sales"]["this"]
    lost_orders = m["orders"]["last"] - m["orders"]["this"]

    oos_lost_orders = sum(s["orders_last_month"] for s in TOP_SKUS_OUT_OF_STOCK)
    oos_lost_sales = sum(s["orders_last_month"] * s["price"] for s in TOP_SKUS_OUT_OF_STOCK)

    cancelled_this = round(m["orders"]["this"] * m["cancellation_rate"]["this"] / 100)
    cancelled_at_old_rate = round(m["orders"]["this"] * m["cancellation_rate"]["last"] / 100)
    extra_cancellations = cancelled_this - cancelled_at_old_rate
    stock_cancels = next(r["count"] for r in CANCELLATION_REASONS if "out of stock" in r["reason"])
    sla_cancels = next(r["count"] for r in CANCELLATION_REASONS if "SLA" in r["reason"])

    impressions_change = _pct(VISIBILITY["search_impressions_last"], VISIBILITY["search_impressions_this"])

    issues = [
        {
            "id": "inventory",
            "title": "Best-sellers out of stock",
            "severity": "critical",
            "evidence": f"Out-of-stock SKUs rose from {m['oos_products']['last']} to {m['oos_products']['this']}; "
                        f"{len(TOP_SKUS_OUT_OF_STOCK)} of them were top sellers that drove {oos_lost_orders} orders last month.",
            "est_monthly_impact_inr": oos_lost_sales,
        },
        {
            "id": "cancellations",
            "title": "Cancellation spike",
            "severity": "high",
            "evidence": f"Cancellation rate up from {m['cancellation_rate']['last']}% to {m['cancellation_rate']['this']}% "
                        f"({cancelled_this} orders). {stock_cancels} were stock-outs, {sla_cancels} were late-dispatch auto-cancels; "
                        f"average dispatch time went from {VISIBILITY['avg_dispatch_hours_last']}h to {VISIBILITY['avg_dispatch_hours_this']}h.",
            "est_monthly_impact_inr": cancelled_this * m["asp"]["this"],
        },
        {
            "id": "visibility",
            "title": "Lower search visibility",
            "severity": "medium",
            "evidence": f"Search impressions down {abs(impressions_change)}% and rating slipped "
                        f"{SELLER['rating_last_month']} to {SELLER['rating_this_month']}, a knock-on effect of stock-outs and cancellations. CTR is stable.",
            "est_monthly_impact_inr": max(sales_drop - oos_lost_sales, 0),
        },
        {
            "id": "pricing",
            "title": "Pricing is not the main cause",
            "severity": "low",
            "evidence": f"Average selling price is flat at Rs {m['asp']['this']}. Only {len(PRICE_BENCHMARK)} SKUs are priced "
                        f"8-13% above the lowest competitor.",
            "est_monthly_impact_inr": 0,
        },
    ]

    return {
        "headline": f"Sales down {abs(_pct(m['sales']['last'], m['sales']['this']))}% (Rs {sales_drop:,}) "
                    f"driven entirely by {lost_orders} fewer orders; price is unchanged.",
        "sales_drop_inr": sales_drop,
        "lost_orders": lost_orders,
        "extra_cancellations_vs_last_rate": extra_cancellations,
        "issues": issues,
    }


def briefing() -> str:
    """Compact plain-text fact sheet for the LLM prompt (keeps input tokens low)."""
    s, m, v, d = SELLER, METRICS, VISIBILITY, diagnose()
    skus = "; ".join(f"{x['name']} ({x['orders_last_month']} orders/mo at Rs {x['price']}, out {x['days_oos']} days)"
                     for x in TOP_SKUS_OUT_OF_STOCK)
    cancels = "; ".join(f"{r['reason']}: {r['count']}" for r in CANCELLATION_REASONS)
    prices = "; ".join(f"{p['name']} Rs {p['our_price']} vs lowest Rs {p['lowest_competitor']}" for p in PRICE_BENCHMARK)
    issues = "\n".join(f"- [{i['severity']}] {i['title']}: {i['evidence']} Est. impact Rs {i['est_monthly_impact_inr']:,}/month."
                       for i in d["issues"])
    return f"""Seller: {s['name']} of {s['store']} ({s['category']}, {s['city']}, on Snapdeal since {s['seller_since']}). Rating {s['rating_last_month']} -> {s['rating_this_month']}.
Last month -> this month: sales Rs {m['sales']['last']:,} -> Rs {m['sales']['this']:,}; orders {m['orders']['last']} -> {m['orders']['this']}; cancellation rate {m['cancellation_rate']['last']}% -> {m['cancellation_rate']['this']}%; average selling price Rs {m['asp']['last']} -> Rs {m['asp']['this']}; out-of-stock products {m['oos_products']['last']} -> {m['oos_products']['this']} (of 60 active).
Best-sellers now out of stock: {skus}.
Cancellations this month: {cancels}.
Search impressions {v['search_impressions_last']:,} -> {v['search_impressions_this']:,}; click-through {v['ctr_pct_last']}% -> {v['ctr_pct_this']}%; avg dispatch time {v['avg_dispatch_hours_last']}h -> {v['avg_dispatch_hours_this']}h.
Price gaps vs lowest competitor: {prices}.
Levers you can offer: {'; '.join(PLATFORM_LEVERS)}.
Pre-call diagnosis: {d['headline']}
{issues}"""


def seller_context() -> dict:
    return {
        "seller": SELLER,
        "metrics": METRICS,
        "top_skus_out_of_stock": TOP_SKUS_OUT_OF_STOCK,
        "cancellation_reasons": CANCELLATION_REASONS,
        "visibility": VISIBILITY,
        "price_benchmark": PRICE_BENCHMARK,
        "platform_levers": PLATFORM_LEVERS,
        "diagnosis": diagnose(),
    }
