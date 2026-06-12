"""FastAPI application — RevOps Dashboard backend."""

import csv
import io
import os
from typing import Optional

from fastapi import FastAPI, Depends, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy import text
from sqlalchemy.orm import Session

from database import get_db, init_db, seed_data
from models import DealOut, PaginatedDeals, KPIsOut, ChartData, InsightRequest, InsightResponse, ExportFilter
from ai_engine import generate_insight

app = FastAPI(title="RevOps Dashboard API", version="3.0.0")

app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_credentials=True,
    allow_methods=["*"], allow_headers=["*"],
)

FRONTEND_DIR = os.path.normpath(os.path.join(os.path.dirname(__file__), ".."))

@app.on_event("startup")
def startup():
    init_db()
    db = next(get_db())
    try:
        seed_data(db)
    finally:
        db.close()

# ─── Helpers ──────────────────────────────────────────────────────────────────

def _multi(val: Optional[str]) -> list[str]:
    """Split comma-separated value into list, strip whitespace."""
    if not val:
        return []
    return [v.strip() for v in val.split(",") if v.strip()]

def _build_where(
    region=None, industry=None, date_from=None, date_to=None,
    product=None, tier=None, source=None,
) -> tuple[str, dict]:
    clauses, params, idx = [], {}, 0
    regions = _multi(region)
    sources = _multi(source)
    years = _multi(date_from)  # date_from now accepts "2024,2025" for multi-year
    if regions:
        ph = ", ".join(f":r{i}" for i in range(len(regions)))
        clauses.append(f"c.region IN ({ph})")
        for i, v in enumerate(regions): params[f"r{i}"] = v
    if industry:
        clauses.append("c.industry = :industry"); params["industry"] = industry
    if tier:
        clauses.append("c.tier = :tier"); params["tier"] = tier
    if product:
        clauses.append("p.code = :product"); params["product"] = product
    if sources:
        ph = ", ".join(f":s{i}" for i in range(len(sources)))
        clauses.append(f"s.name IN ({ph})")
        for i, v in enumerate(sources): params[f"s{i}"] = v
    if years:
        # Multi-year: "2024,2025" → strftime('%Y', deal_date) IN ('2024','2025')
        ph = ", ".join(f":y{i}" for i in range(len(years)))
        clauses.append(f"strftime('%Y', d.deal_date) IN ({ph})")
        for i, v in enumerate(years): params[f"y{i}"] = v
    elif date_to:
        # Single year backward compat: date_to="2025-12-31"
        clauses.append("d.deal_date <= :date_to"); params["date_to"] = date_to
    where = " WHERE " + " AND ".join(clauses) if clauses else ""
    return where, params

DEAL_FROM = """
    FROM deals d
    JOIN products p ON d.product_id = p.id
    JOIN companies c ON d.company_id = c.id
    JOIN marketing_sources s ON d.source_id = s.id
"""

DEAL_SELECT = """
    SELECT d.id, p.code, p.name, p.category,
           c.name, c.region, c.industry, c.tier,
           s.name, d.qty, d.discount,
           d.gross_rev, d.discount_amt, d.net_rev,
           d.total_cost, d.cac_value, d.opex_overhead,
           d.net_profit, d.deal_date
"""

def _rows_to_deals(rows):
    return [DealOut(**{
        "id": r[0], "product_code": r[1], "product_name": r[2], "product_category": r[3],
        "company_name": r[4], "region": r[5], "industry": r[6], "tier": r[7],
        "source_name": r[8], "qty": r[9], "discount": r[10],
        "gross_rev": r[11], "discount_amt": r[12], "net_rev": r[13],
        "total_cost": r[14], "cac_value": r[15], "opex_overhead": r[16],
        "net_profit": r[17], "deal_date": str(r[18]),
    }) for r in rows]

# ─── Endpoints ────────────────────────────────────────────────────────────────

@app.get("/api/deals", response_model=PaginatedDeals)
def get_deals(
    page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=200),
    region: Optional[str] = None, industry: Optional[str] = None,
    date_from: Optional[str] = None, date_to: Optional[str] = None,
    product: Optional[str] = None, tier: Optional[str] = None,
    source: Optional[str] = None, db: Session = Depends(get_db),
):
    where, params = _build_where(region, industry, date_from, date_to, product, tier, source)
    total = db.execute(text(f"SELECT COUNT(*) {DEAL_FROM}{where}"), params).scalar() or 0
    offset = (page - 1) * page_size
    dp = {**params, "limit": page_size, "offset": offset}
    rows = db.execute(text(f"{DEAL_SELECT} {DEAL_FROM}{where} ORDER BY d.deal_date DESC LIMIT :limit OFFSET :offset"), dp).fetchall()
    return PaginatedDeals(
        total=total, page=page, page_size=page_size,
        total_pages=max(1, (total + page_size - 1) // page_size),
        deals=_rows_to_deals(rows),
    )

@app.get("/api/kpis", response_model=KPIsOut)
def get_kpis(
    region: Optional[str] = None, industry: Optional[str] = None,
    date_from: Optional[str] = None, date_to: Optional[str] = None,
    product: Optional[str] = None, tier: Optional[str] = None,
    source: Optional[str] = None, db: Session = Depends(get_db),
):
    where, params = _build_where(region, industry, date_from, date_to, product, tier, source)
    sql = f"""
        SELECT ROUND(COALESCE(SUM(d.net_rev), 0), 2),
               ROUND(COALESCE(SUM(d.total_cost), 0), 2),
               ROUND(COALESCE(SUM(d.net_rev - d.total_cost - d.cac_value - d.opex_overhead), 0), 2),
               ROUND(COALESCE(SUM(d.cac_value), 0), 2),
               ROUND(COALESCE(SUM(d.opex_overhead), 0), 2),
               COUNT(*)
        {DEAL_FROM}{where}
    """
    r = db.execute(text(sql), params).one()
    rev, cost, profit, cac, opex, cnt = r[0] or 0, r[1] or 0, r[2] or 0, r[3] or 0, r[4] or 0, r[5] or 0
    return KPIsOut(
        total_revenue=rev, total_cost=cost, total_margin=rev - cost,
        total_cac=cac, total_opex=opex, net_profit=profit,
        avg_margin=round((profit / rev * 100) if rev else 0, 2), row_count=cnt,
    )

# ─── Chart endpoints ──────────────────────────────────────────────────────────

def _chart_where(source=None, region=None, date_from=None, date_to=None):
    clauses, params, idx = [], {}, 0
    regions = _multi(region)
    sources = _multi(source)
    years = _multi(date_from)  # "2024,2025" multi-year
    if regions:
        ph = ", ".join(f":r{i}" for i in range(len(regions)))
        clauses.append(f"c.region IN ({ph})")
        for i, v in enumerate(regions): params[f"r{i}"] = v
    if sources:
        ph = ", ".join(f":s{i}" for i in range(len(sources)))
        clauses.append(f"s.name IN ({ph})")
        for i, v in enumerate(sources): params[f"s{i}"] = v
    if years:
        ph = ", ".join(f":y{i}" for i in range(len(years)))
        clauses.append(f"strftime('%Y', d.deal_date) IN ({ph})")
        for i, v in enumerate(years): params[f"y{i}"] = v
    elif date_to:
        clauses.append("d.deal_date <= :date_to"); params["date_to"] = date_to
    return (" WHERE " + " AND ".join(clauses)) if clauses else "", params


@app.get("/api/charts/{chart_type}", response_model=ChartData)
def get_chart_data(
    chart_type: str,
    region: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    source: Optional[str] = None,
    db: Session = Depends(get_db),
):
    wh, wp = _chart_where(source, region, date_from, date_to)
    joins = "JOIN companies c ON d.company_id = c.id JOIN marketing_sources s ON d.source_id = s.id"

    if chart_type == "monthly-trend":
        sql = f"""
            SELECT strftime('%Y-%m', d.deal_date) AS label,
                   ROUND(SUM(d.net_rev), 2), ROUND(SUM(d.net_profit), 2)
            FROM deals d {joins} {wh}
            GROUP BY label ORDER BY label ASC
        """
        rows = db.execute(text(sql), wp).fetchall()
        return ChartData(labels=[r[0] for r in rows], series=[
            {"name": "Revenue", "data": [float(r[1]) for r in rows]},
            {"name": "Profit",  "data": [float(r[2]) for r in rows]},
        ])

    elif chart_type == "yoy-comparison":
        # Dynamic YoY: auto-detect 2 most recent years from data or filter
        yoy_wh_parts, yoy_wp = [], {}
        regions = _multi(region)
        sources = _multi(source)
        if regions:
            ph = ", ".join(f":yr{i}" for i in range(len(regions)))
            yoy_wh_parts.append(f"c.region IN ({ph})")
            for i, v in enumerate(regions): yoy_wp[f"yr{i}"] = v
        if sources:
            ph = ", ".join(f":ys{i}" for i in range(len(sources)))
            yoy_wh_parts.append(f"s.name IN ({ph})")
            for i, v in enumerate(sources): yoy_wp[f"ys{i}"] = v
        yoy_where = (" AND " + " AND ".join(yoy_wh_parts)) if yoy_wh_parts else ""

        # Find 2 most recent years with data
        yr_sql = f"SELECT DISTINCT strftime('%Y', d.deal_date) AS y FROM deals d {joins} {('WHERE 1=1 ' + yoy_where) if yoy_where else ''} ORDER BY y DESC LIMIT 2"
        yr_rows = db.execute(text(yr_sql), yoy_wp).fetchall()
        if len(yr_rows) < 2:
            # Fallback: use all available years
            yr_sql2 = f"SELECT DISTINCT strftime('%Y', d.deal_date) AS y FROM deals d {joins} ORDER BY y"
            yr_rows = db.execute(text(yr_sql2), {}).fetchall()

        year_a = yr_rows[1][0] if len(yr_rows) >= 2 else yr_rows[0][0]
        year_b = yr_rows[0][0]

        sql_a = f"""
            SELECT strftime('%m', d.deal_date) AS month_num,
                   ROUND(SUM(d.net_rev), 2), ROUND(SUM(d.net_profit), 2)
            FROM deals d {joins}
            WHERE strftime('%Y', d.deal_date) = :ya {yoy_where}
            GROUP BY month_num ORDER BY month_num
        """
        sql_b = f"""
            SELECT strftime('%m', d.deal_date) AS month_num,
                   ROUND(SUM(d.net_rev), 2), ROUND(SUM(d.net_profit), 2)
            FROM deals d {joins}
            WHERE strftime('%Y', d.deal_date) = :yb {yoy_where}
            GROUP BY month_num ORDER BY month_num
        """
        rows_a = db.execute(text(sql_a), {**yoy_wp, "ya": year_a}).fetchall()
        rows_b = db.execute(text(sql_b), {**yoy_wp, "yb": year_b}).fetchall()
        months = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec']
        rev_a = {r[0]: float(r[1]) for r in rows_a}
        prof_a = {r[0]: float(r[2]) for r in rows_a}
        rev_b = {r[0]: float(r[1]) for r in rows_b}
        prof_b = {r[0]: float(r[2]) for r in rows_b}
        return ChartData(labels=months, series=[
            {"name": f"{year_a} Revenue", "data": [rev_a.get(str(i+1).zfill(2), 0) for i in range(12)]},
            {"name": f"{year_b} Revenue", "data": [rev_b.get(str(i+1).zfill(2), 0) for i in range(12)]},
            {"name": f"{year_a} Profit",  "data": [prof_a.get(str(i+1).zfill(2), 0) for i in range(12)]},
            {"name": f"{year_b} Profit",  "data": [prof_b.get(str(i+1).zfill(2), 0) for i in range(12)]},
        ])

    elif chart_type == "regional-margin":
        sql = f"""
            SELECT c.region AS label,
                   ROUND(AVG(d.net_profit / NULLIF(d.net_rev, 0)) * 100, 2) AS margin,
                   ROUND(SUM(d.net_rev), 2)
            FROM deals d {joins} {wh}
            GROUP BY c.region ORDER BY SUM(d.net_rev) DESC
        """
        rows = db.execute(text(sql), wp).fetchall()
        return ChartData(labels=[r[0] for r in rows], series=[
            {"name": "Margin %", "data": [float(r[1]) for r in rows]},
            {"name": "Revenue",  "data": [float(r[2]) for r in rows]},
        ])

    elif chart_type == "scatter-bubble":
        sql = f"""
            SELECT s.name AS label, ROUND(AVG(s.cac), 2),
                   ROUND(SUM(d.net_rev), 2), COUNT(*)
            FROM deals d {joins} {wh}
            GROUP BY s.name ORDER BY SUM(d.net_rev) DESC
        """
        rows = db.execute(text(sql), wp).fetchall()
        points = [{"label": r[0], "x": float(r[1]), "y": float(r[2]),
                    "r": max(5, min(20, int(r[3]) // 80))} for r in rows]
        return ChartData(labels=[p["label"] for p in points], points=points)

    elif chart_type == "funnel":
        sql = f"""
            SELECT s.name AS label, COUNT(*), ROUND(SUM(d.net_rev), 2)
            FROM deals d {joins} {wh}
            GROUP BY s.name ORDER BY COUNT(*) DESC
        """
        rows = db.execute(text(sql), wp).fetchall()
        return ChartData(labels=[r[0] for r in rows], values=[int(r[1]) for r in rows])

    elif chart_type == "product-performance":
        prod_joins = joins + " JOIN products p ON d.product_id = p.id"
        sql = f"""
            SELECT p.name AS label, ROUND(SUM(d.net_rev), 2), ROUND(SUM(d.net_profit), 2)
            FROM deals d {prod_joins} {wh}
            GROUP BY p.name ORDER BY SUM(d.net_profit) DESC LIMIT 5
        """
        rows = db.execute(text(sql), wp).fetchall()
        return ChartData(labels=[r[0] for r in rows], series=[
            {"name": "Revenue", "data": [float(r[1]) for r in rows]},
            {"name": "Profit",  "data": [float(r[2]) for r in rows]},
        ])

    elif chart_type == "tier-share":
        sql = f"""
            SELECT c.tier AS label, ROUND(SUM(d.net_rev), 2), COUNT(*)
            FROM deals d {joins} {wh}
            GROUP BY c.tier ORDER BY SUM(d.net_rev) DESC
        """
        rows = db.execute(text(sql), wp).fetchall()
        return ChartData(labels=[r[0] for r in rows], series=[
            {"name": "Revenue", "data": [float(r[1]) for r in rows]},
            {"name": "Deals",   "data": [int(r[2]) for r in rows]},
        ])

    elif chart_type == "recommendations":
        # Generate data-driven recommendations
        recs = []
        # 1. Margin analysis
        margin_sql = f"""
            SELECT c.region, ROUND(AVG(d.net_profit / NULLIF(d.net_rev, 0)) * 100, 2) AS margin,
                   ROUND(SUM(d.net_rev), 2) AS rev
            FROM deals d {joins} {wh}
            GROUP BY c.region ORDER BY margin DESC
        """
        margins = db.execute(text(margin_sql), wp).fetchall()
        if margins:
            best = margins[0]
            worst = margins[-1]
            recs.append({"title": "Regional Performance", "type": "info",
                "text": f"{best[0]} leads with {best[1]}% margin (${best[2]/1e6:.1f}M rev). {worst[0]} trails at {worst[1]}% — investigate cost structure there."})

        # 2. Channel ROI
        ch_sql = f"""
            SELECT s.name, ROUND(AVG(s.cac), 2) AS cac,
                   ROUND(SUM(d.net_rev), 2) AS rev, COUNT(*) AS deals,
                   ROUND(SUM(d.net_profit) / NULLIF(SUM(d.net_rev), 0) * 100, 2) AS roi
            FROM deals d {joins} {wh}
            GROUP BY s.name ORDER BY roi DESC
        """
        channels = db.execute(text(ch_sql), wp).fetchall()
        if channels:
            best_ch = channels[0]
            worst_ch = channels[-1]
            recs.append({"title": "Channel Optimization", "type": "action",
                "text": f"Scale {best_ch[0]} (ROI: {best_ch[4]}%, {best_ch[3]} deals). Reduce spend on {worst_ch[0]} (ROI: {worst_ch[4]}%) — realloc budget to higher-performing channels."})

        # 3. Trend analysis
        trend_sql = f"""
            SELECT strftime('%Y-%m', d.deal_date) AS m,
                   ROUND(SUM(d.net_rev), 2) AS rev
            FROM deals d {joins} {wh}
            GROUP BY m ORDER BY m DESC LIMIT 6
        """
        trends = db.execute(text(trend_sql), wp).fetchall()
        if len(trends) >= 2:
            recent = trends[0][1]
            prev = trends[1][1]
            change = ((recent - prev) / prev * 100) if prev else 0
            direction = "up" if change > 0 else "down"
            recs.append({"title": "Revenue Trend", "type": "alert" if change < -5 else "info",
                "text": f"Revenue trended {direction} {abs(change):.1f}% month-over-month ({trends[0][0]}). {'Maintain current strategy.' if change > 0 else 'Investigate pipeline slowdown and accelerate deal closures.'}"})

        # 4. Product focus
        prod_sql = f"""
            SELECT p.name, ROUND(SUM(d.net_profit), 2) AS profit, COUNT(*) AS deals
            FROM deals d JOIN products p ON d.product_id = p.id {joins.replace('JOIN companies', 'JOIN companies').replace('JOIN marketing_sources', 'JOIN marketing_sources')}
            {wh}
            GROUP BY p.name ORDER BY profit DESC LIMIT 3
        """
        prods = db.execute(text(prod_sql), wp).fetchall()
        if prods:
            top = prods[0]
            recs.append({"title": "Product Priority", "type": "action",
                "text": f"Double down on {top[0]} (${top[1]/1e6:.1f}M profit, {top[2]} deals). Consider bundling with lower-performing products to lift overall portfolio margin."})

        return ChartData(labels=[r["title"] for r in recs], series=[{"name": "recommendations", "data": [0]}], values=[0])

    elif chart_type == "thresholds":
        # Real-time alert thresholds
        alerts = []
        # Margin check
        m_sql = f"SELECT ROUND(AVG(d.net_profit / NULLIF(d.net_rev, 0)) * 100, 2) FROM deals d {joins} {wh}"
        margin = db.execute(text(m_sql), wp).scalar() or 0
        if margin < 35:
            alerts.append({"level": "critical", "title": "Margin Below Target", "message": f"Portfolio margin at {margin}% — below 35% SLA threshold", "icon": "🚨"})
        elif margin < 40:
            alerts.append({"level": "warning", "title": "Margin Watch", "message": f"Margin at {margin}% — approaching 35% threshold", "icon": "⚠️"})
        else:
            alerts.append({"level": "ok", "title": "Margin Healthy", "message": f"Margin at {margin}% — above 40% target", "icon": "✅"})

        # MoM trend check
        trend_sql = f"""
            SELECT strftime('%Y-%m', d.deal_date) AS m, ROUND(SUM(d.net_rev), 2)
            FROM deals d {joins} {wh}
            GROUP BY m ORDER BY m DESC LIMIT 2
        """
        trend_rows = db.execute(text(trend_sql), wp).fetchall()
        if len(trend_rows) >= 2:
            curr, prev = trend_rows[0][1], trend_rows[1][1]
            chg = ((curr - prev) / prev * 100) if prev else 0
            if chg < -10:
                alerts.append({"level": "critical", "title": "Revenue Decline", "message": f"Revenue dropped {abs(chg):.1f}% month-over-month", "icon": "📉"})
            elif chg < -5:
                alerts.append({"level": "warning", "title": "Revenue Slowing", "message": f"Revenue down {abs(chg):.1f}% MoM — monitor pipeline", "icon": "⚠️"})
            else:
                alerts.append({"level": "ok", "title": "Revenue Trending", "message": f"Revenue {('up' if chg > 0 else 'down')} {abs(chg):.1f}% MoM", "icon": "📈"})

        # CAC check
        cac_sql = f"SELECT ROUND(SUM(d.cac_value) / COUNT(*), 0) FROM deals d {joins} {wh}"
        avg_cac = db.execute(text(cac_sql), wp).scalar() or 0
        if avg_cac > 800:
            alerts.append({"level": "warning", "title": "High CAC", "message": f"Avg CAC per deal: ${avg_cac:.0f} — target is $500", "icon": "💰"})
        else:
            alerts.append({"level": "ok", "title": "CAC Efficient", "message": f"Avg CAC per deal: ${avg_cac:.0f}", "icon": "✅"})

        return ChartData(labels=[a["title"] for a in alerts],
            series=[{"name": "alerts", "data": [0]}],
            values=[0])

    elif chart_type == "comparison":
        # Side-by-side region comparison: 2 regions, all metrics
        sql = f"""
            SELECT c.region,
                   ROUND(SUM(d.net_rev), 2) AS rev,
                   ROUND(SUM(d.net_profit), 2) AS profit,
                   ROUND(AVG(d.net_profit / NULLIF(d.net_rev, 0)) * 100, 2) AS margin,
                   COUNT(*) AS deals,
                   ROUND(SUM(d.cac_value), 0) AS cac
            FROM deals d {joins} {wh}
            GROUP BY c.region ORDER BY rev DESC
        """
        rows = db.execute(text(sql), wp).fetchall()
        labels = [r[0] for r in rows]
        return ChartData(labels=labels, series=[
            {"name": "Revenue", "data": [float(r[1]) for r in rows]},
            {"name": "Profit", "data": [float(r[2]) for r in rows]},
            {"name": "Margin %", "data": [float(r[3]) for r in rows]},
            {"name": "Deals", "data": [int(r[4]) for r in rows]},
            {"name": "Total CAC", "data": [float(r[5]) for r in rows]},
        ])

    raise HTTPException(status_code=404, detail=f"Unknown chart type: {chart_type}")


@app.post("/api/ai/insight", response_model=InsightResponse)
async def ai_insight(req: InsightRequest, db: Session = Depends(get_db)):
    result = await generate_insight(req.question, db)
    return InsightResponse(**result)

@app.post("/api/export/csv")
def export_csv(filters: ExportFilter, db: Session = Depends(get_db)):
    where, params = _build_where(
        filters.region, filters.industry, filters.date_from, filters.date_to,
        filters.product, filters.tier, filters.source,
    )
    rows = db.execute(text(f"{DEAL_SELECT} {DEAL_FROM}{where} ORDER BY d.deal_date DESC"), params).fetchall()
    output = io.StringIO()
    w = csv.writer(output)
    w.writerow(["ID","Code","Product","Category","Company","Region","Industry","Tier",
                "Source","Qty","Discount","Gross Rev","Disc Amt","Net Rev","Total Cost",
                "CAC","Opex","Net Profit","Date"])
    for r in rows: w.writerow(list(r))
    output.seek(0)
    return StreamingResponse(iter([output.getvalue()]), media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=deals_export.csv"})

@app.get("/")
def serve_index():
    return FileResponse(os.path.join(FRONTEND_DIR, "index.html"))

@app.get("/{full_path:path}")
def serve_frontend(full_path: str):
    fp = os.path.join(FRONTEND_DIR, full_path)
    if os.path.isfile(fp): return FileResponse(fp)
    return FileResponse(os.path.join(FRONTEND_DIR, "index.html"))
