from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
PROC = ROOT / "data" / "processed"
PBI = ROOT / "powerbi" / "data"
DOCS = ROOT / "docs"
for _p in (RAW, PROC, PBI, DOCS):
    _p.mkdir(parents=True, exist_ok=True)

SEED = 42
AS_OF = pd.Timestamp("2026-11-05")          
SHARED_ID_MIN_SURNAMES = 3     
FUZZY_NAME_THRESHOLD = 0.85    

PROFILE_WEIGHTS = {
    "first_name": 0.10, "last_name": 0.10,
    "email": 0.25, "phone": 0.20, "dob": 0.15, "country": 0.20,
}
COMPLETENESS_BANDS = [(0.90, "Complete"), (0.70, "Good"), (0.40, "Partial"), (0.0, "Poor")]

ACTIVE_WINDOW_DAYS = 365       
VALUE_WINDOW_DAYS = 730       
VALUE_TIERS = [(1000, "High"), (300, "Medium"), (0.01, "Low")]   
FRESH_FRESH_DAYS = 90          
FRESH_AGEING_DAYS = 365       
STALE_PROFILE_DAYS = 730       

TARGETS = {
    "Bookings linked to identified customer %": (0.90, True),
    "Bookings linked to loyalty member %": (0.45, True),
    "Avg profile completeness % (identified)": (0.85, True),
    "Profiles >=90% complete %": (0.50, True),
    "Loyalty duplicate rate % (exact-key)": (0.02, False),
    "Probable duplicate rate % (fuzzy, to review)": (0.01, False),
    "Identified profiles refreshed in last 12m %": (0.70, True),
    "Loyalty records stale (>24m) %": (0.15, False),
    "Orphan loyalty IDs on bookings %": (0.005, False),
    "Customers present in 2+ sources %": (0.40, True),
}
