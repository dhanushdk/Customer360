
import pandas as pd
from config import PBI, PROC

fb = pd.read_csv(PROC / "fact_booking.csv", keep_default_na=False, na_values=[""])
dc = pd.read_csv(PROC / "dim_customer.csv", keep_default_na=False, na_values=[""], low_memory=False)
kpi = pd.read_csv(PROC / "fact_dq_kpi.csv")
att = pd.read_csv(PROC / "fact_dq_attribute.csv")

b = pd.DataFrame({
    "record_type": "Booking", "record_id": fb["booking_id"], "customer_id": fb["customer_id"],
    "booking_date": fb["booking_date"], "booking_month": fb["booking_date"].str[:7] + "-01",
    "channel": fb["channel"], "cabin": fb["cabin"], "route": fb["route"], "status": fb["status"],
    "fare_eur": fb["fare_eur"], "net_revenue_eur": fb["net_revenue_eur"], "link_status": fb["link_status"],
    "unlinked_reason": fb["unlinked_reason"], "match_basis": fb["match_basis"],
    "is_linked_identified": fb["is_linked_identified"], "is_linked_loyalty": fb["is_linked_loyalty"],
    "has_loyalty_id_on_booking": fb["has_loyalty_id_on_booking"].astype(int), "loyalty_id_orphan": fb["loyalty_id_orphan"].astype(int)})

flags = ["is_active", "is_digitally_engaged", "has_loyalty", "has_first_name", "has_last_name", "has_email", "has_phone",
         "has_dob", "has_country", "fuzzy_review_flag"]
c = pd.DataFrame({"record_type": "Customer", "record_id": dc["customer_id"], "customer_id": dc["customer_id"]})
for col in ["customer_type", "country", "age_band", "loyalty_tier", "value_tier", "completeness_band", "missing_attributes",
            "freshness_status", "sources_present", "duplicate_flag"]:
    c[col] = dc[col]
for col in ["completeness_score", "days_since_signal", "revenue_24m_eur", "loyalty_records", "source_count", "bookings_12m"]:
    c[col] = dc[col]
for col in flags:
    c[col] = dc[col].astype(str).str.lower().eq("true").astype(int)

k = pd.DataFrame({"record_type": "KPI", "record_id": kpi["kpi_name"], "kpi_name": kpi["kpi_name"], "kpi_dimension": kpi["dimension"],
                  "kpi_value": kpi["value"], "kpi_target": kpi["target"], "kpi_status": kpi["status"]})
a = pd.DataFrame({"record_type": "Attribute", "record_id": att["source"] + "|" + att["attribute"], "attr_source": att["source"],
                  "attr_name": att["attribute"], "attr_records": att["records"], "attr_populated_pct": att["populated_pct"],
                  "attr_valid_pct": att["valid_pct"]})
flat = pd.concat([b, c, k, a], ignore_index=True)
flat.to_csv(PBI / "c360_flat.csv", index=False)
print(f"c360_flat.csv  rows={len(flat):,} cols={flat.shape[1]}  ", flat["record_type"].value_counts().to_dict())

bb, cc = flat[flat.record_type == "Booking"], flat[(flat.record_type == "Customer") & (flat.customer_type == "Identified")]
print("link rate", round(bb.is_linked_identified.mean(), 4), "| avg completeness", round(cc.completeness_score.mean(), 4),
      "| orphan", round(bb.loyalty_id_orphan.sum() / bb.has_loyalty_id_on_booking.sum(), 4),
      "| active", int(cc.is_active.sum()), "| value24m", round(cc.revenue_24m_eur.sum()))
