# Enterprise RevOps Dashboard

> **Interactive Revenue Operations Analytics Platform** — 11,000 deal records, 7 product lines, 4 global regions, 5 acquisition channels, 7 sales reps. Fully client-side, zero backend required.

![Dashboard](https://revops-dashboard-pi.vercel.app/og-image.png)

**🔗 Live Demo: [revops-dashboard-pi.vercel.app](https://revops-dashboard-pi.vercel.app)**

---

## 📊 What It Does

A production-grade Revenue Operations dashboard built as a single `index.html` file. Generates 11,000 seeded deals using a deterministic PRNG (mulberry32, seed=42) for reproducible analytics. No API calls, no database — pure client-side computation.

### Key Metrics Tracked
- **$259.4M** total realized revenue across 11,000 deals
- **43.8%** average profit margin
- **18.5x** overall marketing ROI
- **7** enterprise SaaS products across **4** global regions

## 🏗️ Architecture

```
Single-File Dashboard (index.html)
├── Tailwind CSS (CDN) — responsive UI
├── Chart.js (CDN) — 7 interactive chart types
├── Mulberry32 PRNG — deterministic 11K deal generation
├── Unified Filter Engine — 8 filter categories
├── Tab System — 6 analytical views
└── CSV Export — filtered data download
```

### Tabs
| Tab | Description |
|-----|-------------|
| **Executive Summary** | Revenue/profit trend (monthly/quarterly), portfolio distribution (region/client/rep) |
| **Sales Performance** | Rep/client/region breakdown with drilldown filtering |
| **CAC & Efficiency** | Channel ROI bubble chart, spend vs profit comparison |
| **YoY Trend Analysis** | Year-over-year comparison with monthly/quarterly granularity |
| **Region Comparison** | Side-by-side regional analysis with metrics table |
| **Deal Records** | Sortable, searchable data table with pagination |

### Interactive Features
- 🔍 **Multi-select filters** — Year, Quarter, Region, Sales Rep, Source, Client
- 📊 **Click-to-filter** — Click any chart element to drill down
- 🌙 **Dark mode** — Persistent theme toggle (localStorage)
- 📱 **Fully responsive** — Mobile sidebar, adaptive layouts
- 📥 **CSV export** — Download filtered datasets
- 🏷️ **Active filter badges** — Visual filter state with one-click removal

## 🚀 Quick Start

```bash
# Option 1: Open directly
open index.html

# Option 2: Local server
python3 -m http.server 8000
# Visit http://localhost:8000

# Option 3: Deploy to Vercel
vercel --prod
```

## 📁 Project Structure

```
revops-dashboard/
├── index.html          # Main dashboard (single-file, ~1300 lines)
├── standalone.html     # Standalone version
├── ANALYSIS.md         # Executive summary & recommendations
├── backend/            # Optional Python backend
│   ├── main.py         # FastAPI server
│   ├── models.py       # Data models
│   ├── database.py     # SQLite integration
│   └── ai_engine.py    # AI analytics engine
└── README.md
```

## 🛠️ Tech Stack

- **Frontend:** Vanilla JS, Tailwind CSS, Chart.js
- **Backend (optional):** Python, FastAPI, SQLite
- **Deployment:** Vercel (auto-deploy from GitHub)
- **Data Generation:** mulberry32 PRNG (seed=42, deterministic)

## 📊 Data Model

### Products (7)
| Product | Category | Base Price |
|---------|----------|------------|
| AWS Cloud Infra | Infrastructure | $7,500 |
| Azure Ent. Suite | Platform | $4,500 |
| Snowflake Data | Analytics | $3,200 |
| Salesforce Cloud | CRM | $2,400 |
| CrowdStrike Sec | Security | $1,800 |
| HubSpot Pro | Marketing | $1,300 |
| Google Workspace | Productivity | $800 |

### Regions (4)
- **EMEA** — Europe, Middle East & Africa
- **APAC** — Asia-Pacific
- **North America** — US, Canada
- **LATAM** — Latin America

### Acquisition Channels (5)
| Channel | Avg CAC | ROI |
|---------|---------|-----|
| Partner Network | $75 | 149.3x |
| Google SEO | $150 | 72.4x |
| Outbound Sales | $500 | 20.7x |
| LinkedIn Ads | $850 | 11.3x |
| Tech Summit | $1,200 | 8.0x |

## 📈 Key Findings

### Revenue Distribution
- **EMEA** leads with $78.2M (30.2% of total)
- **AWS Cloud Infra** dominates at $94.3M (36.4% of total)
- **Partner Network** delivers 149.3x ROI — highest efficiency

### Performance Insights
- Top performer: **Jim Halpert** ($40.0M revenue, $25.1K avg deal)
- Q1 consistently strongest quarter ($26.6M avg)
- 2024→2025 YoY growth: +3.3% revenue, +3.7% profit
- Profit margin stable across all dimensions (43-44%)

### Optimization Opportunities
1. **Shift budget to Partner Network & SEO** — 149x and 72x ROI vs 8-11x for paid channels
2. **Expand Snowflake & CrowdStrike sales** — 47.9% and 48.5% margins (highest)
3. **Focus on APAC growth** — largest deal volume, room for margin improvement
4. **Reduce Tech Summit spend** — lowest ROI (8.0x), highest CAC ($1,200)

## 🔧 Customization

### Change Data Seed
```javascript
const SEED = 42; // Change this value for different datasets
```

### Add New Products
```javascript
const PRODUCTS = [
    // Add your products here
    { code: "PROD_008", name: "New Product", cost: 1000, price: 2000 },
];
```

### Modify Date Range
```javascript
const START_DATE = new Date(2024, 0, 1); // Change start date
const TOTAL_DEALS = 11000; // Change deal count
```

## 📊 Analysis Document

See **[ANALYSIS.md](./ANALYSIS.md)** for the full executive summary and strategic recommendations.

## 📄 License

MIT License — Free for commercial and personal use.

---

**Built with ❤️ for Revenue Operations teams**
