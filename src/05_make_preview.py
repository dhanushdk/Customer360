import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
from config import DOCS, PROC

k = pd.read_csv(PROC / "fact_dq_kpi.csv")
fb = pd.read_csv(PROC / "fact_booking.csv")
att = pd.read_csv(PROC / "fact_dq_attribute.csv")
cu = pd.read_csv(PROC / "dim_customer.csv", keep_default_na=False)
unl = pd.read_csv(PROC / "fact_unlinked_reasons.csv")
col = {"Green": "#2E7D32", "Amber": "#F9A825", "Red": "#C62828"}
fig, ax = plt.subplots(2, 3, figsize=(17, 9))
fig.suptitle("Customer 360 data quality - pipeline QA preview (synthetic data)", fontsize=14, color="#1F3864")

a = ax[0, 0]; kk = k.iloc[::-1]
a.barh(kk["kpi_name"].str.slice(0, 42), kk["value"] * 100, color=[col[s] for s in kk["status"]])
for i, (v, t) in enumerate(zip(kk["value"], kk["target"])):
    a.plot([t * 100] * 2, [i - .4, i + .4], color="black", lw=1.5)
a.set_title("KPIs vs target (black tick)"); a.set_xlabel("%"); a.tick_params(axis="y", labelsize=7)

a = ax[0, 1]; ch = fb.groupby("channel")["is_linked_identified"].mean().sort_values() * 100
a.barh(ch.index, ch.values, color="#2E75B6"); a.axvline(90, color="#C62828", ls="--"); a.set_title("Booking link rate by channel (target 90%)")
for i, v in enumerate(ch.values): a.text(v + 1, i, f"{v:.0f}%", va="center", fontsize=8)

a = ax[0, 2]; a.pie(unl["bookings"], labels=unl["unlinked_reason"].str.slice(0, 26), autopct="%1.0f%%", textprops={"fontsize": 7}, colors=["#1F3864", "#2E75B6", "#9DC3E6", "#F9A825"])
a.set_title("Why bookings are unlinked")

a = ax[1, 0]; p = att[att["attribute"].isin(["email", "phone", "dob", "country"]) & att["source"].isin(["Loyalty", "Customer 360 (golden)"])]
pv = p.pivot(index="attribute", columns="source", values="valid_pct") * 100
pv.plot.bar(ax=a, color=["#9DC3E6", "#1F3864"]); a.set_title("Valid %: loyalty source vs Customer 360 golden"); a.set_ylabel("%"); a.tick_params(axis="x", rotation=0); a.legend(fontsize=8)

a = ax[1, 1]; fz = cu[cu["customer_type"] == "Identified"]["freshness_status"].value_counts().reindex(["Fresh (<=90d)", "Ageing (91-365d)", "Stale (>365d)"])
a.bar(fz.index, fz.values, color=["#2E7D32", "#F9A825", "#C62828"]); a.set_title("Customer freshness (identified)")

a = ax[1, 2]; vt = cu[cu["customer_type"] == "Identified"].groupby("value_tier")["revenue_24m_eur"].sum().reindex(["High", "Medium", "Low"]) / 1e6
a.bar(vt.index, vt.values, color="#2E75B6"); a.set_title("24-month customer value by tier (EUR m)")
plt.tight_layout(rect=[0, 0, 1, .95]); plt.savefig(DOCS / "dq_preview.png", dpi=110)
print("saved preview")
