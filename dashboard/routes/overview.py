from collections import Counter
from datetime import datetime, timedelta, timezone

from flask import Blueprint, jsonify, render_template
from src.database import get_supabase


overview_bp = Blueprint("overview", __name__)

HISTORICAL_DAYS = 8


def get_local_timezone():
    return timezone(timedelta(hours=8))


def parse_timestamp(timestamp):
    if not timestamp:
        return None

    text = str(timestamp).strip()

    # Your Supabase timestamp clock value is already local/camera time.
    # Remove timezone suffixes so Python does not add another +8 hours.
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
        key = record.get("dedupe_key") or record.get("event_id") or record.get("id")

        if key in seen:
            continue

        seen.add(key)
        unique_records.append(record)

    return unique_records


def fetch_all_violations():
    supabase = get_supabase()
    records = []
    page_size = 1000
    offset = 0

    while True:
        response = (
            supabase.table("violations")
            .select("*")
            .order("timestamp", desc=False)
            .range(offset, offset + page_size - 1)
            .execute()
        )

        page = response.data if response and hasattr(response, "data") else []
        records.extend(page)

        if len(page) < page_size:
            break

        offset += page_size

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

    records = fetch_all_violations()

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
    location_counter = Counter()
    today_location_counter = Counter()
    location_device_map = {}
    first_today_dt = None

    for log in today_records:
        local_dt = log["_local_dt"]

        hourly_distribution[local_dt.hour] += 1
        hour_counter[local_dt.hour] += 1

        location = log.get("location") or "Unknown Location"
        location_counter[location] += 1
        today_location_counter[location] += 1

        if log.get("device_id"):
            location_device_map[location] = log.get("device_id")

        if first_today_dt is None or local_dt < first_today_dt:
            first_today_dt = local_dt

    comparison_text = "No change from yesterday"

    if total_yesterday > 0:
        pct_diff = ((total_today - total_yesterday) / total_yesterday) * 100

        if pct_diff > 0:
            comparison_text = f"{abs(pct_diff):.0f}% Higher than Yesterday"
        elif pct_diff < 0:
            comparison_text = f"{abs(pct_diff):.0f}% Lower than Yesterday"

    elif total_today > 0:
        comparison_text = "100% Higher than Yesterday"

    if hour_counter:
        peak_hour, peak_time_logged = hour_counter.most_common(1)[0]
        peak_time_str = format_peak_hour(peak_hour)
    else:
        peak_time_str = "No Data Yet"
        peak_time_logged = 0

    if location_counter:
        peak_location_str = location_counter.most_common(1)[0][0]
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
        "since_time": first_today_dt.strftime("%I:%M %p") if first_today_dt else "N/A",
        "peak_time": peak_time_str,
        "peak_time_logged": peak_time_logged,
        "peak_location": peak_location_str,
        "peak_date": now.strftime("%B %d, %Y"),
        "hourly_data": hourly_distribution,
        "trend_labels": [
            datetime.fromisoformat(date_key).strftime("%b %d")
            for date_key in trend_dates
        ],
        "trend_data": [daily_trend_map[date_key] for date_key in trend_dates],
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
        "peak_date": datetime.now(get_local_timezone()).strftime("%B %d, %Y"),
        "hourly_data": [0] * 24,
        "trend_labels": ["No Data"],
        "trend_data": [0],
        "recent_logs": [],
        "hotspots": [],
    }


@overview_bp.route("/overview/data")
def overview_data():
    try:
        return jsonify(build_overview_metrics())
    except Exception as e:
        print(f"[OVERVIEW DATA ERROR] {e}")
        return jsonify(empty_overview_metrics()), 500


@overview_bp.route("/overview")
def index():
    try:
        metrics = build_overview_metrics()
    except Exception as e:
        print(f"[OVERVIEW DATABASE SYSTEM FAILURE] {e}")
        metrics = empty_overview_metrics()

    return render_template("overview.html", **metrics)