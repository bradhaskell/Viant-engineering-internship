INSERT INTO transformed.hourly_stats (campaign_id, hour, impressions, clicks, spend)
SELECT
    campaign_id,
    DATE_TRUNC('hour', timestamp)                             AS hour,
    COUNT(*) FILTER (WHERE event_type = 'impression')         AS impressions,
    COUNT(*) FILTER (WHERE event_type = 'click')              AS clicks,
    ROUND(SUM(bid_price), 4)                                  AS spend
FROM raw.events
GROUP BY campaign_id, DATE_TRUNC('hour', timestamp)
ON CONFLICT (campaign_id, hour) DO UPDATE SET
    impressions = EXCLUDED.impressions,
    clicks      = EXCLUDED.clicks,
    spend       = EXCLUDED.spend;
