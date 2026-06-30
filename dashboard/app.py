import sys
import os
from datetime import datetime, timedelta
from collections import Counter

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from flask import Flask, render_template, session, redirect, url_for, request, flash, jsonify

# Import custom database handlers from src/ folder
from src.database import get_supabase

base_dir = os.path.dirname(os.path.abspath(__file__))

app = Flask(__name__, 
            static_folder=os.path.join(base_dir, 'static'), 
            template_folder=os.path.join(base_dir, 'templates'))

app.secret_key = 'vanguard_system_super_secure_secret_key_development'

# Establish connection to your Supabase project on startup
try:
    supabase_client = get_supabase()
    print("[FLASK] Successfully connected to the Supabase cloud database.")
except Exception as e:
    print(f"[FLASK ERROR] Failed to initialize Supabase client: {e}")

# Import Blueprints from your dashboard routes
from dashboard.routes.auth import auth_bp
from dashboard.routes.data_logs import data_logs_bp
from dashboard.routes.cameras import cameras_bp
from dashboard.routes.history_report import history_report_bp
from dashboard.routes.trend_metrics import trend_metrics_bp

# Register Blueprints with clean URL prefixes
app.register_blueprint(auth_bp, url_prefix='/')
app.register_blueprint(data_logs_bp, url_prefix='/logs')
app.register_blueprint(cameras_bp, url_prefix='/cameras')
app.register_blueprint(history_report_bp, url_prefix='/report')
app.register_blueprint(trend_metrics_bp, url_prefix='/trends')


# ==========================================
# CORE NAVIGATION ROUTES & DATABASE LOGIC
# ==========================================

@app.route('/overview', endpoint='overview')
@app.route('/', endpoint='overview_root')
def overview_index():
    try:
        supabase = get_supabase()
        response = supabase.table('violations').select('*').order('timestamp', desc=False).execute()
        records = response.data if response and hasattr(response, 'data') else []
        
        today_dt = datetime.now()
        current_date_str = today_dt.strftime('%Y-%m-%d')
        yesterday_date_str = (today_dt - timedelta(days=1)).strftime('%Y-%m-%d')
        current_peak_date_str = today_dt.strftime('%B %d, %Y')
        
        total_today = 0
        total_yesterday = 0
        first_log_time_str = "N/A"
        first_today_dt = None
        
        hour_counter = Counter()
        location_counter = Counter()
        hourly_distribution = [0] * 24
        daily_trend_map = {}

        today_logs = []
        today_location_counter = Counter()
        location_device_map = {}

        for log in records:
            ts_str = log.get('timestamp')
            if not ts_str:
                continue
                
            try:
                clean_ts = ts_str.replace('Z', '+00:00')
                dt = datetime.fromisoformat(clean_ts)
                log_date_str = dt.strftime('%Y-%m-%d')
                
                if log_date_str == current_date_str:
                    total_today += 1
                    hourly_distribution[dt.hour] += 1
                    
                    today_logs.append(log)
                    loc = log.get('location', 'Unknown Location')
                    today_location_counter[loc] += 1
                    if log.get('device_id'):
                        location_device_map[loc] = log.get('device_id')
                    
                    if first_today_dt is None or dt < first_today_dt:
                        first_today_dt = dt
                        
                elif log_date_str == yesterday_date_str:
                    total_yesterday += 1
                
                hour_counter[dt.hour] += 1
                if log.get('location'):
                    location_counter[log.get('location')] += 1
                
                daily_trend_map[log_date_str] = daily_trend_map.get(log_date_str, 0) + 1
                
            except Exception as e:
                print(f"[PARSING ERROR] {e}")

        if first_today_dt:
            first_log_time_str = first_today_dt.strftime('%I:%M %p')

        comparison_text = "No change from yesterday"
        if total_yesterday > 0:
            pct_diff = ((total_today - total_yesterday) / total_yesterday) * 100
            if pct_diff > 0:
                comparison_text = f"{abs(pct_diff):.0f}% Higher than Yesterday"
            elif pct_diff < 0:
                comparison_text = f"{abs(pct_diff):.0f}% Lower than Yesterday"
        elif total_today > 0 and total_yesterday == 0:
            comparison_text = "100% Higher than Yesterday"

        if hour_counter:
            peak_hour = hour_counter.most_common(1)[0][0]
            start_ampm = "A.M" if peak_hour < 12 else "P.M"
            end_ampm = "A.M" if (peak_hour + 1) % 24 < 12 else "P.M"
            
            sh = peak_hour if peak_hour <= 12 else peak_hour - 12
            if sh == 0: sh = 12
            eh = (peak_hour + 1) % 24
            eh = eh if eh <= 12 else eh - 12
            if eh == 0: eh = 12
            
            peak_time_str = f"{sh}:00 - {eh}:00 {end_ampm}"
            peak_time_logged = hour_counter.most_common(1)[0][1]
        else:
            peak_time_str = "No Data Yet"
            peak_time_logged = 0

        if location_counter:
            peak_location_str, _ = location_counter.most_common(1)[0]
        else:
            peak_location_str = "No Hotspots Detected"

        today_hotspots = []
        sorted_hotspots = today_location_counter.most_common()
        for rank, (location, total_logs) in enumerate(sorted_hotspots, start=1):
            today_hotspots.append({
                'date': current_date_str,
                'rank': rank,
                'location': location,
                'total_logs': total_logs,
                'device_id': location_device_map.get(location, 'N/A')
            })

        recent_today_logs = list(reversed(today_logs))

        sorted_dates = sorted(daily_trend_map.keys())
        sorted_daily_counts = [daily_trend_map[d] for d in sorted_dates]

        if not sorted_dates:
            sorted_dates = [datetime.now().strftime('%b %d')]
            sorted_daily_counts = [0]
        else:
            sorted_dates = [datetime.fromisoformat(d).strftime('%b %d') for d in sorted_dates]

    except Exception as e:
        print(f"[DATABASE ERROR] {e}")
        total_today = 0
        comparison_text = "Data unavailable"
        first_log_time_str = "N/A"
        peak_time_str = "Unavailable"
        peak_time_logged = 0
        peak_location_str = "Unavailable"
        current_peak_date_str = datetime.now().strftime('%B %d, %Y')
        hourly_distribution = [0] * 24
        sorted_dates = ["No Data"]
        sorted_daily_counts = [0]
        recent_today_logs = []
        today_hotspots = []

    return render_template(
        'overview.html',
        total_today=total_today,
        comparison_text=comparison_text,
        since_time=first_log_time_str,
        peak_time=peak_time_str,
        peak_time_logged=peak_time_logged,
        peak_location=peak_location_str,
        peak_date=current_peak_date_str,
        hourly_data=hourly_distribution,
        trend_labels=sorted_dates,
        trend_data=sorted_daily_counts,
        recent_logs=recent_today_logs,
        hotspots=today_hotspots
    )


# ==========================================
# AUTHENTICATION & MANAGEMENT ROUTES
# ==========================================

@app.route('/logout')
def logout():
    session.clear()
    print("[FLASK] User logged out successfully. Redirecting to auth portal...")
    return render_template('base.html')


@app.route('/login', methods=['POST'])
def login():
    username = request.form.get('username', '').strip().lower()
    password = request.form.get('password', '').strip()
    
    if username == "admin" and password == "password123":
        print("[FLASK] Authentication successful! Redirecting to Overview panel...")
        return redirect(url_for('overview'))
    else:
        print("[FLASK WARNING] Password mismatch or invalid user.")
        return render_template('base.html', error="Invalid credentials. Try again.")


@app.route('/settings/settings')
def show_settings():
    return render_template('settings.html')


@app.route('/settings/about')
def show_about():
    return render_template('about.html')


if __name__ == '__main__':
    print("[FLASK] Launching local development environment...")
    print("[FLASK] Registered URL Routes:")
    for rule in app.url_map.iter_rules():
        print(f"  -> http://127.0.0.1:5000{rule}")

    app.run(host='127.0.0.1', port=5000, debug=True)