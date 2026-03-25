import os
import requests
import pandas as pd
import plotly.express as px
import streamlit as st

API_URL = os.getenv("API_URL", "http://localhost:8000")

st.set_page_config(page_title="CTV Ad Analytics", layout="wide")
st.title("CTV Ad Analytics Dashboard")


@st.cache_data(ttl=30)
def fetch_campaigns():
    resp = requests.get(f"{API_URL}/campaigns", timeout=5)
    resp.raise_for_status()
    return resp.json()


@st.cache_data(ttl=30)
def fetch_campaign(campaign_id: str):
    resp = requests.get(f"{API_URL}/campaigns/{campaign_id}", timeout=5)
    resp.raise_for_status()
    return resp.json()


@st.cache_data(ttl=30)
def fetch_hourly(campaign_id: str):
    resp = requests.get(f"{API_URL}/campaigns/{campaign_id}/hourly", timeout=5)
    resp.raise_for_status()
    return resp.json()


# --- Sidebar: campaign selector ---
try:
    campaigns = fetch_campaigns()
except Exception as e:
    st.error(f"Cannot reach API at {API_URL}: {e}")
    st.stop()

if not campaigns:
    st.warning("No campaign data yet. The generator may still be seeding data.")
    st.stop()

campaign_ids = [c["campaign_id"] for c in campaigns]
selected = st.sidebar.selectbox("Select Campaign", campaign_ids)

# --- KPI Cards ---
try:
    metrics = fetch_campaign(selected)
except Exception as e:
    st.error(f"Failed to load campaign data for '{selected}': {e}")
    st.stop()
ctv_pct = (
    round(metrics["ctv_impressions"] / metrics["impressions"] * 100, 1)
    if metrics["impressions"]
    else 0
)

col1, col2, col3, col4, col5 = st.columns(5)
col1.metric("Impressions",  f"{metrics['impressions']:,}")
col2.metric("Clicks",       f"{metrics['clicks']:,}")
col3.metric("CTR",          f"{float(metrics['ctr']) * 100:.2f}%")
col4.metric("Total Spend",  f"${float(metrics['total_spend']):,.2f}")
col5.metric("CTV %",        f"{ctv_pct}%")

# --- Hourly Impressions Line Chart ---
st.subheader("Hourly Impressions")
try:
    hourly = fetch_hourly(selected)
    df = pd.DataFrame(hourly)
    df["hour"] = pd.to_datetime(df["hour"])
    fig = px.line(df, x="hour", y="impressions", title=f"{selected} — Hourly Impressions")
    st.plotly_chart(fig, use_container_width=True)
except requests.HTTPError as e:
    if e.response is not None and e.response.status_code == 404:
        st.info("No hourly data available yet.")
    else:
        st.error(f"Failed to load hourly data: {e}")
except Exception as e:
    st.error(f"Failed to load hourly data: {e}")

# --- CTV vs Non-CTV Donut Chart ---
st.subheader("CTV vs. Non-CTV Impressions")
ctv = metrics.get("ctv_impressions", 0)
non_ctv = metrics.get("impressions", 0) - ctv
if ctv + non_ctv > 0:
    fig2 = px.pie(
        names=["CTV", "Non-CTV"],
        values=[ctv, non_ctv],
        hole=0.5,
        title="Content Type Breakdown",
    )
    st.plotly_chart(fig2, use_container_width=True)
