Wind Portfolio Intelligence
Finance-grade analytics for wind portfolios · Scenario Engine · Risk Intelligence
An interactive analytics application for evaluating and comparing wind energy project portfolios.
The app enables users to explore multiple projects, adjust key financial assumptions, and understand both returns and structural risk across a portfolio.
🎯 Objective
To transform multiple wind project financial models into a standardised, interactive decision tool that allows:
Portfolio comparison
Scenario analysis
Risk identification
Project-level drill-down
⚙️ Core Features
📊 Portfolio View
Aggregated KPIs:
Installed capacity
IRR
NPV
Portfolio-level cash flow and DSCR trends
⚠️ Risk Analysis
Health score based on:
IRR
DSCR
LCOE
Capacity factor
Risk flags:
Low DSCR
Watchlist projects
DSCR vs IRR analysis
🔍 Project Drill-Down
Individual project KPIs
Assumptions overview
20-year time series:
Cash flow
DSCR
⚖️ Comparison Engine
Compare projects side-by-side
Identify best and worst performers
🌍 Geospatial View
Portfolio map
Region-based filtering
🔧 Key Inputs (Adjustable)
CAPEX
Yield / production
PPA price
Scenario assumptions
🧠 Key Insight
The goal is not only to calculate returns, but to evaluate:
Whether the financial structure is robust enough to sustain risk and variability.
🏗️ Conceptual Architecture
Multiple Project Models
        ↓
Standardised Data Layer
        ↓
Scenario Engine
        ↓
KPI & Risk Computation
        ↓
Interactive Dashboard
📦 Setup
git clone https://github.com/nishaverma24-bot/wind-portfolio-intelligence.git
cd wind-portfolio-intelligence
pip install -r requirements.txt
▶️ Run
streamlit run app.py
📁 Structure
wind-portfolio-intelligence/
├── app.py
├── style.css
├── images/
├── data/ (optional / local)
└── README.md
🚧 Status
Prototype version
Uses synthetic or local data
Designed to integrate real financial models
🔮 Next Steps
Add structured input datasets
Improve scenario engine
Add bankability analysis (DSCR stress testing)
Enhance UI/UX for decision-makers
👩‍💻 Author
Nisha Verma
MBA Sustainability — TU Berlin
⭐ Note
This project is designed as a scalable analytics tool, not a static dashboard —
focusing on comparability, transparency, and decision support for renewable energy portfolios.