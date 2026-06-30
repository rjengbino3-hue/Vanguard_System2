from flask import Blueprint, render_template
from src.database import get_supabase

history_report_bp = Blueprint('history_report', __name__)

@history_report_bp.route('/')
def index():
    try:
        supabase = get_supabase()
        # Fetch all raw records to let the frontend aggregate history dynamically
        response = supabase.table('violations').select('*').order('timestamp', desc=True).execute()
        raw_records = response.data if response and hasattr(response, 'data') else []
    except Exception as e:
        print(f"[DATABASE CONNECTION ERROR] {e}")
        raw_records = []

    # Added: Passing logs down into the template context
    return render_template('history_reports.html', logs=raw_records)