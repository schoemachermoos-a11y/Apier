import requests
import streamlit as st
from datetime import datetime, timezone, timedelta

SCHIPHOL_LOCATION_ID = "0-20000-0-06240"
COLLECTION = "10-minute-in-situ-meteorological-observations"
BASE = f"https://api.dataplatform.knmi.nl/edr/v1/collections/{COLLECTION}"

# Mondkapje: wind VAN oost (90°) t/m zuid (180°)
EAST_MIN = 90.0
SOUTH_MAX = 180.0

def get_token() -> str:
    token = st.secrets.get("KNMI_EDR_TOKEN")
    if not token:
        raise RuntimeError("KNMI_EDR_TOKEN ontbreekt. Zet die als environment variable in PowerShell.")
    return token

def mask_required(dd: float | None) -> bool:
    if dd is None or dd <= 0:
        return False
    return EAST_MIN <= dd <= SOUTH_MAX

@st.cache_data(ttl=30)
def get_latest_dd_and_measured_time(location_id: str, lookback_hours: int = 6):
    headers = {"Authorization": get_token()}

    retrieved_at = datetime.now(timezone.utc)
    now = retrieved_at
    start = now - timedelta(hours=lookback_hours)

    params = {
        "datetime": f"{start.isoformat().replace('+00:00','Z')}/{now.isoformat().replace('+00:00','Z')}",
        "parameter-name": "dd",
    }

    r = requests.get(f"{BASE}/locations/{location_id}", params=params, headers=headers, timeout=30)
    r.raise_for_status()
    cov = r.json()

    coverages = cov.get("coverages", [])
    if not coverages:
        return None, None, retrieved_at

    for c in reversed(coverages):
        ranges = c.get("ranges", {}) or {}
        dd_range = ranges.get("dd") or {}
        values = dd_range.get("values") or dd_range.get("data") or []

        domain = c.get("domain", {}) or {}
        axes = domain.get("axes", {}) or {}
        t_axis = axes.get("t", {}) or {}
        times = t_axis.get("values") or []

        if not values or not times:
            continue

        last_i = min(len(values), len(times)) - 1
        for i in range(last_i, -1, -1):
            v = values[i]
            if v is None:
                continue
            measured_at = datetime.fromisoformat(times[i].replace("Z", "+00:00"))
            return float(v), measured_at, retrieved_at

    return None, None, retrieved_at

st.set_page_config(page_title="Schiphol Mondkapje Monitor", layout="centered")
st.title("Schiphol Mondkapje Monitor")
st.caption("Mondkapje alleen bij windrichting van **Oost (90°)** t/m **Zuid (180°)**.")

with st.sidebar:
    auto_refresh = st.toggle("Auto-refresh", value=True)
    refresh_seconds = st.slider("Ververs elke (seconden)", 10, 600, 60, step=10)
    lookback_hours = st.slider("Lookback (uren)", 1, 24, 6)

if auto_refresh:
    st.markdown(f"<meta http-equiv='refresh' content='{refresh_seconds}'>", unsafe_allow_html=True)

dd, measured_at, retrieved_at = get_latest_dd_and_measured_time(SCHIPHOL_LOCATION_ID, lookback_hours)

required = mask_required(dd)
status_text = "Dringend advies: Mondkapje dragen in rode gebieden" if required else "Dringend advies: Mondkapje dragen in rode gebieden"
emoji = "😷" if required else "✅"

st.markdown(
    f"""
    <div style="padding:18px;border-radius:16px;color:white;
                font-size:34px;font-weight:800;text-align:center;
                background:{'#d32f2f' if required else '#2e7d32'};">
        {emoji} {status_text}
    </div>
    """,
    unsafe_allow_html=True,
)

col1, col2 = st.columns(2)
col1.metric("Windrichting (dd)", "—" if dd is None else f"{dd:.0f}°")
col2.metric("Station", "Schiphol Airport")

if required:
    st.image("begane_grond_rood.png")
    st.image("dak_rood.png")
else:
    st.image("begane_grond_groen.png")
    st.image("dak_groen.png")

st.subheader("Tijdstempels")
st.write(f"**Ophaalmoment:** {retrieved_at.astimezone():%Y-%m-%d %H:%M:%S %Z}")
st.write(f"**Meetmoment KNMI:** {measured_at.astimezone():%Y-%m-%d %H:%M:%S %Z}" if measured_at else "**Meetmoment KNMI:** onbekend")




