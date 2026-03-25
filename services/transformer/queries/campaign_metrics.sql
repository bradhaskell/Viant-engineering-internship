INSERT INTO transformed.campaign_metrics (
    campaign_id, date, impressions, clicks, ctr,
    total_spend, avg_bid_price, unique_devices, ctv_impressions, updated_at
)
SELECT
    campaign_id,
    DATE(timestamp)                                                                 AS date,
    COUNT(*) FILTER (WHERE event_type = 'impression')                               AS impressions,
    COUNT(*) FILTER (WHERE event_type = 'click')                                    AS clicks,
    ROUND(
        COUNT(*) FILTER (WHERE event_type = 'click')::NUMERIC /
        NULLIF(COUNT(*) FILTER (WHERE event_type = 'impression'), 0),
        4
    )                                                                               AS ctr,
    ROUND(SUM(bid_price), 4)                                                        AS total_spend,
    ROUND(AVG(bid_price), 4)                                                        AS avg_bid_price,
    COUNT(DISTINCT device_id)                                                       AS unique_devices,
    COUNT(*) FILTER (WHERE event_type = 'impression' AND content_type = 'ctv')      AS ctv_impressions,
    NOW()                                                                           AS updated_at
FROM raw.events
GROUP BY campaign_id, DATE(timestamp)
ON CONFLICT (campaign_id, date) DO UPDATE SET
    impressions     = EXCLUDED.impressions,
    clicks          = EXCLUDED.clicks,
    ctr             = EXCLUDED.ctr,
    total_spend     = EXCLUDED.total_spend,
    avg_bid_price   = EXCLUDED.avg_bid_price,
    unique_devices  = EXCLUDED.unique_devices,
    ctv_impressions = EXCLUDED.ctv_impressions,
    updated_at      = EXCLUDED.updated_at;
