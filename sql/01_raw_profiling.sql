
SELECT 'loyalty_members' AS source, COUNT(*) AS records FROM raw_loyalty
UNION ALL SELECT 'bookings', COUNT(*) FROM raw_bookings
UNION ALL SELECT 'digital_events', COUNT(*) FROM raw_digital;

WITH t AS (
  SELECT
    CASE WHEN LOWER(TRIM(email))         IN ('','n/a','na','null','none','unknown','-','?','tbd') THEN 0 ELSE 1 END AS email_ok,
    CASE WHEN LOWER(TRIM(phone))         IN ('','n/a','na','null','none','unknown','-','?','tbd') THEN 0 ELSE 1 END AS phone_ok,
    CASE WHEN LOWER(TRIM(date_of_birth)) IN ('','n/a','na','null','none','unknown','-','?','tbd') THEN 0 ELSE 1 END AS dob_ok,
    CASE WHEN LOWER(TRIM(country))       IN ('','n/a','na','null','none','unknown','-','?','tbd') THEN 0 ELSE 1 END AS country_ok
  FROM raw_loyalty)
SELECT 'email'   AS attribute, COUNT(*) AS records, SUM(email_ok)   AS populated, ROUND(1.0*SUM(email_ok)/COUNT(*),4)   AS populated_pct FROM t
UNION ALL SELECT 'phone',   COUNT(*), SUM(phone_ok),   ROUND(1.0*SUM(phone_ok)/COUNT(*),4)   FROM t
UNION ALL SELECT 'dob',     COUNT(*), SUM(dob_ok),     ROUND(1.0*SUM(dob_ok)/COUNT(*),4)     FROM t
UNION ALL SELECT 'country', COUNT(*), SUM(country_ok), ROUND(1.0*SUM(country_ok)/COUNT(*),4) FROM t;

WITH e AS (
  SELECT LOWER(TRIM(email)) AS email_n, COUNT(*) AS n
  FROM raw_loyalty
  WHERE LOWER(TRIM(email)) LIKE '%@%'
  GROUP BY LOWER(TRIM(email))
  HAVING COUNT(*) > 1)
SELECT COUNT(*) AS emails_with_duplicates, COALESCE(SUM(n),0) AS records_involved FROM e;

SELECT COUNT(*) AS bookings_quoting_an_id,
       SUM(CASE WHEN l.member_id IS NULL THEN 1 ELSE 0 END) AS orphan_ids,
       ROUND(1.0*SUM(CASE WHEN l.member_id IS NULL THEN 1 ELSE 0 END)/COUNT(*),4) AS orphan_rate
FROM raw_bookings b
LEFT JOIN raw_loyalty l ON l.member_id = b.loyalty_id
WHERE TRIM(b.loyalty_id) <> '';

SELECT LOWER(TRIM(contact_email)) AS contact_email,
       COUNT(*) AS bookings,
       COUNT(DISTINCT UPPER(TRIM(contact_last_name))) AS distinct_surnames
FROM raw_bookings
WHERE contact_email LIKE '%@%'
GROUP BY LOWER(TRIM(contact_email))
HAVING COUNT(DISTINCT UPPER(TRIM(contact_last_name))) >= 6
ORDER BY bookings DESC
LIMIT 10;

SELECT channel,
       COUNT(*) AS bookings,
       SUM(CASE WHEN TRIM(contact_email)='' AND TRIM(contact_phone)='' THEN 1 ELSE 0 END) AS no_email_no_phone,
       ROUND(1.0*SUM(CASE WHEN TRIM(contact_email)='' AND TRIM(contact_phone)='' THEN 1 ELSE 0 END)/COUNT(*),4) AS pct
FROM raw_bookings
GROUP BY channel
ORDER BY pct DESC;
