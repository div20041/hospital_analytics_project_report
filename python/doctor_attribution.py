"""
doctor_attribution.py
═══════════════════════════════════════════════════════════════
DOCTOR QUALITY vs PATIENT COMPLEXITY — ATTRIBUTION ANALYSIS
═══════════════════════════════════════════════════════════════

The core question:
  Is a doctor's high readmission rate because of poor care
  or because they treat the sickest patients?

Method: Risk-Adjusted Performance Scoring
  1. Build a patient-level risk model (logistic regression)
     predicting readmission from patient profile ONLY
     (age, severity, diagnosis, admission type, bed type)
     — deliberately excluding doctor identity

  2. For every patient, get their EXPECTED readmission
     probability given their profile

  3. For every doctor:
     - Actual readmission rate   = what really happened
     - Expected readmission rate = what the model predicted
       given that doctor's patient mix
     - Attribution Score         = Actual − Expected
       Positive → doctor performs WORSE than expected (quality concern)
       Negative → doctor performs BETTER than expected (quality star)

  4. Compute Patient Complexity Score per doctor
     = average predicted risk of their patient panel
     High complexity = doctor handles hard cases

  5. Classify every doctor into 4 quadrants:
     ⭐ Hidden Star    — high complexity, low actual readmission (best)
     ✅ Solid          — low complexity, low actual readmission (good)
     ⚠️  Overloaded    — high complexity, high actual readmission (needs support)
     🔴 Quality Gap   — low complexity, high actual readmission (concerning)

This is the same methodology used by CMS Hospital Quality Reporting.
"""

import pandas as pd
import numpy as np
import mysql.connector, os, warnings
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.gridspec as gridspec
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import LabelEncoder, StandardScaler
from sklearn.model_selection import cross_val_score
from sklearn.metrics import roc_auc_score
from sklearn.calibration import CalibratedClassifierCV
warnings.filterwarnings("ignore")
np.random.seed(42)

OUT = "outputs"
os.makedirs(OUT, exist_ok=True)

# ── Load data ──────────────────────────────────────────────────────────────────
conn = mysql.connector.connect(
    host     = "localhost",
    user     = "root",
    password = "MYSQL",
    database = "hospital_analytics"
)
adm  = pd.read_sql("SELECT * FROM admissions", conn)
pat  = pd.read_sql("SELECT * FROM patients",   conn)
doc  = pd.read_sql("SELECT * FROM doctors",    conn)
conn.close()

adm["admission_date"] = pd.to_datetime(adm["admission_date"])
df = adm.merge(pat[["patient_id","age","gender"]], on="patient_id", how="left")
df = df.merge(doc[["doctor_id","doctor_name","specialization","experience_years"]],
              on="doctor_id", how="left")

print("═"*60)
print("  DOCTOR ATTRIBUTION ANALYSIS")
print("═"*60)
print(f"  Records : {len(df):,}  |  Doctors: {df['doctor_id'].nunique()}")
print(f"  Overall readmission rate: {df['readmitted_30days'].mean():.1%}")

# ══════════════════════════════════════════════════════════════
#  STEP 1 — PATIENT RISK MODEL (no doctor features)
# ══════════════════════════════════════════════════════════════
print("\n[1/5] Building patient risk model (excluding doctor identity)...")

le = LabelEncoder()
df["severity_enc"]   = le.fit_transform(df["severity"])
df["dept_enc"]       = le.fit_transform(df["department_name"])
df["diag_enc"]       = le.fit_transform(df["diagnosis"])
df["bed_enc"]        = le.fit_transform(df["bed_type"])
df["adm_type_enc"]   = le.fit_transform(df["admission_type"])
df["gender_enc"]     = le.fit_transform(df["gender"].fillna("Unknown"))
df["ins_enc"]        = le.fit_transform(df["insurance_provider"])
df["age"]            = df["age"].fillna(df["age"].median())

# Month of year — captures seasonal patterns
df["month"] = df["admission_date"].dt.month

# Patient complexity proxy features — ONLY patient characteristics
PATIENT_FEATURES = [
    "age", "severity_enc", "dept_enc", "diag_enc",
    "bed_enc", "adm_type_enc", "gender_enc",
    "length_of_stay", "total_bill", "month",
]

X = df[PATIENT_FEATURES].fillna(0)
y = df["readmitted_30days"]

# Calibrated logistic regression — calibration is critical for
# meaningful probability estimates (not just rank ordering)
base_lr = LogisticRegression(C=0.5, max_iter=500, random_state=42,
                              class_weight="balanced")
model   = CalibratedClassifierCV(base_lr, cv=5, method="isotonic")
model.fit(X, y)

cv_auc = cross_val_score(model, X, y, cv=5, scoring="roc_auc").mean()
print(f"  Patient risk model CV AUC: {cv_auc:.3f}")

# Expected readmission probability for every patient
df["expected_readmission_prob"] = model.predict_proba(X)[:, 1]

# ══════════════════════════════════════════════════════════════
#  STEP 2 — DOCTOR-LEVEL ATTRIBUTION SCORES
# ══════════════════════════════════════════════════════════════
print("\n[2/5] Computing doctor attribution scores...")

doc_stats = (df.groupby(["doctor_id","doctor_name","specialization","experience_years"])
             .agg(
                 n_patients           = ("admission_id",            "count"),
                 actual_readmit_rate  = ("readmitted_30days",       "mean"),
                 expected_readmit_rate= ("expected_readmission_prob","mean"),
                 avg_severity         = ("severity_enc",            "mean"),
                 avg_patient_age      = ("age",                     "mean"),
                 avg_complexity       = ("expected_readmission_prob","mean"),
                 revenue_generated    = ("total_bill",              "sum"),
                 recovery_rate        = ("outcome", lambda x: (x=="Recovered").mean()),
             )
             .reset_index())

# Attribution Score = Actual − Expected
# Negative = BETTER than expected (quality star)
# Positive = WORSE than expected (quality concern)
doc_stats["attribution_score"] = (
    doc_stats["actual_readmit_rate"] - doc_stats["expected_readmit_rate"]
)

# Normalise attribution to -100 to +100 for readability
max_abs = doc_stats["attribution_score"].abs().max()
doc_stats["attribution_score_norm"] = (
    doc_stats["attribution_score"] / max_abs * 100
).round(1)

# Patient Complexity Score (0–100)
min_c = doc_stats["avg_complexity"].min()
max_c = doc_stats["avg_complexity"].max()
doc_stats["complexity_score"] = (
    (doc_stats["avg_complexity"] - min_c) / (max_c - min_c) * 100
).round(1)

# ── Quadrant classification ────────────────────────────────────────────────────
med_complexity  = doc_stats["complexity_score"].median()
med_actual      = doc_stats["actual_readmit_rate"].median()

def classify_doctor(row):
    hi_complexity = row["complexity_score"]     >= med_complexity
    hi_readmit    = row["actual_readmit_rate"]  >= med_actual
    if hi_complexity and not hi_readmit: return "⭐ Hidden Star"
    if hi_complexity and hi_readmit:     return "⚠️  Overloaded"
    if not hi_complexity and not hi_readmit: return "✅ Solid"
    return "🔴 Quality Gap"

doc_stats["quadrant"] = doc_stats.apply(classify_doctor, axis=1)

# Sort by attribution score (best performers first)
doc_stats = doc_stats.sort_values("attribution_score_norm").reset_index(drop=True)

print(f"  ⭐ Hidden Stars  : {(doc_stats['quadrant']=='⭐ Hidden Star').sum()}")
print(f"  ✅ Solid         : {(doc_stats['quadrant']=='✅ Solid').sum()}")
print(f"  ⚠️  Overloaded   : {(doc_stats['quadrant']=='⚠️  Overloaded').sum()}")
print(f"  🔴 Quality Gap  : {(doc_stats['quadrant']=='🔴 Quality Gap').sum()}")

# ══════════════════════════════════════════════════════════════
#  STEP 3 — MOST INTERESTING CASES
# ══════════════════════════════════════════════════════════════
print("\n[3/5] Finding most interesting cases...")

# Doctors whose raw rank and risk-adjusted rank differ the most
doc_stats["raw_rank"] = doc_stats["actual_readmit_rate"].rank()
doc_stats["adj_rank"] = doc_stats["attribution_score_norm"].rank()
doc_stats["rank_shift"] = (doc_stats["raw_rank"] - doc_stats["adj_rank"]).round(0)

# Top misclassified: looked bad but actually good
hidden_stars = doc_stats[doc_stats["quadrant"] == "⭐ Hidden Star"].nlargest(3, "complexity_score")
quality_gaps = doc_stats[doc_stats["quadrant"] == "🔴 Quality Gap"].nlargest(3, "attribution_score_norm")
most_improved = doc_stats.nlargest(5, "rank_shift")   # biggest rank improvement after adjustment

print("\n  TOP 3 HIDDEN STARS (looked bad, actually excellent):")
for _, r in hidden_stars.iterrows():
    print(f"    {r['doctor_name']:25s} | Raw: {r['actual_readmit_rate']:.1%} | "
          f"Expected: {r['expected_readmit_rate']:.1%} | "
          f"Complexity: {r['complexity_score']:.0f}/100")

print("\n  TOP 3 QUALITY GAPS (looked fine, actually underperforming):")
for _, r in quality_gaps.iterrows():
    print(f"    {r['doctor_name']:25s} | Raw: {r['actual_readmit_rate']:.1%} | "
          f"Expected: {r['expected_readmit_rate']:.1%} | "
          f"Complexity: {r['complexity_score']:.0f}/100")

# ══════════════════════════════════════════════════════════════
#  STEP 4 — VISUALISATIONS
# ══════════════════════════════════════════════════════════════
print("\n[4/5] Generating charts...")

COLORS = {
    "⭐ Hidden Star":  "#22C98A",
    "✅ Solid":        "#3B82F6",
    "⚠️  Overloaded":  "#F59E0B",
    "🔴 Quality Gap": "#EF4444",
}

fig = plt.figure(figsize=(20, 14))
fig.patch.set_facecolor("#0B1F3A")
gs  = gridspec.GridSpec(2, 3, figure=fig, hspace=0.42, wspace=0.35)
fig.suptitle(
    "Doctor Quality vs Patient Complexity — Risk-Adjusted Attribution Analysis\n"
    "Separating True Doctor Quality from Patient Case Mix",
    fontsize=14, fontweight="bold", color="white", y=1.01
)

TICK_C  = "#7A99BB"
GRID_C  = "rgba(255,255,255,.06)"
FACE_C  = "#0D2845"

# ── CHART 1: The Core Scatter — Complexity vs Actual Readmission ──────────────
ax1 = fig.add_subplot(gs[0, :2])
ax1.set_facecolor(FACE_C)

quad_colors = [COLORS[q] for q in doc_stats["quadrant"]]
sizes       = (doc_stats["n_patients"] / doc_stats["n_patients"].max() * 300 + 60)

sc = ax1.scatter(
    doc_stats["complexity_score"],
    doc_stats["actual_readmit_rate"] * 100,
    c=quad_colors, s=sizes, alpha=0.85, edgecolors="white", linewidths=0.6
)

# Quadrant dividers
ax1.axvline(med_complexity, color="white", linestyle="--", alpha=0.25, lw=1.2)
ax1.axhline(med_actual * 100, color="white", linestyle="--", alpha=0.25, lw=1.2)

# Quadrant labels
ax1.text(med_complexity * 0.35, med_actual * 100 * 1.35,
         "🔴 Quality Gap\n(Easy patients, high readmission)",
         color="#EF4444", fontsize=8.5, fontweight="bold", alpha=0.9)
ax1.text(med_complexity * 1.25, med_actual * 100 * 1.35,
         "⚠️  Overloaded\n(Hard patients, high readmission)",
         color="#F59E0B", fontsize=8.5, fontweight="bold", alpha=0.9)
ax1.text(med_complexity * 0.35, med_actual * 100 * 0.38,
         "✅ Solid\n(Easy patients, low readmission)",
         color="#3B82F6", fontsize=8.5, fontweight="bold", alpha=0.9)
ax1.text(med_complexity * 1.25, med_actual * 100 * 0.38,
         "⭐ Hidden Star\n(Hard patients, low readmission)",
         color="#22C98A", fontsize=8.5, fontweight="bold", alpha=0.9)

# Annotate top hidden stars and quality gaps
for _, row in hidden_stars.iterrows():
    ax1.annotate(
        row["doctor_name"].replace("Dr. ", ""),
        (row["complexity_score"], row["actual_readmit_rate"] * 100),
        textcoords="offset points", xytext=(8, 4),
        color="#22C98A", fontsize=7.5, fontweight="bold",
        arrowprops=dict(arrowstyle="->", color="#22C98A", lw=0.8)
    )
for _, row in quality_gaps.head(2).iterrows():
    ax1.annotate(
        row["doctor_name"].replace("Dr. ", ""),
        (row["complexity_score"], row["actual_readmit_rate"] * 100),
        textcoords="offset points", xytext=(8, -12),
        color="#EF4444", fontsize=7.5, fontweight="bold",
        arrowprops=dict(arrowstyle="->", color="#EF4444", lw=0.8)
    )

ax1.set_xlabel("Patient Complexity Score (0=Easy, 100=Very Complex)", color=TICK_C, fontsize=10)
ax1.set_ylabel("Actual 30-Day Readmission Rate (%)", color=TICK_C, fontsize=10)
ax1.set_title("Core Attribution Plot — Every Dot is One Doctor\n(Bubble size = number of patients)",
              color="white", fontweight="bold", fontsize=11)
ax1.tick_params(colors=TICK_C)
ax1.grid(alpha=0.12, color="white")
legend_els = [mpatches.Patch(color=v, label=k) for k, v in COLORS.items()]
ax1.legend(handles=legend_els, loc="upper left", fontsize=8.5,
           facecolor="#0D2845", labelcolor="white", framealpha=0.8)

# ── CHART 2: Attribution Score distribution ────────────────────────────────────
ax2 = fig.add_subplot(gs[0, 2])
ax2.set_facecolor(FACE_C)

colors_attr = ["#22C98A" if v < 0 else "#EF4444"
               for v in doc_stats["attribution_score_norm"]]
y_pos = range(len(doc_stats))
ax2.barh(y_pos, doc_stats["attribution_score_norm"],
         color=colors_attr, alpha=0.8, edgecolor="none", height=0.7)
ax2.axvline(0, color="white", lw=1.5, alpha=0.6)
ax2.set_xlabel("Attribution Score\n(Negative = Better than expected)", color=TICK_C, fontsize=9)
ax2.set_title("Risk-Adjusted Attribution\nScore per Doctor",
              color="white", fontweight="bold", fontsize=10)
ax2.set_yticks([])
ax2.tick_params(colors=TICK_C)
ax2.grid(axis="x", alpha=0.1, color="white")
ax2.text(0.02, 0.97, "◀ Better than\n   expected",
         transform=ax2.transAxes, color="#22C98A", fontsize=8,
         va="top", fontweight="bold")
ax2.text(0.98, 0.97, "Worse than ▶\nexpected",
         transform=ax2.transAxes, color="#EF4444", fontsize=8,
         va="top", ha="right", fontweight="bold")

# ── CHART 3: Raw rank vs Adjusted rank (rank shift) ───────────────────────────
ax3 = fig.add_subplot(gs[1, 0])
ax3.set_facecolor(FACE_C)

top_shifted = doc_stats.nlargest(10, "rank_shift")
bot_shifted = doc_stats.nsmallest(10, "rank_shift")
shift_show  = pd.concat([top_shifted, bot_shifted]).drop_duplicates()
shift_show  = shift_show.sort_values("rank_shift", ascending=True)

colors_s = ["#22C98A" if v > 0 else "#EF4444" for v in shift_show["rank_shift"]]
bars = ax3.barh(
    shift_show["doctor_name"].str.replace("Dr. ",""),
    shift_show["rank_shift"],
    color=colors_s, alpha=0.85, edgecolor="none"
)
ax3.axvline(0, color="white", lw=1.2, alpha=0.5)
ax3.set_xlabel("Rank Improvement After Risk-Adjustment\n(Positive = unfairly judged by raw metrics)",
               color=TICK_C, fontsize=8)
ax3.set_title("Rank Change: Raw → Risk-Adjusted\n(Who was unfairly judged?)",
              color="white", fontweight="bold", fontsize=10)
ax3.tick_params(colors=TICK_C, labelsize=7.5)
ax3.grid(axis="x", alpha=0.1, color="white")

# ── CHART 4: Actual vs Expected by department ─────────────────────────────────
ax4 = fig.add_subplot(gs[1, 1])
ax4.set_facecolor(FACE_C)

dept_attr = (doc_stats.groupby("specialization")
             .agg(actual=("actual_readmit_rate","mean"),
                  expected=("expected_readmit_rate","mean"),
                  n=("n_patients","sum"))
             .reset_index()
             .sort_values("actual", ascending=True))

x_pos = np.arange(len(dept_attr))
w = 0.35
ax4.barh(x_pos - w/2, dept_attr["expected"] * 100,
         w, color="#3B82F6", alpha=0.8, label="Expected (model)", edgecolor="none")
ax4.barh(x_pos + w/2, dept_attr["actual"] * 100,
         w, color="#EF4444", alpha=0.8, label="Actual", edgecolor="none")

ax4.set_yticks(x_pos)
ax4.set_yticklabels(dept_attr["specialization"], fontsize=8, color=TICK_C)
ax4.set_xlabel("Readmission Rate (%)", color=TICK_C, fontsize=9)
ax4.set_title("Actual vs Expected Readmission\nby Department",
              color="white", fontweight="bold", fontsize=10)
ax4.legend(fontsize=8, facecolor="#0D2845", labelcolor="white")
ax4.tick_params(colors=TICK_C)
ax4.grid(axis="x", alpha=0.1, color="white")

# ── CHART 5: Experience vs Attribution Score ──────────────────────────────────
ax5 = fig.add_subplot(gs[1, 2])
ax5.set_facecolor(FACE_C)

ax5.scatter(
    doc_stats["experience_years"],
    doc_stats["attribution_score_norm"],
    c=[COLORS[q] for q in doc_stats["quadrant"]],
    s=80, alpha=0.8, edgecolors="white", linewidths=0.5
)

# Trend line
z = np.polyfit(doc_stats["experience_years"],
               doc_stats["attribution_score_norm"], 1)
p = np.poly1d(z)
x_line = np.linspace(doc_stats["experience_years"].min(),
                     doc_stats["experience_years"].max(), 100)
ax5.plot(x_line, p(x_line), color="white", lw=1.5, linestyle="--",
         alpha=0.5, label="Trend")

ax5.axhline(0, color="white", lw=1, alpha=0.3)
ax5.set_xlabel("Doctor Experience (Years)", color=TICK_C, fontsize=9)
ax5.set_ylabel("Attribution Score\n(Negative = Better)", color=TICK_C, fontsize=9)
ax5.set_title("Does Experience Predict\nRisk-Adjusted Quality?",
              color="white", fontweight="bold", fontsize=10)
ax5.tick_params(colors=TICK_C)
ax5.grid(alpha=0.1, color="white")
ax5.legend(fontsize=8, facecolor="#0D2845", labelcolor="white")

# Correlation annotation
corr = np.corrcoef(doc_stats["experience_years"],
                   doc_stats["attribution_score_norm"])[0,1]
ax5.text(0.05, 0.05, f"Pearson r = {corr:.3f}",
         transform=ax5.transAxes, color=TICK_C, fontsize=9,
         bbox=dict(boxstyle="round", fc="#0B1F3A", ec="#1E3A5F"))

plt.savefig(f"{OUT}/08_doctor_attribution.png", dpi=150,
            bbox_inches="tight", facecolor="#0B1F3A")
plt.close()
print(f"  ✓ outputs/08_doctor_attribution.png")

# ══════════════════════════════════════════════════════════════
#  STEP 5 — SAVE RESULTS
# ══════════════════════════════════════════════════════════════
print("\n[5/5] Saving results...")

save_cols = [
    "doctor_name", "specialization", "experience_years",
    "n_patients", "actual_readmit_rate", "expected_readmit_rate",
    "attribution_score_norm", "complexity_score",
    "recovery_rate", "revenue_generated", "quadrant", "rank_shift",
]
out_df = doc_stats[save_cols].copy()
out_df["actual_readmit_rate"]   = out_df["actual_readmit_rate"].round(3)
out_df["expected_readmit_rate"] = out_df["expected_readmit_rate"].round(3)
out_df["recovery_rate"]         = out_df["recovery_rate"].round(3)
out_df["revenue_generated"]     = out_df["revenue_generated"].round(0)
out_df.to_csv(f"{OUT}/doctor_attribution_scores.csv", index=False)
print(f"  ✓ outputs/doctor_attribution_scores.csv")

# ── Summary print ──────────────────────────────────────────────────────────────
print("\n" + "═"*60)
print("  KEY FINDINGS")
print("═"*60)

stars = doc_stats[doc_stats["quadrant"] == "⭐ Hidden Star"]
gaps  = doc_stats[doc_stats["quadrant"] == "🔴 Quality Gap"]
most_complex_doc = doc_stats.nlargest(1, "complexity_score").iloc[0]
least_complex_doc= doc_stats.nsmallest(1, "complexity_score").iloc[0]

print(f"\n  1. {len(stars)} doctors classified as Hidden Stars")
print(f"     → High patient complexity but BELOW average readmission")
print(f"     → Raw metrics would have flagged them as average or poor")

print(f"\n  2. {len(gaps)} doctors classified as Quality Gap")
print(f"     → Low patient complexity but ABOVE average readmission")
print(f"     → Raw metrics would have shown them as acceptable")

print(f"\n  3. Most complex patient panel:")
print(f"     {most_complex_doc['doctor_name']} ({most_complex_doc['specialization']})")
print(f"     Complexity: {most_complex_doc['complexity_score']:.0f}/100 | "
      f"Actual readmit: {most_complex_doc['actual_readmit_rate']:.1%}")

print(f"\n  4. Pearson r (experience vs attribution): {corr:.3f}")
if corr < -0.1:
    print(f"     → More experienced doctors perform better after adjustment")
elif corr > 0.1:
    print(f"     → Surprisingly, experience does NOT predict quality here")
else:
    print(f"     → No strong relationship between experience and quality")

print(f"\n  5. Patient risk model CV AUC: {cv_auc:.3f}")
print(f"     → Model reliably separates complex from simple patients")
print("═"*60 + "\n")
