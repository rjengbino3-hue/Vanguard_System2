from flask import Blueprint, render_template
from src.database import get_supabase 
from collections import Counter
from src.database import fetch_all_rows   #mao ni ang addition 

data_logs_bp = Blueprint('data_logs', __name__)

@data_logs_bp.route('/')
@data_logs_bp.route('')
def index():
    try:
        supabase = get_supabase()
        # 1. Fetch ALL raw logs chronologically from Supabase
        raw_records = fetch_all_rows(
    table_name="violations",
    columns="*",
    page_size=500,
    order_column="timestamp",
    descending=True,
)    #DIRIA ANG CHANGES SAB
        
        # Track counts grouped by a unique tuple combination: (location, date_str)
        hotspot_daily_counts = Counter()
        location_device_mapping = {}

        # 2. Process ALL records historically broken down by calendar days
        for log in raw_records:
            loc = log.get('location')
            timestamp = log.get('timestamp')
            
            if loc and timestamp:
                # Extract just the date string part: "YYYY-MM-DD"
                date_str = timestamp[:10]
                
                # Combine location and date as a composite key
                hotspot_daily_counts[(loc, date_str)] += 1
                
                # Track the specific device ID handling this location
                if loc not in location_device_mapping:
                    location_device_mapping[loc] = log.get('device_id', 'N/A')

        # 3. Assemble hotspots dynamically containing unique entries for each location per day
        hotspots = []
        for (loc, date_str), count in hotspot_daily_counts.most_common():
            # Synthesize a clean date-matched timestamp so your frontend JavaScript matches it perfectly
            synthetic_timestamp = f"{date_str} 00:00:00"
            
            hotspots.append({
                'location': loc,
                'count': count,
                'timestamp': synthetic_timestamp,
                'device_id': location_device_mapping.get(loc, 'N/A')
            })

    except Exception as e:
        print(f"[DATABASE CONNECTION ERROR] {e}")
        raw_records, hotspots = [], []

    # Send the historical split dataset to your client template
    return render_template('data_logs.html', logs=raw_records, hotspots=hotspots)