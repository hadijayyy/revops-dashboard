"""AI Insight engine — maps natural-language questions to SQL, then optionally
asks an LLM to produce a human-readable answer."""

import os
import json
from typing import Optional
from sqlalchemy import text
from sqlalchemy.orm import Session
from datetime import date

# ─── Question → SQL mapping ───────────────────────────────────────────────────

QUESTION_PATTERNS = [
    {
        "keywords": ["which region has highest", "top region", "region with highest", "best region"],
        "query": """
            SELECT company.region AS label,
                   ROUND(SUM(deal.net_rev), 2) AS value
            FROM deals deal
            JOIN companies company ON deal.company_id = company.id
            {where}
            GROUP BY company.region
            ORDER BY value DESC
            LIMIT 10
        """,
        "description": "Revenue by region"
    },
    {
        "keywords": ["average margin", "avg margin", "margin rate", "what is the margin"],
        "query": """
            SELECT ROUND(AVG(deal.net_profit / NULLIF(deal.net_rev, 0)) * 100, 2) AS avg_margin_percent,
                   ROUND(SUM(deal.net_profit), 2) AS total_profit,
                   ROUND(SUM(deal.net_rev), 2) AS total_revenue
            FROM deals deal
            {where}
        """,
        "description": "Average margin"
    },
    {
        "keywords": ["top product", "best product", "product by profit", "top products", "highest profit product"],
        "query": """
            SELECT product.name AS label,
                   ROUND(SUM(deal.net_profit), 2) AS value,
                   ROUND(SUM(deal.net_rev), 2) AS revenue,
                   SUM(deal.qty) AS units
            FROM deals deal
            JOIN products product ON deal.product_id = product.id
            {where}
            GROUP BY product.name
            ORDER BY value DESC
            LIMIT 10
        """,
        "description": "Top products by profit"
    },
    {
        "keywords": ["compare channel", "channel comparison", "source performance", "which source", "compare source", "marketing channel"],
        "query": """
            SELECT src.name AS label,
                   ROUND(SUM(deal.net_rev), 2) AS revenue,
                   ROUND(SUM(deal.net_profit), 2) AS profit,
                   COUNT(*) AS deals_count,
                   ROUND(AVG(deal.cac_value), 2) AS avg_cac
            FROM deals deal
            JOIN marketing_sources src ON deal.source_id = src.id
            {where}
            GROUP BY src.name
            ORDER BY revenue DESC
        """,
        "description": "Channel / source comparison"
    },
    {
        "keywords": ["trend", "monthly trend", "revenue over time", "sales trend", "growth"],
        "query": """
            SELECT strftime('%Y-%m', deal.deal_date) AS label,
                   ROUND(SUM(deal.net_rev), 2) AS revenue,
                   ROUND(SUM(deal.net_profit), 2) AS profit,
                   COUNT(*) AS deals_count
            FROM deals deal
            {where}
            GROUP BY label
            ORDER BY label ASC
        """,
        "description": "Monthly trend"
    },
    {
        "keywords": ["revenue by industry", "industry revenue", "which industry", "industry performance"],
        "query": """
            SELECT company.industry AS label,
                   ROUND(SUM(deal.net_rev), 2) AS value,
                   ROUND(SUM(deal.net_profit), 2) AS profit,
                   COUNT(*) AS deals_count
            FROM deals deal
            JOIN companies company ON deal.company_id = company.id
            {where}
            GROUP BY company.industry
            ORDER BY value DESC
        """,
        "description": "Revenue by industry"
    },
    {
        "keywords": ["revenue by tier", "tier revenue", "segment performance", "enterprise vs", "smb vs"],
        "query": """
            SELECT company.tier AS label,
                   ROUND(SUM(deal.net_rev), 2) AS value,
                   ROUND(SUM(deal.net_profit), 2) AS profit,
                   COUNT(*) AS deals_count
            FROM deals deal
            JOIN companies company ON deal.company_id = company.id
            {where}
            GROUP BY company.tier
            ORDER BY value DESC
        """,
        "description": "Revenue by customer tier"
    },
    {
        "keywords": ["total revenue", "overall revenue", "total sales", "how much revenue"],
        "query": """
            SELECT ROUND(SUM(deal.net_rev), 2) AS total_revenue,
                   ROUND(SUM(deal.net_profit), 2) AS total_profit,
                   ROUND(SUM(deal.total_cost), 2) AS total_cost,
                   COUNT(*) AS deal_count
            FROM deals deal
            {where}
        """,
        "description": "Total revenue summary"
    },
    {
        "keywords": ["top company", "best company", "company by revenue", "customer by revenue", "top customer"],
        "query": """
            SELECT company.name AS label,
                   ROUND(SUM(deal.net_rev), 2) AS value,
                   ROUND(SUM(deal.net_profit), 2) AS profit,
                   COUNT(*) AS deals_count
            FROM deals deal
            JOIN companies company ON deal.company_id = company.id
            {where}
            GROUP BY company.name
            ORDER BY value DESC
            LIMIT 10
        """,
        "description": "Top companies by revenue"
    },
    {
        "keywords": ["most deals", "deal count", "number of deals", "how many deals"],
        "query": """
            SELECT COUNT(*) AS total_deals,
                   ROUND(AVG(deal.net_rev), 2) AS avg_deal_size,
                   ROUND(SUM(deal.net_rev), 2) AS total_revenue
            FROM deals deal
            {where}
        """,
        "description": "Deal count summary"
    },
]

DEFAULT_QUERY = """
    SELECT company.region AS label,
           ROUND(SUM(deal.net_rev), 2) AS value
    FROM deals deal
    JOIN companies company ON deal.company_id = company.id
    {where}
    GROUP BY company.region
    ORDER BY value DESC
"""


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _build_where_clause(question: str) -> str:
    """Build a simple WHERE clause if the question mentions a specific filter."""
    clauses = []
    # region filter
    known_regions = ["north america", "emea", "apac", "latam"]
    for region in known_regions:
        if region in question.lower():
            clauses.append(f"LOWER(company.region) = '{region}'")
            break
    # industry filter
    known_industries = ["technology", "finance", "healthcare", "manufacturing",
                        "retail", "energy", "education", "media"]
    for ind in known_industries:
        if ind in question.lower():
            clauses.append(f"LOWER(company.industry) = '{ind}'")
            break
    # tier filter
    known_tiers = ["enterprise", "mid-market", "smb"]
    for tier in known_tiers:
        if tier.lower() in question.lower():
            clauses.append(f"LOWER(company.tier) = '{tier}'")
            break
    # source filter
    known_sources = ["linkedin", "google search", "inbound", "outbound", "tech summit"]
    source_map = {
        "linkedin": "LinkedIn Account-Based Ads",
        "google search": "Google Search Intent SEO",
        "inbound": "Inbound / Partner Network",
        "outbound": "Outbound Sales Development",
        "tech summit": "Global Tech Summit",
    }
    for key, val in source_map.items():
        if key in question.lower():
            clauses.append(f"src.name = '{val}'")
            break

    if clauses:
        return " WHERE " + " AND ".join(clauses)
    return ""


def _find_best_pattern(question: str) -> dict:
    """Return the best-matching question pattern (or DEFAULT_QUERY)."""
    q_lower = question.lower()
    for pattern in QUESTION_PATTERNS:
        for kw in pattern["keywords"]:
            if kw in q_lower:
                return pattern
    # fallback: return the default region-revenue query
    return {
        "keywords": [],
        "query": DEFAULT_QUERY,
        "description": "Revenue breakdown",
    }


def _format_sql_results(rows, description: str) -> str:
    """Pretty-print a list of row dicts as a text summary."""
    if not rows:
        return f"**{description}**\nNo data found for the given criteria."

    lines = [f"📊 **{description}**\n"]
    if isinstance(rows[0], dict) and "label" in rows[0]:
        for row in rows:
            parts = [f"• **{row['label']}**"]
            for k, v in row.items():
                if k == "label":
                    continue
                if isinstance(v, float):
                    parts.append(f"{k.replace('_', ' ').title()}: ${v:,.2f}")
                else:
                    parts.append(f"{k.replace('_', ' ').title()}: {v}")
            lines.append("  " + " | ".join(parts))
        lines.append("")
    else:
        # single-row result
        row = rows[0] if isinstance(rows, list) else rows
        if isinstance(row, dict):
            for k, v in row.items():
                if isinstance(v, float):
                    lines.append(f"• **{k.replace('_', ' ').title()}**: ${v:,.2f}")
                else:
                    lines.append(f"• **{k.replace('_', ' ').title()}**: {v}")
        else:
            lines.append(str(row))

    return "\n".join(lines)


# ─── Public API ───────────────────────────────────────────────────────────────

async def generate_insight(question: str, db: Session) -> dict:
    """Main entry point: analyse *question*, run SQL, optionally ask an LLM."""
    pattern = _find_best_pattern(question)
    where_clause = _build_where_clause(question)
    sql = pattern["query"].format(where=where_clause)
    description = pattern["description"]

    # Run the SQL
    result = db.execute(text(sql))
    rows = [dict(r._mapping) for r in result]

    # Format as text
    formatted = _format_sql_results(rows, description)

    # Try LLM if API key is set
    api_key = os.environ.get("OPENAI_API_KEY", "").strip()
    if api_key:
        try:
            llm_response = await _ask_llm(question, rows, description, sql, api_key)
            return {
                "question": question,
                "insight": llm_response,
                "sql_used": sql,
                "source": "llm",
            }
        except Exception as exc:
            # Fall back to SQL summary on error
            pass

    return {
        "question": question,
        "insight": formatted,
        "sql_used": sql,
        "source": "sql",
    }


async def _ask_llm(question: str, rows, description: str, sql: str, api_key: str) -> str:
    """Send data to an OpenAI-compatible LLM and return the answer."""
    import httpx

    # Build a prompt
    prompt = f"""You are a RevOps analytics assistant. Answer the user's question using the data below.

**User Question:** {question}

**SQL Query Used:** {sql}

**Data (JSON):**
{json.dumps(rows, default=str, indent=2) if rows else "No data returned."}

Please provide a clear, concise answer in natural language. Include:
- The key insight(s) from the data
- Relevant numbers/dollars formatted nicely
- A recommendation or observation if applicable

Keep it under 200 words and use bullet points for readability.
"""

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": os.environ.get("OPENAI_MODEL", "gpt-4o-mini"),
        "messages": [
            {"role": "system", "content": "You are a helpful RevOps assistant."},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.3,
        "max_tokens": 600,
    }

    base_url = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1")
    url = f"{base_url.rstrip('/')}/chat/completions"

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(url, headers=headers, json=payload)
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"].strip()
