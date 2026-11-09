"""Cleaning / standardisation helpers shared by the generator and the pipeline."""
import re
import unicodedata
import pandas as pd

NULL_TOKENS = {"", "n/a", "na", "null", "none", "unknown", "-", "?", "tbd", "nan"}
EMAIL_RE = re.compile(r"^[a-z0-9._%+\-]+@[a-z0-9\-]+(\.[a-z0-9\-]+)*\.[a-z]{2,}$")
TYPO_DOMAINS = {"gmial.com", "gmail.con", "gmal.com", "hotmial.com", "outlok.com", "yaho.com"}
PHONE_PLACEHOLDERS = {"0000000000", "1234567890", "1111111111", "358000000000"}
ISO2 = {"FI", "SE", "DE", "GB", "US", "EE", "NO", "FR", "ES", "PL"}
COUNTRY_NAMES = {
    "finland": "FI", "suomi": "FI", "sweden": "SE", "sverige": "SE", "germany": "DE", "deutschland": "DE",
    "united kingdom": "GB", "uk": "GB", "united states": "US", "usa": "US", "estonia": "EE",
    "norway": "NO", "france": "FR", "spain": "ES", "poland": "PL",
}
DOB_PLACEHOLDERS = {pd.Timestamp("1900-01-01"), pd.Timestamp("1970-01-01")}


def clean_null(x):
    """Return None for NaN / placeholder tokens, otherwise the stripped string."""
    if x is None or (isinstance(x, float) and pd.isna(x)):
        return None
    s = str(x).strip()
    return None if s.lower() in NULL_TOKENS else s


def fold(x):
    """Accent-fold + lowercase + letters only (used for names and match keys)."""
    x = clean_null(x)
    if x is None:
        return None
    s = unicodedata.normalize("NFKD", x).encode("ascii", "ignore").decode().lower()
    s = re.sub(r"[^a-z]+", " ", s).strip()
    return s or None


def norm_email(x):
    """-> (normalised_email or None, is_valid)"""
    s = clean_null(x)
    if s is None:
        return None, False
    s = s.lower().replace("googlemail.com", "gmail.com")
    ok = bool(EMAIL_RE.match(s)) and s.split("@")[-1] not in TYPO_DOMAINS
    return s, ok


def norm_phone(x):
    """-> (digits-only international number or None, is_valid). Finnish national format assumed for leading 0."""
    s = clean_null(x)
    if s is None:
        return None, False
    digits = re.sub(r"\D", "", s)
    if not digits:
        return None, False
    if s.startswith("+"):
        pass
    elif digits.startswith("00"):
        digits = digits[2:]
    elif digits.startswith("0"):
        digits = "358" + digits[1:]
    ok = 8 <= len(digits) <= 15 and digits not in PHONE_PLACEHOLDERS and len(set(digits)) > 2
    return digits, ok


def norm_country(x):
    s = clean_null(x)
    if s is None:
        return None
    u = s.upper()
    if u in ISO2:
        return u
    return COUNTRY_NAMES.get(s.lower())


def parse_dob(series, as_of):
    """Parse ISO or dd.mm.yyyy dates. Returns (dob, populated_mask, valid_mask)."""
    s = series.map(clean_null)
    d = pd.to_datetime(s, format="%Y-%m-%d", errors="coerce").fillna(
        pd.to_datetime(s, format="%d.%m.%Y", errors="coerce"))
    populated = s.notna()
    age = (as_of - d).dt.days / 365.25
    valid = d.notna() & ~d.isin(DOB_PLACEHOLDERS) & age.between(0, 105)
    return d.where(valid), populated, valid
