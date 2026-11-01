
from flask import Blueprint, render_template, request, jsonify
from datetime import datetime, timedelta
from src.database import get_supabase
from dashboard.auth_utils import login_required
import logging

history_report_bp = Blueprint('history_report', __name__)

PAGE_SIZE = 500


@history_report_bp.route('/')
@login_required
def index():
    return render_template('history_reports.html')


@history_report_bp.route('/data')
@login_required
def get_report_data():
    try:
        selected_date = request.args.get('date', '').strip()

        if not selected_date:
            return jsonify({
                "success": False,
                "error": "Please select a date."
            }), 400

        target_date = datetime.strptime(
            selected_date, "%Y-%m-%d"
        ).date()

        previous_date = target_date - timedelta(days=1)

        # Retrieve only the selected date and previous date.
        start_timestamp = (
            f"{previous_date.isoformat()}T00:00:00+00:00"
        )
        end_timestamp = (
            f"{(target_date + timedelta(days=1)).isoformat()}T00:00:00+00:00"
        )

        supabase = get_supabase()

        records = []
        offset = 0

        while True:
            response = (
                supabase.table("violations")
                .select("timestamp,location,device_id")
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

        # Separate selected-day and previous-day records.
        current_logs = [
            log for log in records
            if log.get("timestamp", "")[:10] == selected_date
        ]

        previous_logs = [
            log for log in records
            if log.get("timestamp", "")[:10] == previous_date.isoformat()
        ]

        hourly_counts = [0] * 24
        location_counts = {}
        device_counts = {}

        for log in current_logs:
            timestamp = log.get("timestamp", "")

            if len(timestamp) >= 13:
                try:
                    hour = int(timestamp[11:13])
                    if 0 <= hour < 24:
                        hourly_counts[hour] += 1
                except (ValueError, TypeError):
                    continue

            location = log.get("location")
            if location:
                location_counts[location] = (
                    location_counts.get(location, 0) + 1
                )

            device_id = log.get("device_id")
            if device_id:
                device_counts[device_id] = (
                    device_counts.get(device_id, 0) + 1
                )

        peak_location = (
            max(location_counts, key=location_counts.get)
            if location_counts else "N/A"
        )

        peak_device = (
            max(device_counts, key=device_counts.get)
            if device_counts else "N/A"
        )

        peak_hour = max(range(24), key=lambda hour: hourly_counts[hour])
        peak_count = hourly_counts[peak_hour]

        previous_count = len(previous_logs)
        current_count = len(current_logs)

        if previous_count > 0:
            difference = current_count - previous_count
            percentage = round(
                (difference / previous_count) * 100
            )

            if percentage > 0:
                trend_text = f"{percentage}% Higher than yesterday"
                comparison_text = f"{percentage}% Higher than previous days"
                trend_class = "text-red-600 font-black text-xs mt-1"

            elif percentage < 0:
                trend_text = f"{abs(percentage)}% Lower than yesterday"
                comparison_text = f"{abs(percentage)}% Lower than previous days"
                trend_class = "text-green-600 font-black text-xs mt-1"

            else:
                trend_text = "Equal volume to yesterday"
                comparison_text = "Stable volumes detected"
                trend_class = "text-slate-500 font-black text-xs mt-1"

        elif current_count > 0:
            trend_text = "Initial recorded logs tracking"
            comparison_text = "No comparative records prior"
            trend_class = "text-red-600 font-black text-xs mt-1"

        else:
            trend_text = "No previous data"
            comparison_text = "0% vs Previous Day"
            trend_class = "text-red-600 font-black text-xs mt-1"

        return jsonify({
            "success": True,
            "total_count": current_count,
            "hourly_counts": hourly_counts,
            "peak_location": peak_location,
            "peak_device": peak_device,
            "peak_hour": peak_hour,
            "peak_count": peak_count,
            "previous_count": previous_count,
            "trend_text": trend_text,
            "comparison_text": comparison_text,
            "trend_class": trend_class
        })

    except ValueError:
        return jsonify({
            "success": False,
            "error": "Invalid date format."
        }), 400

    except Exception:
        logging.exception("Failed to retrieve History Report data.")

        return jsonify({
            "success": False,
            "error": "Unable to retrieve report data. Please try again."
        }), 500
