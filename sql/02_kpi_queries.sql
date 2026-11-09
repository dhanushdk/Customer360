
SELECT COUNT(*)                                         AS bookings,
       SUM(is_linked_identified)                        AS linked_identified,
       ROUND(AVG(is_linked_identified),4)               AS pct_linked_identified,
       ROUND(AVG(is_linked_loyalty),4)                  AS pct_linked_loyalty
FROM fact_booking;

SELECT channel,
       COUNT(*)                            AS bookings,
       ROUND(AVG(is_linked_identified),4)  AS pct_linked_identified,
       ROUND(AVG(is_linked_loyalty),4)     AS pct_linked_loyalty
FROM fact_booking
GROUP BY channel
ORDER BY pct_linked_identified;

SELECT SUBSTR(booking_date,1,7) AS year_month,
       COUNT(*)                           AS bookings,
       ROUND(AVG(is_linked_identified),4) AS pct_linked_identified
FROM fact_booking
GROUP BY SUBSTR(booking_date,1,7)
ORDER BY 1;

SELECT COUNT(*)                                              AS identified_customers,
       ROUND(AVG(completeness_score),4)                      AS avg_completeness,
       ROUND(AVG(CASE WHEN completeness_score >= 0.9 THEN 1.0 ELSE 0 END),4) AS pct_ge_90
FROM dim_customer
WHERE customer_type = 'Identified';

SELECT completeness_band, COUNT(*) AS customers,
       ROUND(1.0*COUNT(*)/SUM(COUNT(*)) OVER (),4) AS pct
FROM dim_customer
WHERE customer_type = 'Identified'
GROUP BY completeness_band
ORDER BY MIN(completeness_score) DESC;

SELECT freshness_status, COUNT(*) AS customers,
       ROUND(1.0*COUNT(*)/SUM(COUNT(*)) OVER (),4) AS pct
FROM dim_customer
WHERE customer_type = 'Identified'
GROUP BY freshness_status
ORDER BY MIN(days_since_signal);

SELECT ROUND(AVG(CASE WHEN days_since_signal <= 365 THEN 1.0 ELSE 0 END),4) AS pct_refreshed_12m
FROM dim_customer WHERE customer_type = 'Identified';

SELECT SUM(loyalty_records)                                   AS loyalty_records,
       SUM(loyalty_records - 1)                               AS duplicate_records,
       ROUND(1.0*SUM(loyalty_records - 1)/SUM(loyalty_records),4) AS duplicate_rate
FROM dim_customer
WHERE loyalty_records > 0;

SELECT SUM(has_loyalty_id_on_booking) AS bookings_with_id,
       SUM(loyalty_id_orphan)         AS orphan_ids,
       ROUND(1.0*SUM(loyalty_id_orphan)/SUM(has_loyalty_id_on_booking),4) AS orphan_rate
FROM fact_booking;

SELECT value_tier,
       COUNT(*)                                   AS customers,
       SUM(is_active)                             AS active_customers,
       ROUND(SUM(revenue_24m_eur),0)              AS revenue_24m_eur
FROM dim_customer
WHERE customer_type = 'Identified'
GROUP BY value_tier
ORDER BY MIN(CASE value_tier WHEN 'High' THEN 1 WHEN 'Medium' THEN 2 WHEN 'Low' THEN 3 ELSE 4 END);

WITH ranked AS (
  SELECT customer_id, revenue_24m_eur,
         NTILE(10) OVER (ORDER BY revenue_24m_eur DESC) AS decile
  FROM dim_customer
  WHERE customer_type = 'Identified' AND revenue_24m_eur > 0)
SELECT decile, COUNT(*) AS customers, ROUND(SUM(revenue_24m_eur),0) AS revenue_eur,
       ROUND(1.0*SUM(revenue_24m_eur)/SUM(SUM(revenue_24m_eur)) OVER (),4) AS share_of_revenue
FROM ranked GROUP BY decile ORDER BY decile;

SELECT missing_attributes, COUNT(*) AS customers
FROM dim_customer
WHERE customer_type = 'Identified' AND missing_attributes <> ''
GROUP BY missing_attributes
ORDER BY customers DESC
LIMIT 8;
