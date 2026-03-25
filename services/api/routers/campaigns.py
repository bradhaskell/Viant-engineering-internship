from fastapi import APIRouter, Depends, HTTPException
from ..db import get_db

router = APIRouter(prefix="/campaigns", tags=["campaigns"])


@router.get("")
def list_campaigns(conn=Depends(get_db)):
    """List all campaigns with summary metrics."""
    with conn.cursor() as cur:
        cur.execute("""
            SELECT
                campaign_id,
                SUM(impressions)                                           AS total_impressions,
                SUM(clicks)                                                AS total_clicks,
                ROUND(
                    SUM(clicks)::NUMERIC / NULLIF(SUM(impressions), 0), 4
                )                                                          AS overall_ctr,
                ROUND(SUM(total_spend), 2)                                 AS total_spend
            FROM transformed.campaign_metrics
            GROUP BY campaign_id
            ORDER BY campaign_id
        """)
        return cur.fetchall()


@router.get("/{campaign_id}")
def get_campaign(campaign_id: str, conn=Depends(get_db)):
    """Full metrics for a single campaign across all dates."""
    with conn.cursor() as cur:
        cur.execute("""
            SELECT
                campaign_id,
                MIN(date)                                                      AS start_date,
                MAX(date)                                                      AS end_date,
                SUM(impressions)                                               AS impressions,
                SUM(clicks)                                                    AS clicks,
                ROUND(
                    SUM(clicks)::NUMERIC / NULLIF(SUM(impressions), 0), 4
                )                                                              AS ctr,
                ROUND(SUM(total_spend), 2)                                     AS total_spend,
                ROUND(AVG(avg_bid_price), 4)                                   AS avg_daily_bid_price,
                SUM(unique_devices)                                            AS total_device_days,
                SUM(ctv_impressions)                                           AS ctv_impressions
            FROM transformed.campaign_metrics
            WHERE campaign_id = %s
            GROUP BY campaign_id
        """, (campaign_id,))
        row = cur.fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail=f"Campaign '{campaign_id}' not found")
    return row


@router.get("/{campaign_id}/hourly")
def get_campaign_hourly(campaign_id: str, conn=Depends(get_db)):
    """Hourly time-series data for a campaign."""
    with conn.cursor() as cur:
        cur.execute("""
            SELECT hour, impressions, clicks, spend
            FROM transformed.hourly_stats
            WHERE campaign_id = %s
            ORDER BY hour
        """, (campaign_id,))
        rows = cur.fetchall()
    if not rows:
        raise HTTPException(status_code=404, detail=f"No hourly data for '{campaign_id}'")
    return rows
