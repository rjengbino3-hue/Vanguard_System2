from flask import Blueprint, render_template, request, jsonify
from src.database import get_supabase
from datetime import datetime, timedelta

trend_metrics_bp = Blueprint('trend_metrics', __name__)

def process_violation_data(records, target_date=None, target_week=None):
    """Helper logic to process records into chart formats based on filters."""
    hourly_distribution = [0] * 24
    daily_trend_map = {}

    # Calculate target week start/end if provided
    week_start, week_end = None, None
    if target_week:
        # target_week is usually in format "YYYY-Www" (e.g., "2026-W26")
        try:
            week_start = datetime.strptime(target_week + '-1', "%Y-W%W-%w").date()
            week_end = week_start + timedelta(days=6)
        except Exception:
            pass

    for log in records:
        timestamp_str = log.get('timestamp')
        if not timestamp_str:
            continue
            
        try:
            clean_ts = timestamp_str.replace('Z', '+00:00')
            dt = datetime.fromisoformat(clean_ts)
            record_date = dt.date()
            
            # --- 1. Hourly Chart Processing (Filter by specific date) ---
            if target_date:
                if record_date == target_date:
                    hourly_distribution[dt.hour] += 1
            else:
                # Fallback default: show all if no target date is given to this helper
                hourly_distribution[dt.hour] += 1
                
            # --- 2. Daily Trend Chart Processing (Filter by week if provided) ---
            if week_start and week_end:
                if week_start <= record_date <= week_end:
                    date_str = dt.strftime('%Y-%m-%d')
                    daily_trend_map[date_str] = daily_trend_map.get(date_str, 0) + 1
            else:
                date_str = dt.strftime('%Y-%m-%d')
                daily_trend_map[date_str] = daily_trend_map.get(date_str, 0) + 1

        except Exception as parse_err:
            print(f"[PARSING ERROR] Skipping invalid timestamp: {parse_err}")

    sorted_dates = sorted(daily_trend_map.keys())
    sorted_daily_counts = [daily_trend_map[d] for d in sorted_dates]

    if not sorted_dates:
        sorted_dates = [datetime.now().strftime('%Y-%m-%d')]
        sorted_daily_counts = [0]

    return hourly_distribution, sorted_dates, sorted_daily_counts


@trend_metrics_bp.route('/')
@trend_metrics_bp.route('')
def index():
    try:
        supabase = get_supabase()
        response = supabase.table('violations').select('timestamp').order('timestamp', desc=False).execute()
        records = response.data if response and hasattr(response, 'data') else []
        
        # Default: Default Hourly chart to showing TODAY's data only
        today_date = datetime.now().date()
        
        hourly_distribution, sorted_dates, sorted_daily_counts = process_violation_data(
            records, target_date=today_date, target_week=None
        )
        default_date_str = today_date.strftime('%Y-%m-%d')

    except Exception as e:
        print(f"[TRENDS ENGINE ERROR] Initialization failure: {e}")
        hourly_distribution = [0] * 24
        sorted_dates = ["No Data"]
        sorted_daily_counts = [0]
        default_date_str = datetime.now().strftime('%Y-%m-%d')

    return render_template(
        'trend_metrics.html', 
        hourly_data=hourly_distribution,
        trend_labels=sorted_dates,
        trend_data=sorted_daily_counts,
        default_date=default_date_str
    )


@trend_metrics_bp.route('/data')
def get_filtered_data():
    """Asynchronous API endpoint endpoint for active frontend filtering."""
    try:
        date_param = request.args.get('date')  # Expects YYYY-MM-DD
        week_param = request.args.get('week')  # Expects YYYY-Www

        target_date = datetime.strptime(date_param, '%Y-%m-%d').date() if date_param else None

        supabase = get_supabase()
        response = supabase.table('violations').select('timestamp').order('timestamp', desc=False).execute()
        records = response.data if response and hasattr(response, 'data') else []

        hourly_distribution, sorted_dates, sorted_daily_counts = process_violation_data(
            records, target_date=target_date, target_week=week_param
        )

        return jsonify({
            'hourly_data': hourly_distribution,
            'trend_labels': sorted_dates,
            'trend_data': sorted_daily_counts
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 400