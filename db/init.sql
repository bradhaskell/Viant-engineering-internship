-- Schemas
CREATE SCHEMA IF NOT EXISTS raw;
CREATE SCHEMA IF NOT EXISTS transformed;

-- raw.events: one row per ad event
CREATE TABLE IF NOT EXISTS raw.events (
    event_id      UUID          PRIMARY KEY DEFAULT gen_random_uuid(),
    timestamp     TIMESTAMPTZ   NOT NULL,
    event_type    VARCHAR(20)   NOT NULL CHECK (event_type IN ('impression', 'click', 'bid')),
    campaign_id   VARCHAR(50)   NOT NULL,
    advertiser_id VARCHAR(50)   NOT NULL,
    publisher_id  VARCHAR(50)   NOT NULL,
    content_type  VARCHAR(20)   NOT NULL CHECK (content_type IN ('ctv', 'mobile', 'desktop')),
    device_id     VARCHAR(100)  NOT NULL,
    device_type   VARCHAR(50)   NOT NULL,
    bid_price     NUMERIC(10,4) NOT NULL,
    geo_region    VARCHAR(50)   NOT NULL,
    created_at    TIMESTAMPTZ   NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_events_campaign_date
    ON raw.events (campaign_id, timestamp);
CREATE INDEX IF NOT EXISTS idx_events_timestamp
    ON raw.events (timestamp);

-- transformed.campaign_metrics: daily rollup per campaign
CREATE TABLE IF NOT EXISTS transformed.campaign_metrics (
    campaign_id     VARCHAR(50)   NOT NULL,
    date            DATE          NOT NULL,
    impressions     INTEGER       NOT NULL DEFAULT 0,
    clicks          INTEGER       NOT NULL DEFAULT 0,
    ctr             NUMERIC(8,4)  NOT NULL DEFAULT 0,
    total_spend     NUMERIC(12,4) NOT NULL DEFAULT 0,
    avg_bid_price   NUMERIC(10,4) NOT NULL DEFAULT 0,
    unique_devices  INTEGER       NOT NULL DEFAULT 0,
    ctv_impressions INTEGER       NOT NULL DEFAULT 0,
    updated_at      TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
    PRIMARY KEY (campaign_id, date)
);

-- transformed.hourly_stats: hourly time series per campaign
CREATE TABLE IF NOT EXISTS transformed.hourly_stats (
    campaign_id VARCHAR(50)   NOT NULL,
    hour        TIMESTAMPTZ   NOT NULL,
    impressions INTEGER       NOT NULL DEFAULT 0,
    clicks      INTEGER       NOT NULL DEFAULT 0,
    spend       NUMERIC(12,4) NOT NULL DEFAULT 0,
    PRIMARY KEY (campaign_id, hour)
);
