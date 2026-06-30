from flask import Blueprint, render_template
from src.database import get_supabase 
from collections import Counter

data_logs_bp = Blueprint('data_logs', __name__)

@data_logs_bp.route('/')
@data_logs_bp.route('')
def index():
    try:
        supabase = get_supabase()
        # 1. Fetch ALL raw logs chronologically from Supabase
        response = supabase.table('violations').select('*').order('timestamp', desc=True).execute()
        raw_records = response.data if response and hasattr(response, 'data') else []
        
        hotspot_counts = Counter()
        location_details = {}

        # 2. Process ALL records historically so they reach the template
        for log in raw_records:
            loc = log.get('location')
            if loc:
                hotspot_counts[loc] += 1
                # Save metadata for the hotspot list mapping
                if loc not in location_details:
                    location_details[loc] = {
                        'timestamp': log.get('timestamp'),
                        'device_id': log.get('device_id')
                    }

        # 3. Assemble and sort hotspots dynamically based on total history
        hotspots = []
        for loc, count in hotspot_counts.most_common():
            hotspots.append({
                'location': loc,
                'count': count,
                'timestamp': location_details[loc]['timestamp'],
                'device_id': location_details[loc]['device_id']
            })

    except Exception as e:
        print(f"[DATABASE CONNECTION ERROR] {e}")
        raw_records, hotspots = [], []

    # Send the historical raw_records so your client-side filters can search everything!
    return render_template('data_logs.html', logs=raw_records, hotspots=hotspots)