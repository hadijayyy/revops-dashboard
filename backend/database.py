"""SQLite database setup and seeded data generation."""

import os
import random
from datetime import date, timedelta
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, Session

from models import Base, Product, Company, MarketingSource, Deal

DATABASE_URL = os.path.join(os.path.dirname(__file__), "revops.db")

engine = create_engine(f"sqlite:///{DATABASE_URL}", echo=False)
SessionLocal = sessionmaker(bind=engine)


# ─── Static Reference Data ────────────────────────────────────────────────────

PRODUCTS_DATA = [
    {"code": "PROD_001", "name": "Microsoft Azure Enterprise Suite",
     "category": "Cloud Infrastructure", "cost": 2500, "price": 4500},
    {"code": "PROD_002", "name": "Amazon AWS Cloud Infrastructure",
     "category": "Cloud Infrastructure", "cost": 4000, "price": 7500},
    {"code": "PROD_003", "name": "Google Workspace Enterprise",
     "category": "Productivity & SaaS", "cost": 300, "price": 800},
    {"code": "PROD_004", "name": "Salesforce Sales Cloud",
     "category": "CRM & Sales Tech", "cost": 1200, "price": 2400},
    {"code": "PROD_005", "name": "HubSpot Marketing Hub Pro",
     "category": "Marketing Automation", "cost": 600, "price": 1300},
    {"code": "PROD_006", "name": "CrowdStrike Falcon Endpoint Security",
     "category": "Cybersecurity", "cost": 800, "price": 1800},
    {"code": "PROD_007", "name": "Snowflake Data Cloud",
     "category": "Data Infrastructure", "cost": 1500, "price": 3200},
    {"code": "PROD_008", "name": "Datadog Infrastructure Monitoring",
     "category": "Observability & Devops", "cost": 400, "price": 950},
    {"code": "PROD_009", "name": "Cisco Meraki Networking",
     "category": "Networking Hardware", "cost": 1100, "price": 2200},
    {"code": "PROD_010", "name": "SAP S/4HANA ERP",
     "category": "Enterprise ERP", "cost": 5000, "price": 9800},
]

COMPANIES_DATA = [
    # Enterprise
    {"name": "Acme Corporation",          "region": "North America", "industry": "Technology",    "tier": "Enterprise"},
    {"name": "GlobalTech Solutions",      "region": "North America", "industry": "Technology",    "tier": "Enterprise"},
    {"name": "EuroMed Health Partners",   "region": "EMEA",          "industry": "Healthcare",    "tier": "Enterprise"},
    {"name": "AsiaPacific Manufacturing", "region": "APAC",          "industry": "Manufacturing", "tier": "Enterprise"},
    {"name": "LatAm Financial Services",  "region": "LATAM",         "industry": "Finance",       "tier": "Enterprise"},
    {"name": "Nordic Retail Group",       "region": "EMEA",          "industry": "Retail",        "tier": "Enterprise"},
    {"name": "Sunrise Energy Corp",       "region": "North America", "industry": "Energy",        "tier": "Enterprise"},
    {"name": "EduGlobal Learning",        "region": "APAC",          "industry": "Education",     "tier": "Enterprise"},
    {"name": "MediaOne International",    "region": "EMEA",          "industry": "Media",         "tier": "Enterprise"},
    {"name": "Quantum Computing Inc",     "region": "North America", "industry": "Technology",    "tier": "Enterprise"},
    # Mid-Market
    {"name": "DataDriven Analytics",      "region": "North America", "industry": "Technology",    "tier": "Mid-Market"},
    {"name": "Greenfield Healthcare",     "region": "EMEA",          "industry": "Healthcare",    "tier": "Mid-Market"},
    {"name": "Pacific Trade Logistics",   "region": "APAC",          "industry": "Manufacturing", "tier": "Mid-Market"},
    {"name": "Banco Atlantico",           "region": "LATAM",         "industry": "Finance",       "tier": "Mid-Market"},
    {"name": "TechRetail Solutions",      "region": "EMEA",          "industry": "Retail",        "tier": "Mid-Market"},
    {"name": "CloudBase Systems",         "region": "North America", "industry": "Technology",    "tier": "Mid-Market"},
    {"name": "MediCare Plus",            "region": "North America", "industry": "Healthcare",    "tier": "Mid-Market"},
    {"name": "Sapphire Mining Co",        "region": "APAC",          "industry": "Energy",        "tier": "Mid-Market"},
    {"name": "CampusConnect Edu",         "region": "North America", "industry": "Education",     "tier": "Mid-Market"},
    {"name": "Digital Press Media",       "region": "EMEA",          "industry": "Media",         "tier": "Mid-Market"},
    # SMB
    {"name": "StartupAI Labs",            "region": "North America", "industry": "Technology",    "tier": "SMB"},
    {"name": "Local Dental Care",         "region": "North America", "industry": "Healthcare",    "tier": "SMB"},
    {"name": "Boutique Manufacturing",    "region": "EMEA",          "industry": "Manufacturing", "tier": "SMB"},
    {"name": "MegaMart Retail",           "region": "APAC",          "industry": "Retail",        "tier": "SMB"},
    {"name": "CreditUnion Local",         "region": "North America", "industry": "Finance",       "tier": "SMB"},
    {"name": "SolarPower Home",           "region": "EMEA",          "industry": "Energy",        "tier": "SMB"},
    {"name": "LearnFast Tutoring",        "region": "LATAM",         "industry": "Education",     "tier": "SMB"},
    {"name": "Indie Broadcast Network",   "region": "North America", "industry": "Media",         "tier": "SMB"},
    {"name": "SmartOffice Solutions",     "region": "APAC",          "industry": "Technology",    "tier": "SMB"},
    {"name": "AgriGrow Partners",         "region": "LATAM",         "industry": "Manufacturing", "tier": "SMB"},
]

SOURCES_DATA = [
    {"name": "LinkedIn Account-Based Ads", "cac": 850},
    {"name": "Google Search Intent SEO",   "cac": 150},
    {"name": "Inbound / Partner Network",  "cac": 75},
    {"name": "Outbound Sales Development", "cac": 500},
    {"name": "Global Tech Summit",         "cac": 1200},
]

QUANTITIES = [1, 2, 5, 10, 25]
QUANTITY_WEIGHTS = [0.4, 0.3, 0.18, 0.09, 0.03]

DISCOUNTS = [0.0, 0.05, 0.10, 0.15, 0.25]
DISCOUNT_WEIGHTS = [0.55, 0.20, 0.13, 0.09, 0.03]

START_DATE = date(2024, 1, 1)
END_DATE = date(2026, 6, 30)
TOTAL_DEALS = 11000
SEED = 42


# ─── Database Helpers ─────────────────────────────────────────────────────────

def get_db() -> Session:
    """Yield a database session (for FastAPI dependency injection)."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """Create all tables if they don't exist."""
    Base.metadata.create_all(bind=engine)


def seed_data(db: Session) -> None:
    """Seed database with reference data and 11 000 random deals (seed=42)."""
    # Check if data already exists
    existing = db.query(Deal).count()
    if existing > 0:
        return  # already seeded

    # ── Reference tables ──────────────────────────────────────────────────
    products = []
    for p in PRODUCTS_DATA:
        prod = Product(**p)
        db.add(prod)
        products.append(prod)
    db.flush()

    companies = []
    for c in COMPANIES_DATA:
        comp = Company(**c)
        db.add(comp)
        companies.append(comp)
    db.flush()

    sources = []
    for s in SOURCES_DATA:
        src = MarketingSource(**s)
        db.add(src)
        sources.append(src)
    db.flush()

    # ── Generate deals with seeded random ─────────────────────────────────
    rng = random.Random(SEED)
    days_range = (END_DATE - START_DATE).days  # 911 days

    for _ in range(TOTAL_DEALS):
        product = rng.choice(products)
        company = rng.choice(companies)
        source = rng.choice(sources)

        qty = rng.choices(QUANTITIES, weights=QUANTITY_WEIGHTS)[0]
        disc = rng.choices(DISCOUNTS, weights=DISCOUNT_WEIGHTS)[0]

        rand_days = rng.randint(0, days_range)
        deal_date = START_DATE + timedelta(days=rand_days)

        # Seasonal multiplier: Q4 surge, Q1 slowdown
        month = deal_date.month
        seasonal = {1: 0.82, 2: 0.85, 3: 0.92, 4: 0.95, 5: 1.0, 6: 1.05,
                    7: 0.98, 8: 0.95, 9: 1.08, 10: 1.15, 11: 1.25, 12: 1.30}
        season_mult = seasonal.get(month, 1.0)
        noise = 1.0 + rng.uniform(-0.08, 0.08)  # ±8% random noise
        price = round(product.price * season_mult * noise)
        cost = round(product.cost * (1.0 + rng.uniform(-0.03, 0.03)))

        gross_rev = qty * price
        discount_amt = round(gross_rev * disc, 2)
        net_rev = round(gross_rev - discount_amt, 2)
        total_cost = qty * cost
        cac_value = source.cac
        opex_overhead = round(net_rev * 0.03, 2)
        net_profit = round(net_rev - total_cost - cac_value - opex_overhead, 2)

        deal = Deal(
            product_id=product.id,
            company_id=company.id,
            source_id=source.id,
            qty=qty,
            discount=disc,
            gross_rev=gross_rev,
            discount_amt=discount_amt,
            net_rev=net_rev,
            total_cost=total_cost,
            cac_value=cac_value,
            opex_overhead=opex_overhead,
            net_profit=net_profit,
            deal_date=deal_date,
        )
        db.add(deal)

    db.commit()
