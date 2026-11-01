
from collections import Counter
from datetime import datetime, timedelta, timezone

from flask import Blueprint, jsonify, render_template
from src.database import get_supabase
from dashboard.auth_utils import login_required

overview_bp = Blueprint("overview", __name__)

HISTORICAL_DAYS = 8
PAGE_SIZE = 1000


def get_local_timezone():
    return timezone(timedelta(hours=8))


def parse_timestamp(timestamp):
    if not timestamp:
        return None

    text = str(timestamp).strip()

    # Preserve the existing camera/local-time interpretation.
    if text.endswith("Z"):
        text = text[:-1]

    if len(text) > 19:
        text = text[:19]

    parsed = datetime.fromisoformat(text)
    return parsed.replace(tzinfo=get_local_timezone())


def dedupe_records(records):
    seen = set()
    unique_records = []

    for record in records:
        record_id = record.get("id")

        # Keep records without an ID rather than accidentally discarding them.
        if record_id is None:
            unique_records.append(record)
            continue

        if record_id not in seen:
            seen.add(record_id)
            unique_records.append(record)

    return unique_records


def fetch_recent_violations(start_date, end_date):
    """
    Fetch records from start_date inclusive
    to end_date exclusive.

    Dates use the existing camera/local-time interpretation.
    """

    supabase = get_supabase()

    start_timestamp = f"{start_date.isoformat()}T00:00:00"
    end_timestamp = f"{end_date.isoformat()}T00:00:00"

    records = []
    offset = 0

    while True:
        response = (
            supabase.table("violations")
            .select("id,timestamp,location,device_id")
            .gte("timestamp", start_timestamp)
            .lt("timestamp", end_timestamp)
            .order("timestamp", desc=False)
            .range(offset, offset + PAGE_SIZE - 1)
            .execute()
        )

        batch = response.data or []
        records.extend(batch)

        if len(batch) < PAGE_SIZE:
            break

        offset += PAGE_SIZE

    return dedupe_records(records)


def format_peak_hour(hour):
    start_hour = hour % 12 or 12
    end_raw = (hour + 1) % 24
    end_hour = end_raw % 12 or 12
    end_ampm = "A.M" if end_raw < 12 else "P.M"

    return f"{start_hour}:00 - {end_hour}:00 {end_ampm}"


def build_overview_metrics():
    local_tz = get_local_timezone()
    now = datetime.now(local_tz)

    today = now.date()
    yesterday = today - timedelta(days=1)
    trend_start_date = today - timedelta(days=HISTORICAL_DAYS - 1)

    # Retrieve only the records needed by the dashboard.
    records = fetch_recent_violations(
        trend_start_date,
        today + timedelta(days=1)
    )

    today_records = []
    yesterday_records = []
    trend_records = []

    for log in records:
        try:
            local_dt = parse_timestamp(log.get("timestamp"))

            if local_dt is None:
                continue

            log["_local_dt"] = local_dt
            log_date = local_dt.date()

            if log_date == today:
                today_records.append(log)

            if log_date == yesterday:
                yesterday_records.append(log)

            if trend_start_date <= log_date <= today:
                trend_records.append(log)

        except Exception as e:
            print(f"[OVERVIEW TIMESTAMP PARSE ERROR] {e}")

    total_today = len(today_records)
    total_yesterday = len(yesterday_records)

    hourly_distribution = [0] * 24
    hour_counter = Counter()
    today_location_counter = Counter()
    location_device_map = {}
    first_today_dt = None

    for log in today_records:
        local_dt = log["_local_dt"]

        hourly_distribution[local_dt.hour] += 1
        hour_counter[local_dt.hour] += 1

        location = log.get("location") or "Unknown Location"
        today_location_counter[location] += 1

        if log.get("device_id"):
            location_device_map[location] = log.get("device_id")

        if first_today_dt is None or local_dt < first_today_dt:
            first_today_dt = local_dt

    comparison_text = "No change from yesterday"

    if total_yesterday > 0:
        pct_diff = (
            (total_today - total_yesterday) / total_yesterday
        ) * 100

        if pct_diff > 0:
            comparison_text = (
                f"{abs(pct_diff):.0f}% Higher than Yesterday"
            )
        elif pct_diff < 0:
            comparison_text = (
                f"{abs(pct_diff):.0f}% Lower than Yesterday"
            )

    elif total_today > 0:
        comparison_text = "100% Higher than Yesterday"

    if hour_counter:
        peak_hour, peak_time_logged = hour_counter.most_common(1)[0]
        peak_time_str = format_peak_hour(peak_hour)
    else:
        peak_time_str = "No Data Yet"
        peak_time_logged = 0

    if today_location_counter:
        peak_location_str = today_location_counter.most_common(1)[0][0]
    else:
        peak_location_str = "No Hotspots Detected"

    daily_trend_map = {
        (trend_start_date + timedelta(days=offset)).isoformat(): 0
        for offset in range(HISTORICAL_DAYS)
    }

    for log in trend_records:
        date_key = log["_local_dt"].date().isoformat()

        if date_key in daily_trend_map:
            daily_trend_map[date_key] += 1

    trend_dates = sorted(daily_trend_map.keys())

    today_hotspots = [
        {
            "date": today.isoformat(),
            "rank": rank,
            "location": location,
            "total_logs": total_logs,
            "device_id": location_device_map.get(location, "N/A"),
        }
        for rank, (location, total_logs) in enumerate(
            today_location_counter.most_common(),
            start=1,
        )
    ]

    return {
        "total_today": total_today,
        "comparison_text": comparison_text,
        "since_time": (
            first_today_dt.strftime("%I:%M %p")
            if first_today_dt else "N/A"
        ),
        "peak_time": peak_time_str,
        "peak_time_logged": peak_time_logged,
        "peak_location": peak_location_str,
        "peak_date": now.strftime("%B %d, %Y"),
        "hourly_data": hourly_distribution,
        "trend_labels": [
            datetime.fromisoformat(date_key).strftime("%b %d")
            for date_key in trend_dates
        ],
        "trend_data": [
            daily_trend_map[date_key]
            for date_key in trend_dates
        ],
        "recent_logs": list(reversed(today_records)),
        "hotspots": today_hotspots,
    }


def empty_overview_metrics():
    return {
        "total_today": 0,
        "comparison_text": "Data unavailable",
        "since_time": "N/A",
        "peak_time": "Unavailable",
        "peak_time_logged": 0,
        "peak_location": "Unavailable",
        "peak_date": datetime.now(
            get_local_timezone()
        ).strftime("%B %d, %Y"),
        "hourly_data": [0] * 24,
        "trend_labels": ["No Data"],
        "trend_data": [0],
        "recent_logs": [],
        "hotspots": [],
    }


@overview_bp.route("/overview/data")
@login_required
def overview_data():
    try:
        return jsonify(build_overview_metrics())

    except Exception:
        import logging
        logging.exception("Overview data retrieval failed.")
        return jsonify(empty_overview_metrics()), 500


@overview_bp.route("/overview")
@login_required
def index():
    try:
        metrics = build_overview_metrics()

    except Exception:
        import logging
        logging.exception("Overview dashboard loading failed.")
        metrics = empty_overview_metrics()

    return render_template("overview.html", **metrics)
