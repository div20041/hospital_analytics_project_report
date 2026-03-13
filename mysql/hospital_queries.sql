-- ============================================================
--  HOSPITAL ANALYTICS — SQL QUERY PORTFOLIO
--  Database: hospital.db (SQLite)
--  Shows: CTEs, Window Functions, Subqueries, Aggregations,
--         CASE WHEN, JOINs, RANK, LAG, ROLLING AVERAGES
-- ============================================================

-- ─── QUERY 1: Department Revenue Ranking (Window Function + CTE) ────────────
-- Business Question: Which departments generate the most revenue?
-- Skills: CTE, SUM, RANK() OVER, ROUND

WITH dept_revenue AS (
    SELECT
        department_name,
        COUNT(admission_id)                          AS total_admissions,
        ROUND(SUM(total_bill), 2)                    AS total_revenue,
        ROUND(AVG(total_bill), 2)                    AS avg_bill_per_patient,
        ROUND(SUM(insurance_covered), 2)             AS insurance_recovered,
        ROUND(SUM(patient_paid), 2)                  AS patient_collections,
        ROUND(AVG(length_of_stay), 1)                AS avg_length_of_stay
    FROM admissions
    GROUP BY department_name
)
SELECT
    department_name,
    total_admissions,
    total_revenue,
    avg_bill_per_patient,
    insurance_recovered,
    patient_collections,
    avg_length_of_stay,
    RANK() OVER (ORDER BY total_revenue DESC)        AS revenue_rank,
    ROUND(total_revenue * 100.0 /
          SUM(total_revenue) OVER (), 2)             AS revenue_share_pct
FROM dept_revenue
ORDER BY revenue_rank;


-- ─── QUERY 2: Monthly Revenue Trend + MoM Growth (LAG + Window) ────────────
-- Business Question: How is revenue trending month over month?
-- Skills: LAG(), ROUND, CASE WHEN, date functions

WITH monthly AS (
    SELECT
        SUBSTR(admission_date, 1, 7)                 AS year_month,
        COUNT(admission_id)                          AS admissions,
        ROUND(SUM(total_bill), 2)                    AS revenue
    FROM admissions
    GROUP BY SUBSTR(admission_date, 1, 7)
)
SELECT
    year_month,
    admissions,
    revenue,
    LAG(revenue) OVER (ORDER BY year_month)          AS prev_month_revenue,
    ROUND(
        (revenue - LAG(revenue) OVER (ORDER BY year_month))
        * 100.0 / NULLIF(LAG(revenue) OVER (ORDER BY year_month), 0),
    2)                                               AS mom_growth_pct,
    CASE
        WHEN revenue > LAG(revenue) OVER (ORDER BY year_month) THEN '▲ Growth'
        WHEN revenue < LAG(revenue) OVER (ORDER BY year_month) THEN '▼ Decline'
        ELSE '→ Flat'
    END                                              AS trend
FROM monthly
ORDER BY year_month;


-- ─── QUERY 3: Patient Readmission Rate by Department + Severity ─────────────
-- Business Question: Which department + severity combo has the highest readmission?
-- Skills: GROUP BY multiple, ROUND, HAVING, subquery

SELECT
    a.department_name,
    a.severity,
    COUNT(*)                                         AS total_admissions,
    SUM(a.readmitted_30days)                         AS readmissions,
    ROUND(SUM(a.readmitted_30days) * 100.0
          / COUNT(*), 2)                             AS readmission_rate_pct,
    ROUND(AVG(a.length_of_stay), 1)                  AS avg_los,
    ROUND(AVG(a.total_bill), 0)                      AS avg_bill
FROM admissions a
GROUP BY a.department_name, a.severity
HAVING COUNT(*) >= 20
ORDER BY readmission_rate_pct DESC
LIMIT 20;


-- ─── QUERY 4: Doctor Performance Scorecard (Multi-metric ranking) ────────────
-- Business Question: Rank doctors by revenue generated + patient outcomes
-- Skills: JOIN, multiple aggregations, RANK() OVER PARTITION BY

WITH doc_stats AS (
    SELECT
        d.doctor_id,
        d.doctor_name,
        d.specialization,
        d.experience_years,
        COUNT(a.admission_id)                        AS patients_treated,
        ROUND(SUM(a.total_bill), 2)                  AS total_revenue_generated,
        ROUND(AVG(a.length_of_stay), 1)              AS avg_patient_los,
        ROUND(AVG(a.total_bill), 0)                  AS avg_bill_per_patient,
        SUM(CASE WHEN a.outcome = 'Recovered' THEN 1 ELSE 0 END)  AS recoveries,
        SUM(CASE WHEN a.readmitted_30days = 1 THEN 1 ELSE 0 END)  AS readmissions,
        ROUND(SUM(CASE WHEN a.outcome = 'Recovered' THEN 1.0 ELSE 0 END)
              / NULLIF(COUNT(*), 0) * 100, 1)        AS recovery_rate_pct
    FROM doctors d
    LEFT JOIN admissions a ON d.doctor_id = a.doctor_id
    GROUP BY d.doctor_id
)
SELECT
    doctor_name,
    specialization,
    experience_years,
    patients_treated,
    total_revenue_generated,
    avg_bill_per_patient,
    avg_patient_los,
    recovery_rate_pct,
    readmissions,
    RANK() OVER (PARTITION BY specialization
                 ORDER BY total_revenue_generated DESC) AS dept_revenue_rank,
    RANK() OVER (PARTITION BY specialization
                 ORDER BY recovery_rate_pct DESC)       AS dept_recovery_rank
FROM doc_stats
WHERE patients_treated > 0
ORDER BY specialization, dept_revenue_rank;


-- ─── QUERY 5: Insurance Provider Analysis (Revenue Leakage) ─────────────────
-- Business Question: Which insurers pay the least? Where is the collection gap?
-- Skills: CASE WHEN, ROUND, multiple aggregations, ORDER BY

SELECT
    insurance_provider,
    COUNT(*)                                         AS total_claims,
    ROUND(SUM(total_bill), 2)                        AS total_billed,
    ROUND(SUM(insurance_covered), 2)                 AS total_insurer_paid,
    ROUND(SUM(patient_paid), 2)                      AS total_patient_paid,
    ROUND(SUM(total_bill - insurance_covered
              - patient_paid), 2)                    AS revenue_gap,
    ROUND(SUM(insurance_covered) * 100.0
          / NULLIF(SUM(total_bill), 0), 1)           AS insurer_coverage_pct,
    ROUND(AVG(total_bill), 0)                        AS avg_claim_value,
    CASE
        WHEN SUM(insurance_covered) * 100.0
             / NULLIF(SUM(total_bill), 0) >= 70      THEN 'High Coverage'
        WHEN SUM(insurance_covered) * 100.0
             / NULLIF(SUM(total_bill), 0) >= 40      THEN 'Medium Coverage'
        ELSE 'Low Coverage'
    END                                              AS coverage_category
FROM admissions
GROUP BY insurance_provider
ORDER BY total_billed DESC;


-- ─── QUERY 6: Patient Cohort Analysis — Repeat Visitors ─────────────────────
-- Business Question: How many patients came back? What's their lifetime value?
-- Skills: Subquery, GROUP BY, HAVING, COUNT DISTINCT

WITH visit_counts AS (
    SELECT
        patient_id,
        COUNT(admission_id)                          AS total_visits,
        MIN(admission_date)                          AS first_visit,
        MAX(admission_date)                          AS last_visit,
        ROUND(SUM(total_bill), 2)                    AS lifetime_value,
        ROUND(AVG(total_bill), 2)                    AS avg_spend_per_visit
    FROM admissions
    GROUP BY patient_id
)
SELECT
    CASE
        WHEN total_visits = 1  THEN '1 Visit (One-time)'
        WHEN total_visits = 2  THEN '2 Visits'
        WHEN total_visits <= 4 THEN '3–4 Visits'
        ELSE '5+ Visits (High Value)'
    END                                              AS visit_segment,
    COUNT(*)                                         AS patients_in_segment,
    ROUND(AVG(lifetime_value), 0)                    AS avg_lifetime_value,
    ROUND(SUM(lifetime_value), 0)                    AS segment_total_revenue,
    ROUND(AVG(avg_spend_per_visit), 0)               AS avg_spend_per_visit
FROM visit_counts
GROUP BY visit_segment
ORDER BY avg_lifetime_value DESC;


-- ─── QUERY 7: 3-Month Rolling Revenue Average (Window + Subquery) ───────────
-- Business Question: Smooth out revenue spikes to see true trend
-- Skills: AVG() OVER with ROWS BETWEEN, window frame

WITH monthly_rev AS (
    SELECT
        SUBSTR(admission_date, 1, 7)                 AS ym,
        ROUND(SUM(total_bill), 2)                    AS revenue,
        COUNT(*)                                     AS admissions
    FROM admissions
    GROUP BY SUBSTR(admission_date, 1, 7)
)
SELECT
    ym,
    admissions,
    revenue,
    ROUND(AVG(revenue) OVER (
        ORDER BY ym
        ROWS BETWEEN 2 PRECEDING AND CURRENT ROW
    ), 2)                                            AS rolling_3m_avg,
    ROUND(SUM(revenue) OVER (
        ORDER BY ym
        ROWS UNBOUNDED PRECEDING
    ), 2)                                            AS cumulative_revenue
FROM monthly_rev
ORDER BY ym;


-- ─── QUERY 8: Top Procedures by Revenue + Frequency ──────────────────────────
-- Business Question: Which procedures drive the most revenue?
-- Skills: JOIN, GROUP BY, NTILE window function

SELECT
    p.procedure_name,
    a.department_name,
    COUNT(p.procedure_id)                            AS times_performed,
    ROUND(SUM(p.cost), 2)                            AS total_revenue,
    ROUND(AVG(p.cost), 0)                            AS avg_cost,
    ROUND(MIN(p.cost), 0)                            AS min_cost,
    ROUND(MAX(p.cost), 0)                            AS max_cost,
    NTILE(4) OVER (ORDER BY SUM(p.cost) DESC)        AS revenue_quartile
FROM procedures p
JOIN admissions a ON p.admission_id = a.admission_id
GROUP BY p.procedure_name, a.department_name
ORDER BY total_revenue DESC
LIMIT 20;


-- ─── QUERY 9: Bed Utilisation & Average LOS by Bed Type ─────────────────────
-- Business Question: Are premium beds generating premium revenue?
-- Skills: GROUP BY, CASE WHEN, ROUND

SELECT
    bed_type,
    admission_type,
    COUNT(*)                                         AS admissions,
    ROUND(AVG(length_of_stay), 1)                    AS avg_los_days,
    ROUND(AVG(total_bill), 0)                        AS avg_bill,
    ROUND(SUM(total_bill), 0)                        AS total_revenue,
    ROUND(AVG(total_bill) / NULLIF(AVG(length_of_stay), 0), 0) AS revenue_per_day,
    ROUND(SUM(readmitted_30days) * 100.0
          / COUNT(*), 1)                             AS readmission_rate_pct
FROM admissions
GROUP BY bed_type, admission_type
ORDER BY avg_bill DESC;


-- ─── QUERY 10: Patient Age Group Analysis ─────────────────────────────────────
-- Business Question: Which age group is most profitable and highest risk?
-- Skills: JOIN, CASE WHEN for age buckets, multiple metrics

SELECT
    CASE
        WHEN p.age < 18  THEN '0–17 Pediatric'
        WHEN p.age < 35  THEN '18–34 Young Adult'
        WHEN p.age < 55  THEN '35–54 Middle Age'
        WHEN p.age < 70  THEN '55–69 Senior'
        ELSE '70+ Elderly'
    END                                              AS age_group,
    COUNT(a.admission_id)                            AS admissions,
    COUNT(DISTINCT a.patient_id)                     AS unique_patients,
    ROUND(AVG(a.total_bill), 0)                      AS avg_bill,
    ROUND(SUM(a.total_bill), 0)                      AS total_revenue,
    ROUND(AVG(a.length_of_stay), 1)                  AS avg_los,
    ROUND(SUM(a.readmitted_30days) * 100.0
          / COUNT(*), 1)                             AS readmission_rate_pct,
    SUM(CASE WHEN a.severity = 'Critical' THEN 1 ELSE 0 END) AS critical_cases
FROM admissions a
JOIN patients p ON a.patient_id = p.patient_id
GROUP BY age_group
ORDER BY avg_bill DESC;


-- ─── QUERY 11: Year-over-Year Department Growth ───────────────────────────────
-- Business Question: Which departments grew or shrank year over year?
-- Skills: CTE, PIVOT-style CASE WHEN, YoY calculation

WITH yearly_dept AS (
    SELECT
        department_name,
        SUBSTR(admission_date, 1, 4)                 AS yr,
        ROUND(SUM(total_bill), 0)                    AS revenue
    FROM admissions
    GROUP BY department_name, SUBSTR(admission_date, 1, 4)
)
SELECT
    department_name,
    SUM(CASE WHEN yr = '2021' THEN revenue ELSE 0 END) AS rev_2021,
    SUM(CASE WHEN yr = '2022' THEN revenue ELSE 0 END) AS rev_2022,
    SUM(CASE WHEN yr = '2023' THEN revenue ELSE 0 END) AS rev_2023,
    SUM(CASE WHEN yr = '2024' THEN revenue ELSE 0 END) AS rev_2024,
    ROUND(
        (SUM(CASE WHEN yr='2024' THEN revenue ELSE 0 END) -
         SUM(CASE WHEN yr='2021' THEN revenue ELSE 0 END))
        * 100.0 /
        NULLIF(SUM(CASE WHEN yr='2021' THEN revenue ELSE 0 END), 0),
    1)                                               AS growth_2021_to_2024_pct
FROM yearly_dept
GROUP BY department_name
ORDER BY growth_2021_to_2024_pct DESC;


-- ─── QUERY 12: Top 10% Patients by Spend (Revenue Concentration) ─────────────
-- Business Question: What % of revenue comes from top 10% patients?
-- Skills: NTILE, CTE, Pareto analysis

WITH patient_spend AS (
    SELECT
        patient_id,
        ROUND(SUM(total_bill), 2)                    AS total_spend,
        COUNT(admission_id)                          AS visits
    FROM admissions
    GROUP BY patient_id
),
ranked AS (
    SELECT *,
        NTILE(10) OVER (ORDER BY total_spend DESC)   AS spend_decile
    FROM patient_spend
)
SELECT
    spend_decile,
    COUNT(*)                                         AS patients,
    ROUND(AVG(total_spend), 0)                       AS avg_spend,
    ROUND(SUM(total_spend), 0)                       AS total_revenue,
    ROUND(SUM(total_spend) * 100.0 /
          (SELECT SUM(total_bill) FROM admissions), 2) AS pct_of_total_revenue
FROM ranked
GROUP BY spend_decile
ORDER BY spend_decile;


-- ─── QUERY 13: Diagnosis Frequency + Average Treatment Cost ──────────────────
-- Business Question: Which diagnoses are most common and most expensive?
-- Skills: GROUP BY, RANK, DENSE_RANK

SELECT
    diagnosis,
    department_name,
    COUNT(*)                                         AS cases,
    ROUND(AVG(total_bill), 0)                        AS avg_treatment_cost,
    ROUND(SUM(total_bill), 0)                        AS total_revenue,
    ROUND(AVG(length_of_stay), 1)                    AS avg_los,
    ROUND(SUM(readmitted_30days) * 100.0
          / COUNT(*), 1)                             AS readmission_rate_pct,
    DENSE_RANK() OVER (ORDER BY COUNT(*) DESC)       AS frequency_rank,
    DENSE_RANK() OVER (ORDER BY AVG(total_bill) DESC) AS cost_rank
FROM admissions
GROUP BY diagnosis, department_name
HAVING COUNT(*) >= 15
ORDER BY cases DESC
LIMIT 25;


-- ─── QUERY 14: Staff Efficiency — Revenue per Doctor per Month ───────────────
-- Business Question: Identify high and low performing doctors monthly
-- Skills: Multi-level GROUP BY, window RANK, CTE

WITH monthly_doc AS (
    SELECT
        d.doctor_name,
        d.specialization,
        SUBSTR(a.admission_date, 1, 7)               AS ym,
        COUNT(a.admission_id)                        AS patients,
        ROUND(SUM(a.total_bill), 0)                  AS monthly_revenue
    FROM admissions a
    JOIN doctors d ON a.doctor_id = d.doctor_id
    GROUP BY d.doctor_id, SUBSTR(a.admission_date, 1, 7)
)
SELECT
    doctor_name,
    specialization,
    ROUND(AVG(monthly_revenue), 0)                   AS avg_monthly_revenue,
    ROUND(SUM(monthly_revenue), 0)                   AS total_revenue,
    SUM(patients)                                    AS total_patients,
    COUNT(ym)                                        AS active_months,
    RANK() OVER (PARTITION BY specialization
                 ORDER BY AVG(monthly_revenue) DESC) AS rank_in_dept
FROM monthly_doc
GROUP BY doctor_name, specialization
ORDER BY specialization, rank_in_dept;


-- ─── QUERY 15: Executive KPI Summary (Single Query Dashboard) ────────────────
-- Business Question: Give me all top-level KPIs in one view
-- Skills: Multiple subqueries, scalar aggregations

SELECT
    (SELECT COUNT(DISTINCT patient_id) FROM admissions)         AS total_unique_patients,
    (SELECT COUNT(*) FROM admissions)                           AS total_admissions,
    (SELECT ROUND(SUM(total_bill)/1e7, 2) FROM admissions)      AS total_revenue_crore,
    (SELECT ROUND(AVG(total_bill), 0) FROM admissions)          AS avg_bill_per_admission,
    (SELECT ROUND(AVG(length_of_stay), 1) FROM admissions)      AS avg_length_of_stay,
    (SELECT ROUND(SUM(readmitted_30days)*100.0/COUNT(*),2)
     FROM admissions)                                           AS overall_readmission_rate_pct,
    (SELECT ROUND(SUM(insurance_covered)*100.0/SUM(total_bill),1)
     FROM admissions)                                           AS insurance_coverage_pct,
    (SELECT department_name FROM admissions
     GROUP BY department_name ORDER BY SUM(total_bill) DESC
     LIMIT 1)                                                   AS top_revenue_dept,
    (SELECT COUNT(*) FROM admissions
     WHERE outcome = 'Recovered')                               AS total_recoveries,
    (SELECT ROUND(COUNT(*)*100.0/(SELECT COUNT(*) FROM admissions),1)
     FROM admissions WHERE outcome = 'Recovered')               AS recovery_rate_pct;
