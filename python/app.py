"""
app.py
Flask backend — connects to MySQL and serves live data to dashboard.

Run:  python app.py
Open: http://localhost:5000
"""

from flask import Flask, jsonify
from flask_cors import CORS
import mysql.connector
import pandas as pd

app = Flask(__name__)
CORS(app)

# ── MySQL Connection ───────────────────────────────────────────────────────────
DB_CONFIG = {
    "host":     "localhost",
    "user":     "root",
    "password": "MYSQL",
    "database": "hospital_analytics"
}

def query(sql):
    conn = mysql.connector.connect(**DB_CONFIG)
    df   = pd.read_sql(sql, conn)
    conn.close()
    return df

# ── API ENDPOINTS ──────────────────────────────────────────────────────────────

@app.route("/api/kpis")
def kpis():
    df = query("""
        SELECT
            ROUND(SUM(total_bill)/1e7, 2)                        AS total_revenue_crore,
            COUNT(*)                                              AS total_admissions,
            COUNT(DISTINCT patient_id)                            AS unique_patients,
            ROUND(AVG(total_bill), 0)                             AS avg_bill,
            ROUND(AVG(length_of_stay), 1)                         AS avg_los,
            ROUND(SUM(readmitted_30days)*100.0/COUNT(*), 1)       AS readmission_rate,
            ROUND(SUM(insurance_covered)*100.0/SUM(total_bill),1) AS insurance_pct,
            ROUND(SUM(CASE WHEN outcome='Recovered' THEN 1 ELSE 0 END)*100.0/COUNT(*),1) AS recovery_rate
        FROM admissions
    """)
    return jsonify(df.to_dict(orient="records")[0])

@app.route("/api/monthly")
def monthly():
    df = query("""
        SELECT
            DATE_FORMAT(admission_date, '%Y-%m') AS ym,
            COUNT(*)                             AS admissions,
            ROUND(SUM(total_bill), 0)            AS revenue
        FROM admissions
        GROUP BY DATE_FORMAT(admission_date, '%Y-%m')
        ORDER BY ym
    """)
    return jsonify(df.to_dict(orient="records"))

@app.route("/api/departments")
def departments():
    df = query("""
        SELECT
            department_name,
            COUNT(*)                                              AS admissions,
            ROUND(SUM(total_bill), 0)                             AS revenue,
            ROUND(AVG(total_bill), 0)                             AS avg_bill,
            ROUND(AVG(length_of_stay), 1)                         AS avg_los,
            ROUND(SUM(readmitted_30days)*100.0/COUNT(*), 1)       AS readmission_rate,
            ROUND(SUM(CASE WHEN outcome='Recovered' THEN 1 ELSE 0 END)*100.0/COUNT(*),1) AS recovery_rate
        FROM admissions
        GROUP BY department_name
        ORDER BY revenue DESC
    """)
    return jsonify(df.to_dict(orient="records"))

@app.route("/api/yoy")
def yoy():
    df = query("""
        SELECT
            YEAR(admission_date)      AS year,
            COUNT(*)                  AS admissions,
            ROUND(SUM(total_bill), 0) AS revenue
        FROM admissions
        GROUP BY YEAR(admission_date)
        ORDER BY year
    """)
    return jsonify(df.to_dict(orient="records"))

@app.route("/api/severity")
def severity():
    df = query("""
        SELECT severity, COUNT(*) AS total
        FROM admissions
        GROUP BY severity
        ORDER BY total DESC
    """)
    return jsonify(df.to_dict(orient="records"))

@app.route("/api/outcomes")
def outcomes():
    df = query("""
        SELECT outcome, COUNT(*) AS total
        FROM admissions
        GROUP BY outcome
        ORDER BY total DESC
    """)
    return jsonify(df.to_dict(orient="records"))

@app.route("/api/insurance")
def insurance():
    df = query("""
        SELECT
            insurance_provider,
            COUNT(*)                        AS claims,
            ROUND(SUM(total_bill), 0)       AS billed,
            ROUND(SUM(insurance_covered),0) AS covered,
            ROUND(SUM(patient_paid), 0)     AS patient_paid
        FROM admissions
        GROUP BY insurance_provider
        ORDER BY billed DESC
        LIMIT 8
    """)
    return jsonify(df.to_dict(orient="records"))

@app.route("/api/doctors")
def doctors():
    df = query("""
        SELECT
            d.doctor_name,
            d.specialization,
            d.experience_years,
            COUNT(a.admission_id)          AS patients,
            ROUND(SUM(a.total_bill), 0)    AS revenue,
            ROUND(AVG(a.total_bill), 0)    AS avg_bill,
            ROUND(SUM(CASE WHEN a.outcome='Recovered' THEN 1 ELSE 0 END)*100.0/COUNT(*),1) AS recovery_rate,
            SUM(a.readmitted_30days)       AS readmissions
        FROM doctors d
        LEFT JOIN admissions a ON d.doctor_id = a.doctor_id
        GROUP BY d.doctor_id, d.doctor_name, d.specialization, d.experience_years
        ORDER BY revenue DESC
        LIMIT 10
    """)
    return jsonify(df.to_dict(orient="records"))

@app.route("/api/readmission_heatmap")
def readmission_heatmap():
    df = query("""
        SELECT
            department_name,
            severity,
            ROUND(SUM(readmitted_30days)*100.0/COUNT(*), 0) AS readmission_rate
        FROM admissions
        GROUP BY department_name, severity
        ORDER BY department_name, severity
    """)
    return jsonify(df.to_dict(orient="records"))

@app.route("/api/bed_types")
def bed_types():
    df = query("""
        SELECT bed_type, COUNT(*) AS total
        FROM admissions
        GROUP BY bed_type
        ORDER BY total DESC
    """)
    return jsonify(df.to_dict(orient="records"))

# ── Serve dashboard HTML ───────────────────────────────────────────────────────
@app.route("/")
def dashboard():
    try:
        with open("Hospital_Analytics_Dashboard_Live.html", "r", encoding="utf-8") as f:
            return f.read()
    except:
        return "<h2>Place Hospital_Analytics_Dashboard_Live.html in the same folder as app.py</h2>"

if __name__ == "__main__":
    print("="*50)
    print("  Hospital Analytics — Live MySQL Dashboard")
    print("  Database : hospital_analytics @ localhost")
    print("  Open     : http://localhost:5000")
    print("="*50)
    app.run(debug=True, port=5000)
