# 📊 Hospital Analytics — Key Insights

## Overview

This document summarizes the key findings from the Hospital Analytics project
across three dashboards: Procedures, Sales Data, and Train Schedule.

---

## 🔬 Dashboard 1 — Procedures

### KPI Summary
| Metric | Value |
|---|---|
| Total Procedures | 8,580 |
| Average Procedure Cost | ₹32.89K |
| Success Rate | 89.99% |
| Total Procedure Revenue | ₹1.41T |

### Key Findings

**Success Rate is below target**
- Overall success rate of 89.99% is below the 90% benchmark
- Patients with outcomes of Recovered or Improved are counted as successful
- Requires clinical review to identify departments dragging the rate down

**Department D01 leads in volume**
- Department D01 has the highest number of procedures performed
- Followed by D05 and D07
- High volume departments should be monitored for quality alongside quantity

**Procedure costs vary significantly**
- Average procedure cost is ₹32.89K
- Some individual procedures exceed ₹19,000 per admission
- Angiography appears frequently as a high-cost procedure

**Admissions typically have 1–3 procedures**
- Most admissions have between 1 and 3 procedures recorded
- Admissions with 3 procedures represent the highest complexity cases

### Recommendations
- Investigate departments with Success Rate below 90% for process improvements
- Review high-cost procedures for cost optimization opportunities
- Monitor readmission rates alongside procedure outcomes

---

## 💰 Dashboard 2 — Sales Data

### KPI Summary
| Metric | Value |
|---|---|
| Total Sales | ₹15K (Jan 2021 sample) |
| Total Transactions | 24 |
| Average Sale Value | ₹638.38 |
| Max Single Sale | ₹939 |

### Regional Sales (salesdata1)
| State | Total Sales | Share |
|---|---|---|
| Bihar | ₹6K | ~40% |
| Jharkhand | ₹6K | ~40% |
| Maharastra | ₹3K | ~20% |

### Key Findings

**Bihar and Jharkhand are top performing states**
- Both states contribute equally at approximately 40% of total sales each
- Maharastra contributes around 20% — potential growth opportunity

**Sales trend shows daily fluctuation**
- Daily sales in January 2021 range from ₹767 to ₹2,207
- Peak sales observed around Jan 19–20
- Dip observed around Jan 14–16 requiring investigation

**Sales declined over the period**
- Sales Growth % shows a negative value
- Indicates overall sales were lower at end of period vs start
- Needs further investigation with more months of data

### Recommendations
- Expand data collection beyond January 2021 for meaningful trend analysis
- Investigate low sales days (Jan 14–16) for operational issues
- Develop growth strategy for Maharastra region to match Bihar and Jharkhand

---

## 🚆 Dashboard 3 — Train Schedule

### KPI Summary
| Metric | Value |
|---|---|
| Total Trains | Multiple routes |
| Total Stations | Multiple stations |
| Total Schedules | All active schedules |

### Key Findings

**Station distribution is uneven**
- Some stations appear more frequently in the schedule than others
- High-frequency stations likely serve more hospital staff

**Schedule utilization visible via Gauge**
- Gauge chart shows current schedules vs maximum capacity
- Helps operations team plan additional routes if needed

### Recommendations
- Add more stations if staff transport demand increases
- Review timing distribution to avoid peak congestion
- Track on-time performance once delay data is available

---

## 🔗 Cross-Dashboard Insights

**Procedure volume drives revenue**
- Higher procedure counts in a department directly correlate with higher revenue
- Department D01 likely generates the most revenue given its procedure volume

**Patient outcomes affect readmission rates**
- Patients with outcome "Referred" may return as new admissions
- Tracking referred patients could reduce unexpected readmissions

**Staff transport supports operations**
- Train schedule ensures medical staff arrive on time
- Delays in transport could indirectly affect procedure scheduling

---

## 🛠 Tools Used

| Tool | Purpose |
|---|---|
| Power BI Desktop | Interactive dashboards and visualizations |
| Python (pandas) | Data cleaning and analysis |
| Python (scikit-learn) | Doctor attribution model |
| Python (openpyxl) | Excel report generation |
| SQL | Data extraction and transformation |
| Excel | Reporting and data dictionary |

---

## 📁 Related Files

- `Hospital_Analytics_Dashboard.html` — Interactive HTML dashboard
- `Hospital_Analytics_Report.xlsx` — Full Excel report
- `doctor_attribution_scores.csv` — Doctor performance scores
- `hospital_queries.sql` — All SQL queries used
- `POWERBI_SETUP_GUIDE.md` — Power BI implementation guide

---

*Last updated: March 2026*
