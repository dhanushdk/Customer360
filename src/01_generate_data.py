import numpy as np
import pandas as pd
from config import AS_OF, RAW, SEED
from utils import fold

rng = np.random.default_rng(SEED)
N_PERSONS = 9000

FIRST = ["Matti", "Mikko", "Juha", "Timo", "Antti", "Jussi", "Petri", "Ville", "Lauri", "Eero", "Johanna", "Anna",
         "Maria", "Katarina", "Laura", "Sanna", "Emilia", "Aino", "Helena", "Elisabeth", "Sofia", "Oskar", "Erik",
         "Lars", "Anders", "Hannes", "Jonas", "Lukas", "Emma", "Olivia", "James", "Thomas", "Daniel", "Sarah",
         "Kristiina", "Päivi", "Tuomas", "Väinö", "Åsa", "Jörgen"]
LAST = ["Virtanen", "Korhonen", "Mäkinen", "Nieminen", "Mäkelä", "Hämäläinen", "Laine", "Heikkinen", "Koskinen",
        "Järvinen", "Lehtonen", "Lehtinen", "Saarinen", "Salminen", "Heinonen", "Niemi", "Heikkilä", "Kinnunen",
        "Salonen", "Turunen", "Åström", "Öhman", "Lindqvist", "Johansson", "Andersson", "Müller", "Schmidt", "Smith",
        "Brown", "Taylor", "Nielsen", "Hansen", "Kask", "Tamm", "Dubois", "Martin", "Garcia", "Rossi", "Kowalski",
        "Nguyen"]
NICK = {"Matti": "Matias", "Mikko": "Mikael", "Johanna": "Joanna", "Katarina": "Kata", "Elisabeth": "Liisa",
        "Anders": "Andreas", "Thomas": "Tom", "Daniel": "Dan", "James": "Jim", "Lukas": "Luke"}
CALLING = {"FI": "358", "SE": "46", "DE": "49", "GB": "44", "US": "1", "EE": "372", "NO": "47", "FR": "33",
           "ES": "34", "PL": "48"}
COUNTRY_P = [.55, .10, .07, .07, .05, .04, .03, .03, .03, .03]
COUNTRY_NAME = {"FI": "Finland", "SE": "Sweden", "DE": "Germany", "GB": "United Kingdom", "US": "USA",
                "EE": "Estonia", "NO": "Norway", "FR": "France", "ES": "Spain", "PL": "Poland"}
DOMAINS = ["gmail.com", "outlook.com", "hotmail.com", "yahoo.com", "icloud.com", "elisa.fi", "suomi24.fi", "luukku.com"]
DOMAIN_P = [.45, .15, .10, .08, .07, .07, .04, .04]
TYPOS = ["gmial.com", "gmail.con", "hotmial.com", "outlok.com"]
ROUTES = [("HEL", "LHR"), ("HEL", "ARN"), ("HEL", "CPH"), ("HEL", "FRA"), ("HEL", "AMS"), ("HEL", "JFK"),
          ("HEL", "BKK"), ("HEL", "NRT"), ("HEL", "BCN"), ("HEL", "OUL"), ("HEL", "RVN"), ("HEL", "TLL")]
AGENCIES = [(f"reservations@{n}.com", f"3589{rng.integers(1000000, 9999999)}") for n in
            ["nordic-travel", "sunwings-fi", "matkatoimisto", "globetrotters", "eurotrip", "polarjourneys",
             "lomamatkat", "airdeals-eu", "citybreaks", "traveldesk-oy"]]
CORPS = [(f"travel@{n}.fi", f"3585{rng.integers(1000000, 9999999)}") for n in
         ["kone-corp", "nordbank", "paperworks", "teleco", "shipyard", "medtech"]]


def maybe(p):
    return rng.random() < p


def typo(s):
    if len(s) < 4:
        return s
    i = int(rng.integers(1, len(s) - 1))
    return s[:i] + s[i + 1] + s[i] + s[i + 2:] if maybe(.5) else s[:i] + s[i + 1:]


def fmt_phone(p):
    style = int(rng.integers(0, 4))
    if style == 0:
        return "+" + p
    if style == 1 and p.startswith("358"):
        return "0" + p[3:5] + " " + p[5:]
    if style == 2:
        return "+" + p[:3] + " " + p[3:]
    return p


persons = pd.DataFrame({"person_id": np.arange(1, N_PERSONS + 1),
                        "first": rng.choice(FIRST, N_PERSONS), "last": rng.choice(LAST, N_PERSONS)})
persons["dob"] = AS_OF - pd.to_timedelta(rng.integers(18 * 365, 80 * 365, N_PERSONS), unit="D")
persons["country"] = rng.choice(list(CALLING), N_PERSONS, p=COUNTRY_P)


def make_phone(c):
    if c == "FI":
        return "358" + str(rng.choice(["40", "41", "44", "45", "50"])) + f"{rng.integers(0, 10**7):07d}"
    return CALLING[c] + f"{rng.integers(2 * 10**8, 10**9):09d}"


persons["phone"] = persons["country"].map(make_phone)
used, emails = set(), []
for f, l in zip(persons["first"], persons["last"]):
    base = f"{fold(f).replace(' ', '')}.{fold(l).replace(' ', '')}"
    dom = rng.choice(DOMAINS, p=DOMAIN_P)
    e = f"{base}{rng.integers(1, 99)}@{dom}" if maybe(.4) else f"{base}@{dom}"
    while e in used:
        e = f"{base}{rng.integers(1, 9999)}@{dom}"
    used.add(e)
    emails.append(e)
persons["email"] = emails
persons["is_member"] = rng.random(N_PERSONS) < 0.42
P = persons.set_index("person_id")

TIERS, TIER_P = ["Basic", "Silver", "Gold", "Platinum"], [.70, .18, .09, .03]


def messy_contact(first, last, email, phone, dob, country):
    """Apply source-system defects to one set of contact attributes."""
    # email
    if email is None or maybe(.06):
        email = str(rng.choice(["", "N/A", "null", "-"]))
    else:
        r = rng.random()
        if r < .05:
            email = email.upper()
        elif r < .08:
            email = f" {email} "
        elif r < .095:
            email = email.split("@")[0] + "@" + str(rng.choice(TYPOS))
    # phone
    if phone is None or maybe(.20):
        phone = str(rng.choice(["", "", "N/A", "0000000000"])) if maybe(.9) else "1234567890"
    else:
        phone = fmt_phone(phone)
    # dob
    if dob is None or maybe(.10):
        dob_s = str(rng.choice(["", "", "NULL"]))
    else:
        r = rng.random()
        if r < .01:
            dob_s = "1970-01-01"
        elif r < .015:
            dob_s = (AS_OF + pd.Timedelta(days=int(rng.integers(30, 900)))).strftime("%Y-%m-%d")
        elif r < .165:
            dob_s = dob.strftime("%d.%m.%Y")
        else:
            dob_s = dob.strftime("%Y-%m-%d")
    # country
    if country is None or maybe(.04):
        country_s = str(rng.choice(["", "unknown"]))
    else:
        country_s = COUNTRY_NAME[country] if maybe(.2) else country
    # names
    if maybe(.08):
        first, last = first.upper(), last.upper()
    if maybe(.02):
        last = last + " "
    return first, last, email, phone, dob_s, country_s


def loyalty_row(pid, member_id, variant="primary"):
    p = P.loc[pid]
    first, last, email, phone, dob, country = p["first"], p["last"], p["email"], p["phone"], p["dob"], p["country"]
    if variant == "dup_email":        
        first = NICK.get(first, first[:4])
        phone = None if maybe(.5) else phone
    elif variant == "dup_phone":      
        email = email.replace("@", ".old@")
    elif variant == "dup_fuzzy":      
        last = typo(last) if maybe(.6) else last
        first = typo(first) if last == p["last"] else first
        email = f"{fold(first).replace(' ', '')[:1]}{fold(last).replace(' ', '')}@hotmail.com"
        phone = None
    first, last, email, phone, dob_s, country_s = messy_contact(first, last, email, phone, dob, country)
    enrol = AS_OF - pd.Timedelta(days=int(rng.integers(30, 365 * 14)))
    upd = max(AS_OF - pd.Timedelta(days=int(rng.exponential(330))), enrol)
    return {"member_id": member_id, "first_name": first, "last_name": last, "email": email, "phone": phone,
            "date_of_birth": dob_s, "country": country_s, "tier": str(rng.choice(TIERS, p=TIER_P)),
            "enrolment_date": enrol.strftime("%Y-%m-%d"), "points_balance": int(rng.gamma(1.5, 6000)),
            "last_updated": upd.strftime("%Y-%m-%d"), "marketing_consent": str(rng.choice(["Y", "N"], p=[.6, .4]))}


members = persons.loc[persons["is_member"], "person_id"].to_numpy()
loy_rows, truth, member_ids = [], [], {}
mid = 10_000_000
for pid in members:
    mid += 1
    member_ids[pid] = [f"FP{mid}"]
    loy_rows.append(loyalty_row(pid, f"FP{mid}"))
    truth.append(("LOYALTY", f"FP{mid}", pid))
for pid in rng.choice(members, int(len(members) * 0.07), replace=False):
    variant = str(rng.choice(["dup_email", "dup_phone", "dup_fuzzy"], p=[.40, .25, .35]))
    mid += 1
    member_ids[pid].append(f"FP{mid}")
    loy_rows.append(loyalty_row(pid, f"FP{mid}", variant))
    truth.append(("LOYALTY", f"FP{mid}", pid))
loyalty = pd.DataFrame(loy_rows).sample(frac=1, random_state=SEED).reset_index(drop=True)
valid_member_ids = set(loyalty["member_id"])

CH = ["web", "app", "call_center", "travel_agency", "corporate"]
bk_rows, bnum = [], 20_000_000
for pid in persons["person_id"]:
    p = P.loc[pid]
    n = 1 + rng.poisson(5.5) if p["is_member"] else rng.poisson(1.8)
    for _ in range(n):
        bnum += 1
        ch = str(rng.choice(CH, p=[.35, .35, .05, .15, .10] if p["is_member"] else [.40, .15, .07, .28, .10]))
        first, last, email, phone = p["first"], p["last"], p["email"], p["phone"]
        generic = (ch == "travel_agency" and maybe(.75)) or (ch == "corporate" and maybe(.5))
        if generic:
            email, phone = (AGENCIES if ch == "travel_agency" else CORPS)[int(rng.integers(0, 10 if ch == "travel_agency" else 6))]
            phone = phone if maybe(.7) else ""
        else:
            p_email = {"web": .94, "app": .94, "call_center": .70}.get(ch, .80)
            email = email if maybe(p_email) else ""
            if email and maybe(.015):
                email = email.split("@")[0] + "@" + str(rng.choice(TYPOS))
            phone = fmt_phone(phone) if maybe(.55) else ""
        loyalty_id = ""
        if p["is_member"] and maybe(.75 if ch in ("web", "app") else .30):
            loyalty_id = member_ids[pid][int(rng.integers(0, len(member_ids[pid])))]
            if maybe(.015):
                loyalty_id = f"FP9{rng.integers(0, 10**7):07d}"      
        if maybe(.25):
            first, last = first.upper(), last.upper()
        if maybe(.30):
            first, last = fold(first).upper(), fold(last).upper()
        booked = AS_OF - pd.Timedelta(days=int(rng.integers(1, 1030)))
        dep = booked + pd.Timedelta(days=int(rng.integers(3, 120)))
        orig, dest = ROUTES[int(rng.integers(0, len(ROUTES)))]
        fare = float(np.clip(rng.lognormal(5.4, .6), 40, 3000).round(2))
        cancelled = maybe(.06)
        status = "Cancelled" if cancelled else ("Flown" if dep <= AS_OF else "Confirmed")
        bk_rows.append({"booking_id": f"BK{bnum}", "booking_date": booked.strftime("%Y-%m-%d"),
                        "departure_date": dep.strftime("%Y-%m-%d"), "origin": orig, "destination": dest,
                        "channel": ch, "cabin": str(rng.choice(["Economy", "Economy Comfort", "Business"], p=[.82, .10, .08])),
                        "fare_eur": fare, "status": status, "loyalty_id": loyalty_id,
                        "contact_first_name": first, "contact_last_name": last, "contact_email": email,
                        "contact_phone": phone})
        truth.append(("BOOKING", f"BK{bnum}", pid))
bookings = pd.DataFrame(bk_rows).sample(frac=1, random_state=SEED).reset_index(drop=True)

EVENTS = ["page_view", "search", "login", "app_open", "booking_start", "newsletter_signup", "checkout_start"]
EVENT_P = [.38, .22, .08, .15, .07, .03, .07]
ev_rows, enum_, dnum = [], 0, 0
for pid in persons["person_id"]:
    p = P.loc[pid]
    if not maybe(.80 if p["is_member"] else .40):
        continue
    for _ in range(1 + int(maybe(.3))):
        dnum += 1
        device = f"DV{dnum:07d}"
        truth.append(("DIGITAL", device, pid))
        platform = str(rng.choice(["ios", "android", "web"], p=[.3, .25, .45]))
        email_device = (not p["is_member"] and maybe(.15)) or (p["is_member"] and maybe(.10))
        for _ in range(1 + rng.poisson(7)):
            enum_ += 1
            et = str(rng.choice(EVENTS, p=EVENT_P))
            ts = AS_OF - pd.Timedelta(minutes=int(rng.beta(1, 2.2) * 730 * 1440))
            m_id = ""
            if p["is_member"] and (et == "login" or (platform != "web" and maybe(.5))):
                m_id = member_ids[pid][int(rng.integers(0, len(member_ids[pid])))]
            em = p["email"] if (email_device and et in ("newsletter_signup", "checkout_start")) else ""
            ev_rows.append({"event_id": f"EV{enum_:08d}", "device_id": device, "member_id": m_id, "email": em,
                            "event_type": et, "event_ts": ts.strftime("%Y-%m-%d %H:%M:%S"), "platform": platform})
digital = pd.DataFrame(ev_rows)

loyalty.to_csv(RAW / "loyalty_members.csv", index=False)
bookings.to_csv(RAW / "bookings.csv", index=False)
digital.to_csv(RAW / "digital_events.csv", index=False)
pd.DataFrame(truth, columns=["source", "record_key", "true_person_id"]).to_csv(RAW / "ground_truth.csv", index=False)
print(f"persons={N_PERSONS:,}  loyalty={len(loyalty):,}  bookings={len(bookings):,}  digital_events={len(digital):,}  "
      f"devices={dnum:,}")
