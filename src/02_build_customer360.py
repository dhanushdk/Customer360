import json
from difflib import SequenceMatcher

import numpy as np
import pandas as pd
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components

from config import *
from utils import clean_null, fold, norm_country, norm_email, norm_phone, parse_dob

SRC_PRIORITY = {"LOYALTY": 1, "BOOKING": 2, "DIGITAL": 3}


def read(name):
    return pd.read_csv(RAW / name, dtype=str, keep_default_na=False)


def out(df, name):
    df.to_csv(PROC / f"{name}.csv", index=False)
    df.to_csv(PBI / f"{name}.csv", index=False)


def std_contact(df, f, l, e, p):
    o = pd.DataFrame(index=df.index)
    o["first_name"] = df[f].map(clean_null).str.strip().str.title()
    o["last_name"] = df[l].map(clean_null).str.strip().str.title()
    o["first_n"], o["last_n"] = df[f].map(fold), df[l].map(fold)
    em, ph = df[e].map(norm_email), df[p].map(norm_phone)
    o["email_raw_present"] = df[e].map(clean_null).notna()
    o["email_n"], o["email_valid"] = em.map(lambda t: t[0]), em.map(lambda t: t[1]).astype(bool)
    o["phone_raw_present"] = df[p].map(clean_null).notna()
    o["phone_n"], o["phone_valid"] = ph.map(lambda t: t[0]), ph.map(lambda t: t[1]).astype(bool)
    return o


loy_raw, bk_raw, dg_raw = read("loyalty_members.csv"), read("bookings.csv"), read("digital_events.csv")

L = std_contact(loy_raw, "first_name", "last_name", "email", "phone")
L["dob"], L["dob_populated"], L["dob_valid"] = parse_dob(loy_raw["date_of_birth"], AS_OF)
L["country_populated"] = loy_raw["country"].map(clean_null).notna()
L["country"] = loy_raw["country"].map(norm_country)
L["member_id"], L["tier"] = loy_raw["member_id"], loy_raw["tier"]
L["record_ts"] = pd.to_datetime(loy_raw["last_updated"])
L["source"], L["source_key"] = "LOYALTY", loy_raw["member_id"]
L["record_id"] = "L|" + L["source_key"]

B = std_contact(bk_raw, "contact_first_name", "contact_last_name", "contact_email", "contact_phone")
B["loyalty_id"] = bk_raw["loyalty_id"].map(clean_null)
B["loyalty_id_orphan"] = B["loyalty_id"].notna() & ~B["loyalty_id"].isin(set(L["member_id"]))
B["record_ts"] = pd.to_datetime(bk_raw["booking_date"])
B["source"], B["source_key"] = "BOOKING", bk_raw["booking_id"]
B["record_id"] = "B|" + B["source_key"]

dg = dg_raw.copy()
dg["member_id"] = dg["member_id"].map(clean_null)
em = dg["email"].map(norm_email)
dg["email_n"], dg["email_valid"] = em.map(lambda t: t[0]), em.map(lambda t: t[1]).astype(bool)
dg["event_ts"] = pd.to_datetime(dg["event_ts"])
dg["member_ok"] = dg["member_id"].isin(set(L["member_id"]))
D = dg.groupby("device_id").agg(first_ts=("event_ts", "min"), record_ts=("event_ts", "max"),
                                n_events=("event_id", "count"), platform=("platform", "first")).reset_index()
D["events_90d"] = D["device_id"].map(dg[dg["event_ts"] >= AS_OF - pd.Timedelta(days=90)].groupby("device_id").size()).fillna(0).astype(int)
D["has_member_link"] = D["device_id"].isin(dg.loc[dg["member_ok"], "device_id"])
D["has_email"] = D["device_id"].isin(dg.loc[dg["email_valid"], "device_id"])
D["source"], D["source_key"], D["record_id"] = "DIGITAL", D["device_id"], "D|" + D["device_id"]

names = pd.concat([L[["email_n", "email_valid", "phone_n", "phone_valid", "last_n"]],
                   B[["email_n", "email_valid", "phone_n", "phone_valid", "last_n"]]])
n_sur_email = names[names["email_valid"]].groupby("email_n")["last_n"].nunique()
n_sur_phone = names[names["phone_valid"]].groupby("phone_n")["last_n"].nunique()
shared_emails = set(n_sur_email[n_sur_email >= SHARED_ID_MIN_SURNAMES].index)
shared_phones = set(n_sur_phone[n_sur_phone >= SHARED_ID_MIN_SURNAMES].index)
for df in (L, B):
    df["email_shared"] = df["email_n"].isin(shared_emails)
    df["phone_shared"] = df["phone_n"].isin(shared_phones)
dg["email_shared"] = dg["email_n"].isin(shared_emails)
print(f"shared emails={len(shared_emails)}  shared phones={len(shared_phones)}")

keys = []


def add_keys(rec_ids, kind, values, mask):
    k = pd.DataFrame({"record_id": rec_ids[mask].to_numpy(), "key_type": kind, "key_value": values[mask].to_numpy()})
    keys.append(k)


for df, rid in ((L, L["record_id"]), (B, B["record_id"])):
    add_keys(rid, "EMAIL", df["email_n"], df["email_valid"] & ~df["email_shared"])
    pn = (df["phone_n"].fillna("") + "|" + df["last_n"].fillna(""))
    add_keys(rid, "PHONE_NAME", pn, df["phone_valid"] & ~df["phone_shared"] & df["last_n"].notna())
add_keys(L["record_id"], "LOYALTY_ID", L["member_id"], pd.Series(True, index=L.index))
add_keys(B["record_id"], "LOYALTY_ID", B["loyalty_id"], B["loyalty_id"].notna() & ~B["loyalty_id_orphan"])
dev_member = dg[dg["member_ok"]][["device_id", "member_id"]].drop_duplicates()
keys.append(pd.DataFrame({"record_id": "D|" + dev_member["device_id"], "key_type": "LOYALTY_ID", "key_value": dev_member["member_id"]}))
dev_email = dg[dg["email_valid"] & ~dg["email_shared"]][["device_id", "email_n"]].drop_duplicates()
keys.append(pd.DataFrame({"record_id": "D|" + dev_email["device_id"], "key_type": "EMAIL", "key_value": dev_email["email_n"]}))
K = pd.concat(keys, ignore_index=True).drop_duplicates()

rec_ids = pd.concat([L["record_id"], B["record_id"], D["record_id"]], ignore_index=True)
rid2i = pd.Series(np.arange(len(rec_ids)), index=rec_ids)
K["kid"] = pd.factorize(K["key_type"] + "|" + K["key_value"])[0]
r, k = rid2i.loc[K["record_id"]].to_numpy(), K["kid"].to_numpy() + len(rec_ids)
n_nodes = len(rec_ids) + K["kid"].max() + 1
_, labels = connected_components(coo_matrix((np.ones(len(r)), (r, k)), shape=(n_nodes, n_nodes)), directed=False)
cust_idx = pd.factorize(labels[:len(rec_ids)])[0]
cust_of = pd.Series(["C" + f"{i + 1:07d}" for i in cust_idx], index=rec_ids.to_numpy())
basis = K.groupby("record_id")["key_type"].agg(lambda s: "+".join(sorted(set(s))))

for df in (L, B, D):
    df["customer_id"] = df["record_id"].map(cust_of)
    df["match_basis"] = df["record_id"].map(basis)
    df["has_key"] = df["match_basis"].notna()
    df["match_basis"] = df["match_basis"].fillna("None")

def reason_booking(row):
    if row.has_key:
        return None
    if row.loyalty_id_orphan:
        return "Orphan loyalty ID"
    if row.email_shared or row.phone_shared:
        return "Shared contact (agency / travel desk)"
    if (row.email_raw_present and not row.email_valid) or (row.phone_raw_present and not row.phone_valid):
        return "Invalid contact data"
    if not row.email_raw_present and not row.phone_raw_present:
        return "No contact data"
    return "No usable identifier"


B["unlinked_reason"] = B.apply(reason_booking, axis=1)
D["unlinked_reason"] = np.where(D["has_key"], None, "Anonymous device (no login / email)")
print(f"records={len(rec_ids):,} -> customers={cust_of.nunique():,}")

Lv = L[L["dob"].notna() & L["last_n"].notna() & L["first_n"].notna()].copy()
Lv["blk"] = Lv["dob"].dt.strftime("%Y%m%d") + Lv["last_n"].str[0]
cands = []
for _, g in Lv.groupby("blk"):
    if len(g) < 2:
        continue
    rows = g.to_dict("records")
    for i in range(len(rows)):
        for j in range(i + 1, len(rows)):
            a, b = rows[i], rows[j]
            if a["customer_id"] == b["customer_id"]:
                continue
            ls = SequenceMatcher(None, a["last_n"], b["last_n"]).ratio()
            fs = SequenceMatcher(None, a["first_n"], b["first_n"]).ratio()
            if ls >= FUZZY_NAME_THRESHOLD and (fs >= 0.6 or a["first_n"][0] == b["first_n"][0]):
                cands.append({"member_id_a": a["member_id"], "member_id_b": b["member_id"],
                              "customer_id_a": a["customer_id"], "customer_id_b": b["customer_id"],
                              "name_a": f'{a["first_name"]} {a["last_name"]}', "name_b": f'{b["first_name"]} {b["last_name"]}',
                              "date_of_birth": a["dob"].date(), "surname_similarity": round(ls, 3),
                              "firstname_similarity": round(fs, 3), "match_score": round(.6 * ls + .4 * fs, 3),
                              "status": "Review"})
fuzzy = pd.DataFrame(cands, columns=["member_id_a", "member_id_b", "customer_id_a", "customer_id_b", "name_a", "name_b",
                                     "date_of_birth", "surname_similarity", "firstname_similarity", "match_score", "status"])
fuzzy_members = set(fuzzy["member_id_a"]) | set(fuzzy["member_id_b"])
L["in_fuzzy_pair"] = L["member_id"].isin(fuzzy_members)
print(f"fuzzy candidate pairs={len(fuzzy)}")

def attr_frame(df, src):
    return pd.DataFrame({
        "customer_id": df["customer_id"], "prio": SRC_PRIORITY[src], "ts": df["record_ts"],
        "first_name": df["first_name"], "last_name": df["last_name"],
        "email": df["email_n"].where(df["email_valid"]), "phone": df["phone_n"].where(df["phone_valid"]),
        "dob": df["dob"] if "dob" in df else pd.NaT, "country": df["country"] if "country" in df else None})


A = pd.concat([attr_frame(L, "LOYALTY"), attr_frame(B, "BOOKING")], ignore_index=True)
dev_e = dg[dg["email_valid"]].drop_duplicates("device_id").set_index("device_id")["email_n"]
Ad = pd.DataFrame({"customer_id": D["customer_id"], "prio": 3, "ts": D["record_ts"], "email": D["device_id"].map(dev_e)})
A = pd.concat([A, Ad], ignore_index=True).sort_values(["customer_id", "prio", "ts"], ascending=[True, True, False])
ATTRS = list(PROFILE_WEIGHTS)
G = A.groupby("customer_id")[ATTRS].first()
G["dob"] = pd.to_datetime(G["dob"])

all_cust = pd.Series(cust_of.unique(), name="customer_id")
C = pd.DataFrame({"customer_id": all_cust}).merge(G, left_on="customer_id", right_index=True, how="left")
has_key_c = pd.concat([L[["customer_id", "has_key"]], B[["customer_id", "has_key"]], D[["customer_id", "has_key"]]]).groupby("customer_id")["has_key"].any()
C["customer_type"] = np.where(C["customer_id"].map(has_key_c), "Identified", "Unidentified")

B["booking_date"] = B["record_ts"]
B["status"] = bk_raw["status"]
B["fare_eur"] = bk_raw["fare_eur"].astype(float)
B["net_revenue_eur"] = np.where(B["status"] == "Cancelled", 0.0, B["fare_eur"])
live = B[B["status"] != "Cancelled"]
g = live.groupby("customer_id")
C["bookings_total"] = C["customer_id"].map(B.groupby("customer_id").size()).fillna(0).astype(int)
C["bookings_12m"] = C["customer_id"].map(live[live["booking_date"] >= AS_OF - pd.Timedelta(days=ACTIVE_WINDOW_DAYS)].groupby("customer_id").size()).fillna(0).astype(int)
C["revenue_24m_eur"] = C["customer_id"].map(live[live["booking_date"] >= AS_OF - pd.Timedelta(days=VALUE_WINDOW_DAYS)].groupby("customer_id")["fare_eur"].sum()).fillna(0).round(2)
C["revenue_lifetime_eur"] = C["customer_id"].map(g["fare_eur"].sum()).fillna(0).round(2)
C["last_booking_date"] = C["customer_id"].map(B.groupby("customer_id")["booking_date"].max())
Lg = L.sort_values("record_ts", ascending=False).groupby("customer_id")
C["loyalty_records"] = C["customer_id"].map(L.groupby("customer_id").size()).fillna(0).astype(int)
C["primary_member_id"] = C["customer_id"].map(Lg["member_id"].first())
C["loyalty_tier"] = C["customer_id"].map(Lg["tier"].first())
C["loyalty_last_updated"] = C["customer_id"].map(L.groupby("customer_id")["record_ts"].max())
C["devices"] = C["customer_id"].map(D.groupby("customer_id").size()).fillna(0).astype(int)
C["last_digital_event"] = C["customer_id"].map(D.groupby("customer_id")["record_ts"].max())
C["digital_events_90d"] = C["customer_id"].map(D.groupby("customer_id")["events_90d"].sum()).fillna(0).astype(int)
src = pd.concat([L[["customer_id", "source"]], B[["customer_id", "source"]], D[["customer_id", "source"]]]).drop_duplicates()
C["sources_present"] = C["customer_id"].map(src.groupby("customer_id")["source"].agg(lambda s: "+".join(x[0] for x in ["BOOKING", "LOYALTY", "DIGITAL"] if x in set(s))))
C["source_count"] = C["customer_id"].map(src.groupby("customer_id").size())
C["has_loyalty"] = C["loyalty_records"] > 0
C["last_signal_date"] = C[["last_booking_date", "last_digital_event", "loyalty_last_updated"]].max(axis=1).dt.normalize()
C["days_since_signal"] = (AS_OF - C["last_signal_date"]).dt.days
C["freshness_status"] = np.select([C["days_since_signal"] <= FRESH_FRESH_DAYS, C["days_since_signal"] <= FRESH_AGEING_DAYS],
                                  ["Fresh (<=90d)", "Ageing (91-365d)"], "Stale (>365d)")
C["is_active"] = C["bookings_12m"] >= 1
C["is_digitally_engaged"] = C["digital_events_90d"] >= 1
C["value_tier"] = "No spend"
for thr, name in sorted(VALUE_TIERS):
    C.loc[C["revenue_24m_eur"] >= thr, "value_tier"] = name
for a in ATTRS:
    C[f"has_{a}"] = C[a].notna()
C["completeness_score"] = sum(C[f"has_{a}"] * w for a, w in PROFILE_WEIGHTS.items()).round(4)
C["completeness_band"] = np.select([C["completeness_score"] >= t for t, _ in COMPLETENESS_BANDS[:-1]],
                                   [n for _, n in COMPLETENESS_BANDS[:-1]], COMPLETENESS_BANDS[-1][1])
C["missing_attributes"] = C[[f"has_{a}" for a in ATTRS]].apply(lambda r: ", ".join(a for a in ATTRS if not r[f"has_{a}"]), axis=1)
C["duplicate_flag"] = np.select([C["loyalty_records"] > 1], ["Merged duplicates"], "Unique")
C["fuzzy_review_flag"] = C["customer_id"].isin(set(fuzzy["customer_id_a"]) | set(fuzzy["customer_id_b"]))
L["enrol_date"] = pd.to_datetime(loy_raw["enrolment_date"])
C["loyalty_tenure_years"] = ((AS_OF - C["customer_id"].map(L.groupby("customer_id")["enrol_date"].min())).dt.days / 365.25).round(1)
ident = C[C["customer_type"] == "Identified"]

cust_has_loy = C.set_index("customer_id")["has_loyalty"]
B["is_linked_identified"] = B["has_key"]
B["is_linked_loyalty"] = B["customer_id"].map(cust_has_loy)
B["link_status"] = np.select([B["is_linked_loyalty"], B["is_linked_identified"]],
                             ["Linked - loyalty member", "Linked - identified non-member"], "Unlinked")

def attr_row(source, attr, populated, valid):
    n = len(populated)
    return {"source": source, "attribute": attr, "records": n, "populated": int(populated.sum()), "valid": int(valid.sum()),
            "populated_pct": populated.mean(), "valid_pct": valid.mean(),
            "valid_of_populated_pct": valid.sum() / max(populated.sum(), 1)}


rows = []
t = pd.Series(True, index=L.index)
for a, p_, v_ in [("first_name", L["first_n"].notna(), L["first_n"].notna()), ("last_name", L["last_n"].notna(), L["last_n"].notna()),
                  ("email", L["email_raw_present"], L["email_valid"]), ("phone", L["phone_raw_present"], L["phone_valid"]),
                  ("dob", L["dob_populated"], L["dob_valid"]), ("country", L["country_populated"], L["country"].notna())]:
    rows.append(attr_row("Loyalty", a, p_, v_))
for a, p_, v_ in [("first_name", B["first_n"].notna(), B["first_n"].notna()), ("last_name", B["last_n"].notna(), B["last_n"].notna()),
                  ("email", B["email_raw_present"], B["email_valid"]), ("phone", B["phone_raw_present"], B["phone_valid"]),
                  ("loyalty_id", B["loyalty_id"].notna(), B["loyalty_id"].notna() & ~B["loyalty_id_orphan"])]:
    rows.append(attr_row("Bookings", a, p_, v_))
rows.append(attr_row("Digital", "email", D["has_email"], D["has_email"]))
rows.append(attr_row("Digital", "loyalty_id", D["has_member_link"], D["has_member_link"]))
for a in ATTRS:
    rows.append(attr_row("Customer 360 (golden)", a, ident[f"has_{a}"], ident[f"has_{a}"]))
f_attr = pd.DataFrame(rows)

# source freshness
fr = []
for name, df in (("Loyalty", L), ("Bookings", B), ("Digital", D)):
    age = (AS_OF - df["record_ts"]).dt.days
    fr.append({"source": name, "records": len(df), "latest_record_date": df["record_ts"].max().date(),
               "median_age_days": float(age.median()), "pct_older_365d": (age > 365).mean(), "pct_older_730d": (age > 730).mean()})
f_fresh = pd.DataFrame(fr)

# rule-level issue log
l_stale = (AS_OF - L["record_ts"]).dt.days > STALE_PROFILE_DAYS
dup_records = len(L) - L["customer_id"].nunique()
bk_shared = B["email_shared"] | B["phone_shared"]
rules = [
    ("LOY-C01", "Completeness", "Loyalty", "Email missing", len(L), (~L["email_raw_present"]).sum(), "High"),
    ("LOY-V01", "Validity", "Loyalty", "Email present but invalid / typo domain", L["email_raw_present"].sum(), (L["email_raw_present"] & ~L["email_valid"]).sum(), "High"),
    ("LOY-C02", "Completeness", "Loyalty", "Phone missing", len(L), (~L["phone_raw_present"]).sum(), "Medium"),
    ("LOY-V02", "Validity", "Loyalty", "Phone present but invalid / placeholder", L["phone_raw_present"].sum(), (L["phone_raw_present"] & ~L["phone_valid"]).sum(), "Medium"),
    ("LOY-C03", "Completeness", "Loyalty", "Date of birth missing", len(L), (~L["dob_populated"]).sum(), "Medium"),
    ("LOY-V03", "Validity", "Loyalty", "Date of birth placeholder / future / unparseable", L["dob_populated"].sum(), (L["dob_populated"] & ~L["dob_valid"]).sum(), "Medium"),
    ("LOY-C04", "Completeness", "Loyalty", "Country missing", len(L), (~L["country_populated"]).sum(), "Low"),
    ("LOY-V04", "Consistency", "Loyalty", "Country not an ISO-2 code (needed mapping)", L["country_populated"].sum(),
     (loy_raw["country"].map(clean_null).notna() & ~loy_raw["country"].isin(sorted(["FI", "SE", "DE", "GB", "US", "EE", "NO", "FR", "ES", "PL"]))).sum(), "Low"),
    ("LOY-F01", "Timeliness", "Loyalty", "Record not updated for > 24 months", len(L), l_stale.sum(), "Medium"),
    ("LOY-U01", "Uniqueness", "Loyalty", "Duplicate member record (exact-key match)", len(L), dup_records, "High"),
    ("LOY-U02", "Uniqueness", "Loyalty", "Probable duplicate (fuzzy, needs review)", len(L), len(fuzzy_members), "Medium"),
    ("BKG-C01", "Completeness", "Bookings", "No email and no phone on booking", len(B), (~B["email_raw_present"] & ~B["phone_raw_present"]).sum(), "High"),
    ("BKG-V01", "Validity", "Bookings", "Email present but invalid / typo domain", B["email_raw_present"].sum(), (B["email_raw_present"] & ~B["email_valid"]).sum(), "Medium"),
    ("BKG-I01", "Integrity", "Bookings", "Loyalty ID not found in loyalty master (orphan)", B["loyalty_id"].notna().sum(), B["loyalty_id_orphan"].sum(), "High"),
    ("BKG-S01", "Consistency", "Bookings", "Contact is a shared agency / travel-desk identifier", len(B), bk_shared.sum(), "Medium"),
    ("BKG-L01", "Linkage", "Bookings", "Booking cannot be linked to an identified customer", len(B), (~B["has_key"]).sum(), "High"),
    ("DIG-L01", "Linkage", "Digital", "Anonymous device (no login / email)", len(D), (~D["has_key"]).sum(), "Medium"),
]
f_rules = pd.DataFrame(rules, columns=["rule_id", "dimension", "source", "rule", "records_checked", "records_failed", "severity"])
f_rules[["records_checked", "records_failed"]] = f_rules[["records_checked", "records_failed"]].astype(int)
f_rules["fail_pct"] = (f_rules["records_failed"] / f_rules["records_checked"]).round(4)

unl = B[~B["has_key"]].groupby("unlinked_reason").size().rename("bookings").reset_index()
unl["pct_of_unlinked"] = unl["bookings"] / unl["bookings"].sum()

kv = {
    "Bookings linked to identified customer %": (B["is_linked_identified"].mean(), "Linkage", "Bookings resolved to a customer via a usable identifier / total bookings"),
    "Bookings linked to loyalty member %": (B["is_linked_loyalty"].mean(), "Linkage", "Bookings whose customer has >=1 loyalty record / total bookings"),
    "Avg profile completeness % (identified)": (ident["completeness_score"].mean(), "Completeness", "Weighted share of 6 critical attributes populated AND valid, identified customers"),
    "Profiles >=90% complete %": ((ident["completeness_score"] >= .9).mean(), "Completeness", "Identified customers with completeness score >= 0.90"),
    "Loyalty duplicate rate % (exact-key)": (dup_records / len(L), "Uniqueness", "Loyalty records merged into another record by exact keys / loyalty records"),
    "Probable duplicate rate % (fuzzy, to review)": (len(fuzzy_members) / len(L), "Uniqueness", "Loyalty records in a fuzzy name+DOB candidate pair / loyalty records"),
    "Identified profiles refreshed in last 12m %": ((ident["days_since_signal"] <= 365).mean(), "Timeliness", "Identified customers with any signal (booking, digital, loyalty update) in 365 days"),
    "Loyalty records stale (>24m) %": (l_stale.mean(), "Timeliness", "Loyalty records not updated for more than 24 months"),
    "Orphan loyalty IDs on bookings %": (B["loyalty_id_orphan"].sum() / B["loyalty_id"].notna().sum(), "Integrity", "Booking loyalty IDs not found in loyalty master / bookings quoting an ID"),
    "Customers present in 2+ sources %": ((ident["source_count"] >= 2).mean(), "Integration", "Identified customers appearing in at least two source systems"),
}
f_kpi = pd.DataFrame([{"kpi_name": k, "dimension": d, "value": v, "target": TARGETS[k][0], "higher_is_better": TARGETS[k][1],
                       "definition": defn} for k, (v, d, defn) in kv.items()])


def rag(r):
    v, t, hb = r["value"], r["target"], r["higher_is_better"]
    if hb:
        return "Green" if v >= t else ("Amber" if v >= t * 0.85 else "Red")
    return "Green" if v <= t else ("Amber" if v <= t * 1.5 else "Red")


f_kpi["status"] = f_kpi.apply(rag, axis=1)

truth = read("ground_truth.csv")
R = pd.concat([L[["source", "source_key", "customer_id", "has_key"]], B[["source", "source_key", "customer_id", "has_key"]],
               D[["source", "source_key", "customer_id", "has_key"]]])
T = R.merge(truth, left_on=["source", "source_key"], right_on=["source", "record_key"])


def pairs(s):
    return int((s * (s - 1) // 2).sum())


def prf(T_):
    tp = pairs(T_.groupby(["customer_id", "true_person_id"]).size())
    pr, tr = pairs(T_.groupby("customer_id").size()), pairs(T_.groupby("true_person_id").size())
    return {"precision": tp / pr, "recall": tp / tr, "true_pairs": tr, "predicted_pairs": pr, "correct_pairs": tp}


lt = T[T["source"] == "LOYALTY"]
dup_truth = lt.groupby("true_person_id")["source_key"].apply(list)
dup_truth = dup_truth[dup_truth.str.len() > 1]
cid = L.set_index("member_id")["customer_id"]
found_exact = sum(cid[v[0]] == cid[v[1]] for v in dup_truth)
fz = {frozenset(p) for p in zip(fuzzy["member_id_a"], fuzzy["member_id_b"])}
found_fuzzy = sum((cid[v[0]] != cid[v[1]]) and (frozenset(v[:2]) in fz) for v in dup_truth)
fuzzy_true = sum(frozenset(p) in {frozenset(v[:2]) for v in dup_truth} for p in fz)
evaluation = {
    "all_records": prf(T), "keyed_records_only": prf(T[T["has_key"]]),
    "loyalty_duplicates": {"true_duplicate_members": int(len(dup_truth)), "found_by_exact_keys": int(found_exact),
                           "found_by_fuzzy_review": int(found_fuzzy),
                           "missed": int(len(dup_truth) - found_exact - found_fuzzy),
                           "fuzzy_pairs_flagged": int(len(fz)), "fuzzy_precision": fuzzy_true / max(len(fz), 1)},
    "note": "Ground truth is synthetic. Unkeyed records (agency bookings, anonymous devices) cannot be linked by design.",
}
(DOCS / "matching_evaluation.json").write_text(json.dumps(evaluation, indent=2, default=float))

dim_customer = C.copy()
for c in ("dob", "last_booking_date", "loyalty_last_updated", "last_digital_event", "last_signal_date"):
    dim_customer[c] = pd.to_datetime(dim_customer[c]).dt.date
dim_customer = dim_customer.drop(columns=["first_name", "last_name", "email", "phone"]).assign(
    country=C["country"], has_email_domain=C["email"].str.split("@").str[-1])  # PII minimised: no names/emails/phones in the model
dim_customer["age_band"] = pd.cut((AS_OF - C["dob"]).dt.days / 365.25, [0, 25, 35, 45, 55, 65, 120],
                                  labels=["<25", "25-34", "35-44", "45-54", "55-64", "65+"], right=False).astype(object).fillna("Unknown")

fact_booking = pd.DataFrame({
    "booking_id": bk_raw["booking_id"], "customer_id": B["customer_id"], "booking_date": B["booking_date"].dt.date,
    "departure_date": pd.to_datetime(bk_raw["departure_date"]).dt.date, "channel": bk_raw["channel"], "cabin": bk_raw["cabin"],
    "route": bk_raw["origin"] + "-" + bk_raw["destination"], "status": B["status"], "fare_eur": B["fare_eur"],
    "net_revenue_eur": B["net_revenue_eur"], "has_loyalty_id_on_booking": B["loyalty_id"].notna(),
    "loyalty_id_orphan": B["loyalty_id_orphan"], "has_email": B["email_raw_present"], "has_phone": B["phone_raw_present"],
    "match_basis": B["match_basis"], "link_status": B["link_status"], "unlinked_reason": B["unlinked_reason"],
    "is_linked_identified": B["is_linked_identified"].astype(int), "is_linked_loyalty": B["is_linked_loyalty"].astype(int)})

dim_date = pd.DataFrame({"date": pd.date_range("2024-01-01", AS_OF + pd.Timedelta(days=150))})
dim_date = dim_date.assign(year=dim_date["date"].dt.year, month_num=dim_date["date"].dt.month,
                           month_name=dim_date["date"].dt.strftime("%b"), year_month=dim_date["date"].dt.strftime("%Y-%m"),
                           quarter="Q" + dim_date["date"].dt.quarter.astype(str), date_key=dim_date["date"].dt.date)
dim_date = dim_date.drop(columns="date").rename(columns={"date_key": "date"})[["date", "year", "quarter", "month_num", "month_name", "year_month"]]

out(dim_customer, "dim_customer"); out(fact_booking, "fact_booking"); out(dim_date, "dim_date")
out(f_attr, "fact_dq_attribute"); out(f_rules, "fact_dq_rules"); out(f_fresh, "fact_source_freshness")
out(f_kpi, "fact_dq_kpi"); out(unl, "fact_unlinked_reasons"); out(fuzzy, "fact_duplicate_candidates")
for name, df in (("raw_loyalty", loy_raw), ("raw_bookings", bk_raw), ("raw_digital", dg_raw)):
    df.to_csv(PROC / f"{name}.csv", index=False)

pd.set_option("display.width", 200, "display.max_columns", 20)
print("\n=== KPI SUMMARY ===")
print(f_kpi[["kpi_name", "value", "target", "status"]].round(4).to_string(index=False))
print("\n=== MATCHING EVALUATION ===\n", json.dumps(evaluation, indent=2, default=float))
print("\nUnlinked reasons:\n", unl.round(3).to_string(index=False))
