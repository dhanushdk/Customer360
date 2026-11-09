
import re
import sqlite3
import pandas as pd
from config import PROC, ROOT, DOCS

db = ROOT / "data" / "customer360.db"
if db.exists():
    db.unlink()
con = sqlite3.connect(db)
for t in ["raw_loyalty", "raw_bookings", "raw_digital", "dim_customer", "fact_booking", "fact_dq_attribute",
          "fact_dq_kpi", "fact_duplicate_candidates"]:
    raw = t.startswith("raw_")
    kw = dict(dtype=str, keep_default_na=False) if raw else dict(keep_default_na=False, na_values=[""], low_memory=False)
    pd.read_csv(PROC / f"{t}.csv", **kw).to_sql(t, con, index=False)


def run_file(path):
    blocks = re.split(r"^-- name:\s*(\w+)\s*$", path.read_text(), flags=re.M)[1:]
    return {blocks[i]: pd.read_sql_query(blocks[i + 1].strip().rstrip(";"), con) for i in range(0, len(blocks), 2)}


res = {}
for f in sorted((ROOT / "sql").glob("*.sql")):
    res.update(run_file(f))

log = []
pd.set_option("display.width", 200, "display.max_columns", 20)
for name, df in res.items():
    log.append(f"--- {name} ---\n{df.to_string(index=False)}\n")

kpi = pd.read_csv(PROC / "fact_dq_kpi.csv").set_index("kpi_name")["value"]
checks = [
    ("Bookings linked to identified customer %", res["booking_link_rate"]["pct_linked_identified"][0]),
    ("Bookings linked to loyalty member %", res["booking_link_rate"]["pct_linked_loyalty"][0]),
    ("Avg profile completeness % (identified)", res["avg_profile_completeness"]["avg_completeness"][0]),
    ("Profiles >=90% complete %", res["avg_profile_completeness"]["pct_ge_90"][0]),
    ("Loyalty duplicate rate % (exact-key)", res["loyalty_duplicate_rate"]["duplicate_rate"][0]),
    ("Orphan loyalty IDs on bookings %", res["orphan_loyalty_id_rate"]["orphan_rate"][0]),
    ("Identified profiles refreshed in last 12m %", res["refreshed_last_12m"]["pct_refreshed_12m"][0]),
]
log.append("=== RECONCILIATION: SQL vs Pandas ===")
ok = True
for k, sql_v in checks:
    diff = abs(sql_v - kpi[k])
    ok &= diff < 5e-4
    log.append(f"{'PASS' if diff < 5e-4 else 'FAIL'}  {k:<48} sql={sql_v:.4f} pandas={kpi[k]:.4f}")
(DOCS / "sql_validation.txt").write_text("\n".join(log))
print("\n".join(log[-(len(checks) + 1):]))
print("\nALL CHECKS PASSED" if ok else "\nCHECKS FAILED")
for n in ("row_counts", "loyalty_raw_completeness", "orphan_loyalty_ids_on_bookings", "shared_contact_candidates", "booking_link_rate_by_channel", "freshness_buckets", "active_customers_and_value"):
    print(f"\n--- {n} ---\n{res[n].to_string(index=False)}")
