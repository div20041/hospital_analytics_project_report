"""
python_analysis.py
Full Python analysis layer:
  1. EDA with rich visualizations
  2. Readmission prediction (Random Forest + feature importance)
  3. Patient segmentation (K-Means clustering)
  4. Revenue forecasting (rolling trend)
  5. Department KPI heatmap
"""

import pandas as pd
import numpy as np
import mysql.connector, os, warnings
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
from matplotlib.ticker import FuncFormatter
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.cluster import KMeans
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.metrics import classification_report, roc_auc_score, confusion_matrix
from sklearn.preprocessing import StandardScaler, LabelEncoder
warnings.filterwarnings("ignore")
np.random.seed(42)

OUT = "outputs"
os.makedirs(OUT, exist_ok=True)

# ── Load data ─────────────────────────────────────────────────────────────────
conn = mysql.connector.connect(
    host     = "localhost",
    user     = "root",
    password = "MYSQL",
    database = "hospital_analytics"
)
admissions = pd.read_sql("SELECT * FROM admissions", conn)
patients   = pd.read_sql("SELECT * FROM patients",   conn)
doctors    = pd.read_sql("SELECT * FROM doctors",     conn)
procedures = pd.read_sql("SELECT * FROM procedures",  conn)
conn.close()

admissions["admission_date"] = pd.to_datetime(admissions["admission_date"])
admissions["discharge_date"] = pd.to_datetime(admissions["discharge_date"])
admissions["year"]  = admissions["admission_date"].dt.year
admissions["month"] = admissions["admission_date"].dt.month
admissions["ym"]    = admissions["admission_date"].dt.to_period("M")

COLORS = {"primary":"#0D3B6E","teal":"#0E7490","green":"#16A34A",
          "red":"#DC2626","orange":"#D97706","purple":"#7C3AED",
          "light":"#F0F9FF","grey":"#64748B"}

def crore_fmt(x, _): return f"₹{x/1e7:.1f}Cr"
def lakh_fmt(x, _):  return f"₹{x/1e5:.0f}L"

# ════════════════════════════════════════════════════════
#  CHART 1 — Executive KPI Overview
# ════════════════════════════════════════════════════════
def plot_executive_kpis():
    fig = plt.figure(figsize=(18, 10))
    fig.patch.set_facecolor("#0A1628")
    gs = gridspec.GridSpec(2, 4, figure=fig, hspace=0.45, wspace=0.35)
    fig.suptitle("🏥  Hospital Revenue & Patient Analytics — Executive Dashboard",
                 fontsize=16, fontweight="bold", color="white", y=1.01)

    kpis = [
        ("Total Revenue",    f"₹{admissions['total_bill'].sum()/1e7:.2f} Cr", COLORS["teal"]),
        ("Total Admissions", f"{len(admissions):,}",                         COLORS["green"]),
        ("Unique Patients",  f"{admissions['patient_id'].nunique():,}",       COLORS["orange"]),
        ("Avg Bill/Patient", f"₹{admissions['total_bill'].mean():,.0f}",      COLORS["purple"]),
        ("Avg LOS (days)",   f"{admissions['length_of_stay'].mean():.1f}",    COLORS["teal"]),
        ("Readmission Rate", f"{admissions['readmitted_30days'].mean()*100:.1f}%", COLORS["red"]),
        ("Insurance Cover%", f"{admissions['insurance_covered'].sum()/admissions['total_bill'].sum()*100:.1f}%", COLORS["green"]),
        ("Recovery Rate",    f"{(admissions['outcome']=='Recovered').mean()*100:.1f}%", COLORS["orange"]),
    ]

    for i, (label, value, color) in enumerate(kpis):
        ax = fig.add_subplot(gs[i // 4, i % 4])
        ax.set_facecolor("#0D2137")
        ax.set_xlim(0, 1); ax.set_ylim(0, 1); ax.axis("off")
        ax.add_patch(plt.Rectangle((0.05,0.05), 0.9, 0.9,
                     fill=True, color=color, alpha=0.15, transform=ax.transData))
        ax.text(0.5, 0.62, value, transform=ax.transAxes,
                ha="center", va="center", fontsize=22, fontweight="bold", color=color)
        ax.text(0.5, 0.28, label, transform=ax.transAxes,
                ha="center", va="center", fontsize=11, color="#94A3B8")

    plt.tight_layout()
    plt.savefig(f"{OUT}/01_executive_kpis.png", dpi=150, bbox_inches="tight",
                facecolor="#0A1628")
    plt.close()
    print("  ✓ 01_executive_kpis.png")

# ════════════════════════════════════════════════════════
#  CHART 2 — Revenue Trend + MoM Growth
# ════════════════════════════════════════════════════════
def plot_revenue_trend():
    monthly = (admissions.groupby("ym")
               .agg(revenue=("total_bill","sum"), admissions=("admission_id","count"))
               .reset_index())
    monthly["ym_str"] = monthly["ym"].astype(str)
    monthly["mom_growth"] = monthly["revenue"].pct_change() * 100

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(16, 9), sharex=True,
                                    gridspec_kw={"height_ratios":[2,1]})
    fig.patch.set_facecolor("#FAFAFA")
    fig.suptitle("Monthly Revenue Trend & Month-over-Month Growth",
                 fontsize=14, fontweight="bold", color=COLORS["primary"])

    ax1.set_facecolor("#F0F9FF")
    ax1.fill_between(range(len(monthly)), monthly["revenue"],
                     alpha=0.3, color=COLORS["teal"])
    ax1.plot(range(len(monthly)), monthly["revenue"],
             color=COLORS["teal"], lw=2.5, marker="o", markersize=4)
    ax1.yaxis.set_major_formatter(FuncFormatter(lakh_fmt))
    ax1.set_ylabel("Monthly Revenue", fontsize=11); ax1.grid(axis="y", alpha=0.4)

    # Add trend line
    z = np.polyfit(range(len(monthly)), monthly["revenue"], 1)
    p = np.poly1d(z)
    ax1.plot(range(len(monthly)), p(range(len(monthly))),
             "r--", alpha=0.6, lw=1.5, label="Trend line")
    ax1.legend()

    ax2.set_facecolor("#F0F9FF")
    colors_mom = [COLORS["green"] if x >= 0 else COLORS["red"]
                  for x in monthly["mom_growth"].fillna(0)]
    ax2.bar(range(len(monthly)), monthly["mom_growth"].fillna(0),
            color=colors_mom, alpha=0.8, edgecolor="white")
    ax2.axhline(0, color="black", lw=0.8)
    ax2.set_ylabel("MoM Growth %", fontsize=10)
    ax2.set_xticks(range(0, len(monthly), 3))
    ax2.set_xticklabels(monthly["ym_str"].iloc[::3], rotation=45, ha="right", fontsize=8)
    ax2.grid(axis="y", alpha=0.3)

    plt.tight_layout()
    plt.savefig(f"{OUT}/02_revenue_trend.png", dpi=150, bbox_inches="tight",
                facecolor="#FAFAFA")
    plt.close()
    print("  ✓ 02_revenue_trend.png")

# ════════════════════════════════════════════════════════
#  CHART 3 — Department Performance Matrix
# ════════════════════════════════════════════════════════
def plot_department_matrix():
    dept = (admissions.groupby("department_name")
            .agg(revenue=("total_bill","sum"),
                 admissions=("admission_id","count"),
                 avg_los=("length_of_stay","mean"),
                 readmission_rate=("readmitted_30days","mean"),
                 avg_bill=("total_bill","mean"))
            .reset_index())

    fig, axes = plt.subplots(1, 3, figsize=(18, 6))
    fig.patch.set_facecolor("#FAFAFA")
    fig.suptitle("Department Performance Matrix", fontsize=14,
                 fontweight="bold", color=COLORS["primary"])

    # Revenue bar
    ax = axes[0]; ax.set_facecolor("#F0F9FF")
    dept_s = dept.sort_values("revenue", ascending=True)
    colors = [COLORS["teal"] if i >= len(dept_s)-3 else COLORS["grey"]
              for i in range(len(dept_s))]
    bars = ax.barh(dept_s["department_name"], dept_s["revenue"]/1e7,
                   color=colors, edgecolor="white", alpha=0.85)
    for bar, val in zip(bars, dept_s["revenue"]/1e7):
        ax.text(bar.get_width()+0.02, bar.get_y()+bar.get_height()/2,
                f"₹{val:.2f}Cr", va="center", fontsize=9, fontweight="bold")
    ax.set_xlabel("Total Revenue (Crore)"); ax.set_title("Revenue by Department", fontweight="bold")
    ax.grid(axis="x", alpha=0.3)

    # Bubble chart: revenue vs readmission
    ax = axes[1]; ax.set_facecolor("#F0F9FF")
    scatter = ax.scatter(dept["readmission_rate"]*100, dept["avg_bill"]/1000,
                         s=dept["admissions"]*5, alpha=0.7,
                         c=dept["revenue"], cmap="YlOrRd", edgecolors="white")
    for _, row in dept.iterrows():
        ax.annotate(row["department_name"][:8],
                    (row["readmission_rate"]*100, row["avg_bill"]/1000),
                    textcoords="offset points", xytext=(5,5), fontsize=7)
    plt.colorbar(scatter, ax=ax, label="Total Revenue")
    ax.set_xlabel("Readmission Rate (%)"); ax.set_ylabel("Avg Bill (₹ thousands)")
    ax.set_title("Risk vs Revenue (bubble = admissions)", fontweight="bold")
    ax.grid(alpha=0.3)

    # Avg LOS comparison
    ax = axes[2]; ax.set_facecolor("#F0F9FF")
    dept_los = dept.sort_values("avg_los", ascending=False)
    bar_colors = [COLORS["red"] if v > 5 else COLORS["orange"] if v > 3
                  else COLORS["green"] for v in dept_los["avg_los"]]
    bars = ax.bar(dept_los["department_name"], dept_los["avg_los"],
                  color=bar_colors, edgecolor="white", alpha=0.85)
    for bar, val in zip(bars, dept_los["avg_los"]):
        ax.text(bar.get_x()+bar.get_width()/2, bar.get_height()+0.05,
                f"{val:.1f}d", ha="center", fontsize=9, fontweight="bold")
    ax.axhline(dept["avg_los"].mean(), color="black", linestyle="--",
               alpha=0.5, label=f"Avg: {dept['avg_los'].mean():.1f}d")
    ax.set_ylabel("Avg Length of Stay (days)")
    ax.set_title("Average LOS by Department", fontweight="bold")
    plt.setp(ax.xaxis.get_majorticklabels(), rotation=45, ha="right", fontsize=8)
    ax.legend(); ax.grid(axis="y", alpha=0.3)

    plt.tight_layout()
    plt.savefig(f"{OUT}/03_department_matrix.png", dpi=150, bbox_inches="tight",
                facecolor="#FAFAFA")
    plt.close()
    print("  ✓ 03_department_matrix.png")

# ════════════════════════════════════════════════════════
#  CHART 4 — ML: Readmission Prediction
# ════════════════════════════════════════════════════════
def build_readmission_model():
    df = admissions.merge(patients[["patient_id","age","gender"]], on="patient_id", how="left")

    le = LabelEncoder()
    df["dept_enc"]      = le.fit_transform(df["department_name"])
    df["severity_enc"]  = le.fit_transform(df["severity"])
    df["bed_enc"]       = le.fit_transform(df["bed_type"])
    df["adm_type_enc"]  = le.fit_transform(df["admission_type"])
    df["gender_enc"]    = le.fit_transform(df["gender"].fillna("Unknown"))

    features = ["age","dept_enc","severity_enc","bed_enc","adm_type_enc",
                "gender_enc","length_of_stay","total_bill","insurance_covered",
                "patient_paid","month"]
    df_clean = df[features + ["readmitted_30days"]].dropna()

    X = df_clean[features]
    y = df_clean["readmitted_30days"]

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, stratify=y, random_state=42)

    model = RandomForestClassifier(n_estimators=150, max_depth=7,
                                    class_weight="balanced", random_state=42)
    model.fit(X_train, y_train)
    y_pred  = model.predict(X_test)
    y_proba = model.predict_proba(X_test)[:,1]

    auc = roc_auc_score(y_test, y_proba)
    cv  = cross_val_score(model, X, y, cv=5, scoring="roc_auc").mean()

    # Feature importance plot
    feat_imp = pd.Series(model.feature_importances_, index=features).sort_values(ascending=False)

    fig, axes = plt.subplots(1, 3, figsize=(18, 6))
    fig.patch.set_facecolor("#FAFAFA")
    fig.suptitle(f"Readmission Prediction Model — ROC-AUC: {auc:.3f} | CV AUC: {cv:.3f}",
                 fontsize=14, fontweight="bold", color=COLORS["primary"])

    # Feature importance
    ax = axes[0]; ax.set_facecolor("#F0F9FF")
    colors_fi = [COLORS["red"] if v > 0.15 else COLORS["teal"] for v in feat_imp.values]
    bars = ax.barh(feat_imp.index, feat_imp.values, color=colors_fi,
                   edgecolor="white", alpha=0.85)
    for bar, val in zip(bars, feat_imp.values):
        ax.text(bar.get_width()+0.002, bar.get_y()+bar.get_height()/2,
                f"{val:.3f}", va="center", fontsize=9)
    ax.set_title("Feature Importance", fontweight="bold")
    ax.invert_yaxis(); ax.grid(axis="x", alpha=0.3)

    # Confusion matrix
    ax = axes[1]
    cm = confusion_matrix(y_test, y_pred)
    im = ax.imshow(cm, cmap="Blues")
    ax.set_xticks([0,1]); ax.set_yticks([0,1])
    ax.set_xticklabels(["Not Readmitted","Readmitted"])
    ax.set_yticklabels(["Not Readmitted","Readmitted"])
    ax.set_xlabel("Predicted"); ax.set_ylabel("Actual")
    ax.set_title("Confusion Matrix", fontweight="bold")
    thresh = cm.max() / 2
    for i in range(2):
        for j in range(2):
            ax.text(j, i, str(cm[i,j]), ha="center", va="center",
                    fontsize=16, fontweight="bold",
                    color="white" if cm[i,j] > thresh else "black")

    # Readmission rate by severity
    ax = axes[2]; ax.set_facecolor("#F0F9FF")
    sev_rates = (admissions.groupby(["severity","department_name"])
                 ["readmitted_30days"].mean() * 100).reset_index()
    pivot = sev_rates.pivot(index="department_name", columns="severity",
                            values="readmitted_30days").fillna(0)
    pivot = pivot[["Mild","Moderate","Severe","Critical"]]
    im2 = ax.imshow(pivot.values, cmap="RdYlGn_r", aspect="auto")
    ax.set_xticks(range(len(pivot.columns))); ax.set_xticklabels(pivot.columns)
    ax.set_yticks(range(len(pivot.index)))
    ax.set_yticklabels(pivot.index, fontsize=8)
    ax.set_title("Readmission Rate Heatmap\nDept × Severity (%)", fontweight="bold")
    plt.colorbar(im2, ax=ax, label="Readmission %")
    for i in range(len(pivot.index)):
        for j in range(len(pivot.columns)):
            ax.text(j, i, f"{pivot.values[i,j]:.0f}%",
                    ha="center", va="center", fontsize=8, color="black")

    plt.tight_layout()
    plt.savefig(f"{OUT}/04_readmission_model.png", dpi=150, bbox_inches="tight",
                facecolor="#FAFAFA")
    plt.close()
    print(f"  ✓ 04_readmission_model.png  (AUC={auc:.3f})")
    return auc, cv

# ════════════════════════════════════════════════════════
#  CHART 5 — Patient Segmentation (K-Means)
# ════════════════════════════════════════════════════════
def plot_patient_segmentation():
    pat_stats = (admissions.groupby("patient_id")
                 .agg(total_spend=("total_bill","sum"),
                      visits=("admission_id","count"),
                      avg_los=("length_of_stay","mean"),
                      readmissions=("readmitted_30days","sum"))
                 .reset_index())
    pat_stats = pat_stats.merge(patients[["patient_id","age"]], on="patient_id", how="left")
    pat_stats = pat_stats.dropna()

    features = ["total_spend","visits","avg_los","readmissions","age"]
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(pat_stats[features])

    kmeans = KMeans(n_clusters=4, random_state=42, n_init=10)
    pat_stats["segment"] = kmeans.fit_predict(X_scaled)

    seg_labels = {
        pat_stats.groupby("segment")["total_spend"].mean().idxmax(): "💎 High Value",
        pat_stats.groupby("segment")["visits"].mean().idxmax():       "🔄 Frequent",
        pat_stats.groupby("segment")["avg_los"].mean().idxmax():      "🏥 Complex Care",
        pat_stats.groupby("segment")["total_spend"].mean().idxmin():  "🌱 Low Engagement",
    }
    # Handle conflicts gracefully
    used = set()
    final_labels = {}
    for seg_id in pat_stats["segment"].unique():
        if seg_id in seg_labels and seg_labels[seg_id] not in used:
            final_labels[seg_id] = seg_labels[seg_id]
            used.add(seg_labels[seg_id])
        else:
            final_labels[seg_id] = f"Segment {seg_id}"
    pat_stats["segment_label"] = pat_stats["segment"].map(final_labels)

    fig, axes = plt.subplots(1, 3, figsize=(18, 6))
    fig.patch.set_facecolor("#FAFAFA")
    fig.suptitle("Patient Segmentation — K-Means Clustering (4 Segments)",
                 fontsize=14, fontweight="bold", color=COLORS["primary"])

    seg_colors = ["#0D3B6E","#16A34A","#D97706","#DC2626"]

    # Scatter: spend vs visits
    ax = axes[0]; ax.set_facecolor("#F0F9FF")
    for i, (seg_id, label) in enumerate(final_labels.items()):
        sub = pat_stats[pat_stats["segment"] == seg_id]
        ax.scatter(sub["visits"], sub["total_spend"]/1000, alpha=0.5,
                   s=20, color=seg_colors[i % 4], label=label)
    ax.set_xlabel("Number of Visits"); ax.set_ylabel("Total Spend (₹ thousands)")
    ax.set_title("Spend vs Visits", fontweight="bold")
    ax.legend(fontsize=8); ax.grid(alpha=0.3)

    # Segment size + revenue
    ax = axes[1]; ax.set_facecolor("#F0F9FF")
    seg_summary = (pat_stats.groupby("segment_label")
                   .agg(patients=("patient_id","count"),
                        avg_spend=("total_spend","mean"),
                        total_revenue=("total_spend","sum"))
                   .reset_index())
    bars = ax.bar(seg_summary["segment_label"],
                  seg_summary["total_revenue"]/1e6,
                  color=seg_colors[:len(seg_summary)], edgecolor="white", alpha=0.85)
    for bar, val in zip(bars, seg_summary["total_revenue"]/1e6):
        ax.text(bar.get_x()+bar.get_width()/2, bar.get_height()+0.2,
                f"₹{val:.1f}M", ha="center", fontsize=9, fontweight="bold")
    ax.set_ylabel("Segment Revenue (₹ Million)")
    ax.set_title("Revenue by Patient Segment", fontweight="bold")
    plt.setp(ax.xaxis.get_majorticklabels(), rotation=20, ha="right", fontsize=9)
    ax.grid(axis="y", alpha=0.3)

    # Radar-style bar: avg metrics per segment
    ax = axes[2]; ax.set_facecolor("#F0F9FF")
    seg_avg = pat_stats.groupby("segment_label")[["total_spend","visits","avg_los"]].mean()
    seg_avg_norm = (seg_avg - seg_avg.min()) / (seg_avg.max() - seg_avg.min() + 1e-9)
    x = np.arange(len(seg_avg_norm.columns))
    w = 0.2
    for i, (seg, row) in enumerate(seg_avg_norm.iterrows()):
        ax.bar(x + i*w, row.values, w, label=seg,
               color=seg_colors[i % 4], alpha=0.8, edgecolor="white")
    ax.set_xticks(x + w*1.5)
    ax.set_xticklabels(["Normalised\nSpend","Normalised\nVisits","Normalised\nLOS"])
    ax.set_title("Segment Profile (Normalised)", fontweight="bold")
    ax.legend(fontsize=8); ax.grid(axis="y", alpha=0.3)

    plt.tight_layout()
    plt.savefig(f"{OUT}/05_patient_segments.png", dpi=150, bbox_inches="tight",
                facecolor="#FAFAFA")
    plt.close()
    print("  ✓ 05_patient_segments.png")

# ════════════════════════════════════════════════════════
#  CHART 6 — Insurance & Revenue Leakage
# ════════════════════════════════════════════════════════
def plot_insurance_analysis():
    ins = (admissions.groupby("insurance_provider")
           .agg(claims=("admission_id","count"),
                billed=("total_bill","sum"),
                covered=("insurance_covered","sum"),
                collected=("patient_paid","sum"))
           .reset_index())
    ins["gap"]      = ins["billed"] - ins["covered"] - ins["collected"]
    ins["coverage_pct"] = ins["covered"] / ins["billed"] * 100
    ins = ins.sort_values("billed", ascending=False)

    fig, axes = plt.subplots(1, 2, figsize=(16, 7))
    fig.patch.set_facecolor("#FAFAFA")
    fig.suptitle("Insurance Provider Analysis — Revenue & Coverage",
                 fontsize=14, fontweight="bold", color=COLORS["primary"])

    # Stacked bar
    ax = axes[0]; ax.set_facecolor("#F0F9FF")
    x = range(len(ins))
    ax.bar(x, ins["covered"]/1e6,   label="Insurance Paid", color=COLORS["teal"],  alpha=0.85)
    ax.bar(x, ins["collected"]/1e6, label="Patient Paid",   color=COLORS["green"], alpha=0.85,
           bottom=ins["covered"]/1e6)
    ax.bar(x, ins["gap"].clip(lower=0)/1e6, label="Revenue Gap",
           color=COLORS["red"], alpha=0.7,
           bottom=(ins["covered"]+ins["collected"])/1e6)
    ax.set_xticks(x)
    ax.set_xticklabels(ins["insurance_provider"], rotation=45, ha="right", fontsize=8)
    ax.set_ylabel("Revenue (₹ Million)")
    ax.set_title("Billing Breakdown by Insurer", fontweight="bold")
    ax.legend(); ax.grid(axis="y", alpha=0.3)

    # Coverage % scatter
    ax = axes[1]; ax.set_facecolor("#F0F9FF")
    colors_cov = [COLORS["green"] if c >= 60 else COLORS["orange"] if c >= 35
                  else COLORS["red"] for c in ins["coverage_pct"]]
    scatter = ax.scatter(ins["claims"], ins["coverage_pct"],
                         s=ins["billed"]/5000, c=colors_cov, alpha=0.8, edgecolors="white")
    for _, row in ins.iterrows():
        ax.annotate(row["insurance_provider"][:10],
                    (row["claims"], row["coverage_pct"]),
                    textcoords="offset points", xytext=(5,4), fontsize=7)
    ax.axhline(60, color=COLORS["green"], linestyle="--", alpha=0.5, label="Good (60%)")
    ax.axhline(35, color=COLORS["orange"], linestyle="--", alpha=0.5, label="Moderate (35%)")
    ax.set_xlabel("Number of Claims")
    ax.set_ylabel("Insurance Coverage %")
    ax.set_title("Coverage % vs Claim Volume\n(bubble = total billed)", fontweight="bold")
    ax.legend(fontsize=8); ax.grid(alpha=0.3)

    plt.tight_layout()
    plt.savefig(f"{OUT}/06_insurance_analysis.png", dpi=150, bbox_inches="tight",
                facecolor="#FAFAFA")
    plt.close()
    print("  ✓ 06_insurance_analysis.png")

# ════════════════════════════════════════════════════════
#  MAIN
# ════════════════════════════════════════════════════════
if __name__ == "__main__":
    print("\n" + "="*55)
    print("  HOSPITAL ANALYTICS — PYTHON ANALYSIS LAYER")
    print("="*55)

    print("\n[1/6] Executive KPIs...")
    plot_executive_kpis()

    print("[2/6] Revenue trend...")
    plot_revenue_trend()

    print("[3/6] Department matrix...")
    plot_department_matrix()

    print("[4/6] Readmission ML model...")
    auc, cv = build_readmission_model()

    print("[5/6] Patient segmentation...")
    plot_patient_segmentation()

    print("[6/6] Insurance analysis...")
    plot_insurance_analysis()

    print("\n" + "="*55)
    print("  ✅  All charts saved to outputs/")
    total_rev = admissions["total_bill"].sum()
    print(f"\n  Key Metrics:")
    print(f"  Total Revenue     : ₹{total_rev/1e7:.2f} Crore")
    print(f"  Total Admissions  : {len(admissions):,}")
    print(f"  Readmission Rate  : {admissions['readmitted_30days'].mean()*100:.1f}%")
    print(f"  ML Model AUC      : {auc:.3f}")
    print(f"  ML CV AUC         : {cv:.3f}")
    print("="*55 + "\n")
