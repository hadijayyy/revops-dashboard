"""SQLAlchemy models and Pydantic schemas for the RevOps Dashboard."""

from sqlalchemy import Column, Integer, String, Float, Date, ForeignKey
from sqlalchemy.orm import declarative_base, relationship
from pydantic import BaseModel
from typing import Optional, List
from datetime import date

Base = declarative_base()


# ─── SQLAlchemy Models ────────────────────────────────────────────────────────

class Product(Base):
    __tablename__ = "products"

    id = Column(Integer, primary_key=True, autoincrement=True)
    code = Column(String(20), unique=True, nullable=False)
    name = Column(String(200), nullable=False)
    category = Column(String(100), nullable=False)
    cost = Column(Float, nullable=False)
    price = Column(Float, nullable=False)


class Company(Base):
    __tablename__ = "companies"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(200), nullable=False)
    region = Column(String(100), nullable=False)
    industry = Column(String(100), nullable=False)
    tier = Column(String(50), nullable=False)


class MarketingSource(Base):
    __tablename__ = "marketing_sources"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(200), nullable=False)
    cac = Column(Float, nullable=False)


class Deal(Base):
    __tablename__ = "deals"

    id = Column(Integer, primary_key=True, autoincrement=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False)
    source_id = Column(Integer, ForeignKey("marketing_sources.id"), nullable=False)
    qty = Column(Integer, nullable=False)
    discount = Column(Float, nullable=False)
    gross_rev = Column(Float, nullable=False)
    discount_amt = Column(Float, nullable=False)
    net_rev = Column(Float, nullable=False)
    total_cost = Column(Float, nullable=False)
    cac_value = Column(Float, nullable=False)
    opex_overhead = Column(Float, nullable=False)
    net_profit = Column(Float, nullable=False)
    deal_date = Column(Date, nullable=False)

    product = relationship("Product", lazy="joined")
    company = relationship("Company", lazy="joined")
    source = relationship("MarketingSource", lazy="joined")


# ─── Pydantic Schemas ─────────────────────────────────────────────────────────

class DealOut(BaseModel):
    """Schema for a single deal returned by the API."""
    id: int
    product_code: str
    product_name: str
    product_category: str
    company_name: str
    region: str
    industry: str
    tier: str
    source_name: str
    qty: int
    discount: float
    gross_rev: float
    discount_amt: float
    net_rev: float
    total_cost: float
    cac_value: float
    opex_overhead: float
    net_profit: float
    deal_date: str

    class Config:
        from_attributes = True


class PaginatedDeals(BaseModel):
    total: int
    page: int
    page_size: int
    total_pages: int
    deals: List[DealOut]


class KPIsOut(BaseModel):
    total_revenue: float
    total_cost: float
    total_margin: float
    total_cac: float
    total_opex: float
    net_profit: float
    avg_margin: float
    row_count: int


class ChartData(BaseModel):
    labels: List[str]
    datasets: Optional[List[dict]] = None
    values: Optional[List[float]] = None
    series: Optional[List[dict]] = None
    points: Optional[List[dict]] = None


class InsightRequest(BaseModel):
    question: str


class InsightResponse(BaseModel):
    question: str
    insight: str
    sql_used: Optional[str] = None
    source: str  # "llm" or "sql"


class ExportFilter(BaseModel):
    region: Optional[str] = None
    industry: Optional[str] = None
    date_from: Optional[str] = None
    date_to: Optional[str] = None
    product: Optional[str] = None
    tier: Optional[str] = None
    source: Optional[str] = None
