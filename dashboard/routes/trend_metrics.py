from flask import Blueprint, render_template, request, jsonify
from src.database import get_supabase
from datetime import datetime, timedelta
from src.database import fetch_all_rows #ADDITIO NI

trend_metrics_bp = Blueprint('trend_metrics', __name__)

def process_violation_data(records, target_date=None, target_week=None):
    """Helper logic to process records into chart formats based on slices matching data_logs."""
    hourly_distribution = [0] * 24
    daily_trend_map = {}
    
    week_start, week_end = None, None

    # Parse HTML5 ISO Week format (e.g., "2026-W28") safely using built-in calendar mappings
    if target_week and target_week.strip():
        try:
            year_str, week_str = target_week.split('-W')
            iso_year = int(year_str)
            iso_week = int(week_str)
            
            # Day 1 = Monday, Day 7 = Sunday
            week_start = datetime.fromisocalendar(iso_year, iso_week, 1).date()
            week_end = datetime.fromisocalendar(iso_year, iso_week, 7).date()
            
            # Pre-populate the whole week with 0 baseline metrics
            current_day = week_start
            while current_day <= week_end:
                daily_trend_map[current_day.strftime('%Y-%m-%d')] = 0
                current_day += timedelta(days=1)
        except Exception as e:
            print(f"[WEEK PARSING ERROR] Failed parsing ISO week '{target_week}': {e}")

    for log in records:
        timestamp_str = log.get('timestamp')
        if not timestamp_str or len(timestamp_str) < 13:
            continue
            
        try:
            # Match data_logs approach: extract standard 'YYYY-MM-DD' by slicing first 10 characters
            date_str = timestamp_str[:10] 
            
            # Safely parse out hour characters from index 11 and 12 (e.g., "2026-07-12 15:45:20" -> "15")
            hour_str = timestamp_str[11:13]
            hour_val = int(hour_str)
            
            # Convert extracted date string to comparison object safely
            record_date = datetime.strptime(date_str, '%Y-%m-%d').date()
            
            # --- Hourly Chart Mapping ---
            if target_date:
                if record_date == target_date:
                    if 0 <= hour_val < 24:
                        hourly_distribution[hour_val] += 1
            else:
                if 0 <= hour_val < 24:
                    hourly_distribution[hour_val] += 1
                
            # --- Daily Trend Chart Mapping ---
            if week_start and week_end:
                if week_start <= record_date <= week_end:
                    daily_trend_map[date_str] = daily_trend_map.get(date_str, 0) + 1
            else:
                daily_trend_map[date_str] = daily_trend_map.get(date_str, 0) + 1

        except Exception as parse_err:
            print(f"[PARSING ERROR] Skipping entry index due to unexpected format mapping: {parse_err}")

    # Build response trends chronologically
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
        # Query exactly like data_logs.py to make sure the records arrive structured correctly
        records = fetch_all_rows(
    table_name="violations",
    columns="*",
    page_size=500,
    order_column="timestamp",
    descending=True,
)  #CHANGES DIRIA
        
        today_date = datetime.now().date()
        
        hourly_distribution, sorted_dates, sorted_daily_counts = process_violation_data(
            records, target_date=today_date, target_week=None
        )
        default_date_str = today_date.strftime('%Y-%m-%d')

    except Exception as e:
        print(f"[TRENDS ENGINE ERROR] Initialization failure: {e}")
        hourly_distribution = [0] * 24
        sorted_dates = [datetime.now().strftime('%Y-%m-%d')]
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
    try:
        date_param = request.args.get('date')
        week_param = request.args.get('week')

        target_date = None
        if date_param and date_param.strip():
            target_date = datetime.strptime(date_param.strip(), '%Y-%m-%d').date()

        supabase = get_supabase()
        records = fetch_all_rows(
    table_name="violations",
    columns="*",
    page_size=500,
    order_column="timestamp",
    descending=True,
) #changes diria

        hourly_distribution, sorted_dates, sorted_daily_counts = process_violation_data(
            records, target_date=target_date, target_week=week_param
        )

        return jsonify({
            'hourly_data': hourly_distribution,
            'trend_labels': sorted_dates,
            'trend_data': sorted_daily_counts
        })
    except Exception as e:
        print(f"[API FILTER ERROR] Exception caught: {e}")
        return jsonify({'error': str(e)}), 500