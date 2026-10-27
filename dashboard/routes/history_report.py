from flask import Blueprint, render_template
from src.database import get_supabase
from src.database import fetch_all_rows #additional diria

history_report_bp = Blueprint('history_report', __name__)

@history_report_bp.route('/')
def index():
    try:
        supabase = get_supabase()
        # Fetch all raw records to let the frontend aggregate history dynamically
        raw_records = fetch_all_rows(
    table_name="violations",
    columns="*",
    page_size=500,
    order_column="timestamp",
    descending=True,  #diria nag change sab 
)
    except Exception as e:
        print(f"[DATABASE CONNECTION ERROR] {e}")
        raw_records = []

    # Added: Passing logs down into the template context
    return render_template('history_reports.html', logs=raw_records)