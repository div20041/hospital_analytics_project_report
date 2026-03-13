"""
generate_data.py
Generates a realistic hospital dataset with:
- 5,000 patient records (2021–2024)
- 10 departments, 50 doctors
- Admissions, diagnoses, procedures, billing
- Readmissions, insurance claims
- Staff performance data
"""

import pandas as pd
import numpy as np
import sqlite3, os
from datetime import datetime, timedelta
import random

np.random.seed(42)
random.seed(42)

OUT = "data"
os.makedirs(OUT, exist_ok=True)

# ── Master data ────────────────────────────────────────────────────────────────
DEPARTMENTS = {
    "D01": ("Cardiology",       8500),
    "D02": ("Orthopedics",      6200),
    "D03": ("Oncology",        12000),
    "D04": ("Neurology",        9800),
    "D05": ("General Medicine", 3500),
    "D06": ("Pediatrics",       4200),
    "D07": ("Emergency",        5500),
    "D08": ("Gynecology",       5800),
    "D09": ("Urology",          7100),
    "D10": ("Gastroenterology", 6800),
}

DIAGNOSES = {
    "D01": ["Hypertension","Coronary Artery Disease","Heart Failure","Arrhythmia","Angina"],
    "D02": ["Fracture","Osteoarthritis","Disc Herniation","Joint Replacement","Sports Injury"],
    "D03": ["Lung Cancer","Breast Cancer","Colon Cancer","Lymphoma","Leukemia"],
    "D04": ["Stroke","Epilepsy","Parkinson's Disease","Migraine","Brain Tumor"],
    "D05": ["Diabetes","Typhoid","Pneumonia","Anemia","Hypertension"],
    "D06": ["Dengue","Asthma","Malnutrition","Respiratory Infection","Fever"],
    "D07": ["Trauma","Poisoning","Cardiac Arrest","Road Accident","Burns"],
    "D08": ["PCOS","Pregnancy Complications","Fibroid","Endometriosis","Cervical Cancer"],
    "D09": ["Kidney Stones","UTI","Prostate Cancer","Bladder Infection","Renal Failure"],
    "D10": ["Appendicitis","Liver Cirrhosis","GERD","IBD","Pancreatitis"],
}

INSURANCE = ["Star Health","HDFC ERGO","Niva Bupa","Bajaj Allianz","Arogya Karnataka",
             "CGHS","ESIC","Self-Pay","Ayushman Bharat","New India Assurance"]

CITIES = ["Hyderabad","Bengaluru","Mumbai","Chennai","Delhi",
          "Pune","Kolkata","Ahmedabad","Jaipur","Lucknow"]

BLOOD_GROUPS = ["A+","A-","B+","B-","AB+","AB-","O+","O-"]

def random_date(start, end):
    return start + timedelta(days=random.randint(0, (end-start).days))

START = datetime(2021, 1, 1)
END   = datetime(2024, 12, 31)

# ── Generate doctors ──────────────────────────────────────────────────────────
doctors = []
for dept_id, (dept_name, _) in DEPARTMENTS.items():
    for j in range(5):
        doc_id = f"DOC{dept_id[1:]}{j+1:02d}"
        doctors.append({
            "doctor_id":    doc_id,
            "doctor_name":  f"Dr. {random.choice(['Sharma','Reddy','Patel','Kumar','Singh','Nair','Iyer','Rao','Mehta','Joshi'])} {chr(65+j)}",
            "department_id":dept_id,
            "specialization":dept_name,
            "experience_years": random.randint(3, 25),
            "consultation_fee": random.choice([500, 800, 1000, 1200, 1500, 2000]),
        })
doctors_df = pd.DataFrame(doctors)

# ── Generate patients ─────────────────────────────────────────────────────────
patients = []
for i in range(3000):
    pid = f"PAT{10000+i}"
    age = random.randint(1, 85)
    patients.append({
        "patient_id":   pid,
        "patient_name": f"Patient_{i+1}",
        "age":          age,
        "gender":       random.choice(["Male","Female","Male","Female","Male"]),
        "blood_group":  random.choice(BLOOD_GROUPS),
        "city":         random.choice(CITIES),
        "phone":        f"9{random.randint(100000000,999999999)}",
        "insurance":    random.choice(INSURANCE),
        "registration_date": random_date(START, END).strftime("%Y-%m-%d"),
    })
patients_df = pd.DataFrame(patients)

# ── Generate admissions ───────────────────────────────────────────────────────
admissions = []
adm_id = 1
for i in range(5000):
    pid      = random.choice(patients_df["patient_id"].tolist())
    dept_id  = random.choice(list(DEPARTMENTS.keys()))
    dept_name, base_bill = DEPARTMENTS[dept_id]
    doc      = random.choice(doctors_df[doctors_df["department_id"]==dept_id]["doctor_id"].tolist())
    adm_date = random_date(START, END)
    los      = random.choices([1,2,3,4,5,6,7,10,14,21],
                               weights=[5,15,20,20,15,8,7,5,3,2])[0]
    dis_date = adm_date + timedelta(days=los)
    if dis_date > END: dis_date = END

    bill         = round(base_bill * los * random.uniform(0.7, 1.4), 2)
    insurance_co = random.choice(INSURANCE)
    ins_covered  = round(bill * random.uniform(0, 0.85), 2) if insurance_co != "Self-Pay" else 0
    patient_paid = round(bill - ins_covered, 2)

    severity = random.choices(["Mild","Moderate","Severe","Critical"],
                               weights=[35,40,18,7])[0]

    # Readmission logic: severe/critical patients more likely to return within 30 days
    readmitted_30 = 0
    if severity in ["Severe","Critical"] and random.random() < 0.22:
        readmitted_30 = 1
    elif severity == "Moderate" and random.random() < 0.08:
        readmitted_30 = 1

    admissions.append({
        "admission_id":     f"ADM{adm_id:05d}",
        "patient_id":       pid,
        "doctor_id":        doc,
        "department_id":    dept_id,
        "department_name":  dept_name,
        "diagnosis":        random.choice(DIAGNOSES[dept_id]),
        "admission_date":   adm_date.strftime("%Y-%m-%d"),
        "discharge_date":   dis_date.strftime("%Y-%m-%d"),
        "length_of_stay":   los,
        "severity":         severity,
        "total_bill":       bill,
        "insurance_provider": insurance_co,
        "insurance_covered": ins_covered,
        "patient_paid":     patient_paid,
        "readmitted_30days": readmitted_30,
        "bed_type":         random.choice(["General","Semi-Private","Private","ICU"]),
        "admission_type":   random.choice(["Emergency","Elective","Urgent"]),
        "outcome":          random.choices(["Recovered","Improved","Referred","Expired"],
                                           weights=[65,25,7,3])[0],
    })
    adm_id += 1

admissions_df = pd.DataFrame(admissions)

# ── Generate procedures ───────────────────────────────────────────────────────
PROCEDURES = {
    "D01": [("ECG",1200),("Angiography",18000),("Bypass Surgery",450000),("Stent Placement",85000)],
    "D02": [("X-Ray",800),("MRI",6000),("Knee Replacement",180000),("Physiotherapy",1500)],
    "D03": [("Biopsy",8000),("Chemotherapy",25000),("Radiation",35000),("PET Scan",18000)],
    "D04": [("CT Scan",5000),("EEG",2500),("Brain MRI",9000),("Nerve Conduction",3500)],
    "D05": [("Blood Test",400),("Urine Test",300),("Chest X-Ray",900),("ECG",1200)],
    "D06": [("Vaccination",500),("Blood Test",400),("Nebulization",800),("IV Fluids",1200)],
    "D07": [("Emergency Surgery",120000),("Wound Suturing",3500),("CT Scan",5000),("Blood Transfusion",8000)],
    "D08": [("Ultrasound",1800),("Laparoscopy",35000),("C-Section",65000),("Hysteroscopy",28000)],
    "D09": [("Urine Culture",600),("Kidney Ultrasound",2200),("TURP",55000),("Dialysis",4500)],
    "D10": [("Endoscopy",5500),("Colonoscopy",7000),("Liver Biopsy",12000),("Stool Test",400)],
}

procedures = []
proc_id = 1
for _, adm in admissions_df.sample(frac=0.85).iterrows():
    dept = adm["department_id"]
    proc_list = PROCEDURES.get(dept, [("Consultation",500)])
    n_procs = random.randint(1, 3)
    for proc_name, base_cost in random.sample(proc_list, min(n_procs, len(proc_list))):
        procedures.append({
            "procedure_id":   f"PROC{proc_id:06d}",
            "admission_id":   adm["admission_id"],
            "patient_id":     adm["patient_id"],
            "department_id":  dept,
            "procedure_name": proc_name,
            "procedure_date": adm["admission_date"],
            "cost":           round(base_cost * random.uniform(0.9, 1.2), 2),
            "performed_by":   adm["doctor_id"],
        })
        proc_id += 1
procedures_df = pd.DataFrame(procedures)

# ── Generate monthly revenue summary ─────────────────────────────────────────
admissions_df["admission_date"] = pd.to_datetime(admissions_df["admission_date"])
admissions_df["year_month"] = admissions_df["admission_date"].dt.to_period("M")

monthly = (admissions_df.groupby("year_month")
           .agg(total_revenue=("total_bill","sum"),
                total_admissions=("admission_id","count"),
                avg_los=("length_of_stay","mean"),
                readmissions=("readmitted_30days","sum"))
           .reset_index())
monthly["year_month"] = monthly["year_month"].astype(str)
monthly["total_revenue"] = monthly["total_revenue"].round(2)
monthly["avg_los"]       = monthly["avg_los"].round(2)

# ── Save all to CSV + SQLite ───────────────────────────────────────────────────
patients_df.to_csv(f"{OUT}/patients.csv",    index=False)
doctors_df.to_csv(f"{OUT}/doctors.csv",      index=False)
admissions_df["year_month"] = admissions_df["year_month"].astype(str)
admissions_df["admission_date"] = admissions_df["admission_date"].astype(str)
admissions_df.to_csv(f"{OUT}/admissions.csv",index=False)
procedures_df.to_csv(f"{OUT}/procedures.csv",index=False)
monthly.to_csv(f"{OUT}/monthly_revenue.csv", index=False)

# SQLite database
conn = sqlite3.connect(f"{OUT}/hospital.db")
patients_df.to_sql("patients",    conn, if_exists="replace", index=False)
doctors_df.to_sql("doctors",      conn, if_exists="replace", index=False)
admissions_df.to_sql("admissions",conn, if_exists="replace", index=False)
procedures_df.to_sql("procedures",conn, if_exists="replace", index=False)
monthly.to_sql("monthly_revenue", conn, if_exists="replace", index=False)
conn.close()

print("✓ Dataset generated:")
print(f"  Patients   : {len(patients_df):,}")
print(f"  Doctors    : {len(doctors_df):,}")
print(f"  Admissions : {len(admissions_df):,}")
print(f"  Procedures : {len(procedures_df):,}")
print(f"  Revenue    : ₹{admissions_df['total_bill'].sum()/1e7:.2f} Crore total")
print(f"  Saved to   : {OUT}/hospital.db + CSVs")
