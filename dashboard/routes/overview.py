from flask import Blueprint, render_template
from src.database import get_supabase
from datetime import datetime
from collections import Counter

overview_bp = Blueprint('overview', __name__)

@overview_bp.route('/overview')
@overview_bp.route('')
def index():
    try:
        supabase = get_supabase()
        # Fetch all live records from the database table chronologically
        response = supabase.table('violations').select('*').order('timestamp', desc=False).execute()
        records = response.data if response and hasattr(response, 'data') else []
        
        # 1. Prepare trackers for real-time calculations
        current_date_str = datetime.now().strftime('%Y-%m-%d')
        total_today = 0
        
        hour_counter = Counter()
        location_counter = Counter()
        
        # Initialize 24 spots for the 24-hour bar chart dataset array
        hourly_distribution = [0] * 24
        daily_trend_map = {}

        for log in records:
            ts_str = log.get('timestamp')
            if not ts_str:
                continue
                
            try:
                # Normalize string variations (handling timezone offsets gracefully)
                clean_ts = ts_str.replace('Z', '+00:00')
                dt = datetime.fromisoformat(clean_ts)
                log_date_str = dt.strftime('%Y-%m-%d')
                
                # Increment 'Today' counter if it matches the system calendar date
                if log_date_str == current_date_str:
                    total_today += 1
                
                # Track frequencies for recommendations
                hour_counter[dt.hour] += 1
                if log.get('location'):
                    location_counter[log.get('location')] += 1
                
                # Distribute values across chronological charts arrays
                hourly_distribution[dt.hour] += 1
                daily_trend_map[log_date_str] = daily_trend_map.get(log_date_str, 0) + 1
                
            except Exception as e:
                print(f"[OVERVIEW PARSE ERROR] Skipping row item: {e}")

        # 2. Extract dynamic recommendations string structures
        if hour_counter:
            peak_hour = hour_counter.most_common(1)[0][0]
            # Formats standard military block bounds cleanly into standard views
            peak_time_str = f"{peak_hour:02d}:00 - {(peak_hour + 1) % 24:02d}:00"
            peak_time_logged = hour_counter.most_common(1)[0][1]
        else:
            peak_time_str = "No Data Yet"
            peak_time_logged = 0

        if location_counter:
            peak_location_str, _ = location_counter.most_common(1)[0]
        else:
            peak_location_str = "No Hotspots Detected"

        # 3. Sort trend lines mapping keys chronologically
        sorted_dates = sorted(daily_trend_map.keys())
        sorted_daily_counts = [daily_trend_map[d] for d in sorted_dates]

        # Formatting backup defaults if tables are empty
        if not sorted_dates:
            # Format dates to show short month styles like "May 14" to match layout designs
            sorted_dates = [datetime.now().strftime('%b %d')]
            sorted_daily_counts = [0]
        else:
            # Re-format dates display cleanly for the line graph frontend axis
            sorted_dates = [datetime.fromisoformat(d).strftime('%b %d') for d in sorted_dates]

    except Exception as e:
        print(f"[OVERVIEW DATABASE SYSTEM FAILURE] {e}")
        total_today = 0
        peak_time_str = "Unavailable"
        peak_time_logged = 0
        peak_location_str = "Unavailable"
        hourly_distribution = [0] * 24
        sorted_dates = ["No Data"]
        sorted_daily_counts = [0]

    return render_template(
        'overview.html',
        total_today=total_today,
        peak_time=peak_time_str,
        peak_time_logged=peak_time_logged,
        peak_location=peak_location_str,
        hourly_data=hourly_distribution,
        trend_labels=sorted_dates,
        trend_data=sorted_daily_counts
    )