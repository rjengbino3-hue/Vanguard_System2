
from flask import Blueprint, render_template, request, jsonify
from datetime import datetime, timedelta, timezone
from src.database import get_supabase
from dashboard.auth_utils import login_required
import logging

trend_metrics_bp = Blueprint("trend_metrics", __name__)

# The project operates in Philippine local time.
PH_TIMEZONE = timezone(timedelta(hours=8))

# Retrieve records in manageable batches.
PAGE_SIZE = 500


def get_current_local_date():
    return datetime.now(PH_TIMEZONE).date()


def get_week_range(target_week):
    """
    Convert an HTML ISO week value (YYYY-Www)
    into its Monday start date and following Monday.
    """
    try:
        year_str, week_str = target_week.split("-W")
        iso_year = int(year_str)
        iso_week = int(week_str)

        week_start = datetime.fromisocalendar(
            iso_year, iso_week, 1
        ).date()

        week_end = week_start + timedelta(days=7)

        return week_start, week_end

    except (ValueError, TypeError):
        raise ValueError("Invalid week format. Please select a valid week.")


def fetch_records_for_range(start_date, end_date):
    """
    Retrieve only timestamp records within the requested date range.
    Uses pagination so results are not limited to one Supabase page.

    Date boundaries are UTC to preserve the existing behavior of
    interpreting the first 10 timestamp characters as the calendar date.
    """
    supabase = get_supabase()

    start_timestamp = (
        f"{start_date.isoformat()}T00:00:00+00:00"
    )
    end_timestamp = (
        f"{end_date.isoformat()}T00:00:00+00:00"
    )

    records = []
    offset = 0

    while True:
        response = (
            supabase.table("violations")
            .select("timestamp")
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

    return records


def build_hourly_data(records):
    """Count violations in each hour of the selected date."""
    hourly_distribution = [0] * 24

    for record in records:
        timestamp = record.get("timestamp")

        if not timestamp or len(timestamp) < 13:
            continue

        try:
            hour = int(str(timestamp)[11:13])

            if 0 <= hour < 24:
                hourly_distribution[hour] += 1

        except (ValueError, TypeError):
            logging.warning(
                "Skipping record with invalid timestamp: %s",
                timestamp
            )

    return hourly_distribution


def build_weekly_data(records, week_start):
    """Count violations for each day of the selected ISO week."""
    daily_counts = {}

    # Prepopulate all seven days with zero.
    for day_offset in range(7):
        current_day = week_start + timedelta(days=day_offset)
        daily_counts[current_day.isoformat()] = 0

    for record in records:
        timestamp = record.get("timestamp")

        if not timestamp or len(timestamp) < 10:
            continue

        try:
            date_str = str(timestamp)[:10]

            if date_str in daily_counts:
                daily_counts[date_str] += 1

        except (ValueError, TypeError):
            logging.warning(
                "Skipping record with invalid timestamp: %s",
                timestamp
            )

    labels = sorted(daily_counts.keys())
    counts = [daily_counts[day] for day in labels]

    return labels, counts


@trend_metrics_bp.route("/")
@trend_metrics_bp.route("")
@login_required
def index():
    # Render the page only. Do not retrieve violation records here.
    today = get_current_local_date()

    return render_template(
        "trend_metrics.html",
        hourly_data=[0] * 24,
        trend_labels=[today.isoformat()],
        trend_data=[0],
        default_date=today.isoformat()
    )


@trend_metrics_bp.route("/data")
@login_required
def get_filtered_data():
    try:
        date_param = request.args.get("date", "").strip()
        week_param = request.args.get("week", "").strip()

        # Use today's date if no date was supplied.
        if date_param:
            target_date = datetime.strptime(
                date_param, "%Y-%m-%d"
            ).date()
        else:
            target_date = get_current_local_date()

        # Validate the selected week.
        if week_param:
            week_start, week_end = get_week_range(week_param)
        else:
            # Default to the current ISO week.
            current_date = get_current_local_date()
            week_start = current_date - timedelta(
                days=current_date.weekday()
            )
            week_end = week_start + timedelta(days=7)

        # Query 1: Only the selected date for the hourly chart.
        hourly_records = fetch_records_for_range(
            target_date,
            target_date + timedelta(days=1)
        )

        # Query 2: Only the selected week for the daily chart.
        weekly_records = fetch_records_for_range(
            week_start,
            week_end
        )

        hourly_distribution = build_hourly_data(hourly_records)

        sorted_dates, sorted_daily_counts = build_weekly_data(
            weekly_records,
            week_start
        )

        return jsonify({
            "hourly_data": hourly_distribution,
            "trend_labels": sorted_dates,
            "trend_data": sorted_daily_counts
        })

    except ValueError as error:
        return jsonify({
            "error": str(error)
        }), 400

    except Exception:
        logging.exception(
            "Failed to retrieve Trend Metrics data."
        )

        return jsonify({
            "error": "Unable to retrieve metrics. Please try again."
        }), 500
