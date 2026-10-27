import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from flask import Flask, render_template, session, redirect, url_for, request
from src.database import get_supabase


base_dir = os.path.dirname(os.path.abspath(__file__))

app = Flask(
    __name__,
    static_folder=os.path.join(base_dir, "static"),
    template_folder=os.path.join(base_dir, "templates"),
)

app.secret_key = "vanguard_system_super_secure_secret_key_development"


try:
    supabase_client = get_supabase()
    print("[FLASK] Successfully connected to the Supabase cloud database.")
except Exception as e:
    print(f"[FLASK ERROR] Failed to initialize Supabase client: {e}")


from dashboard.routes.auth import auth_bp
from dashboard.routes.overview import overview_bp
from dashboard.routes.data_logs import data_logs_bp
from dashboard.routes.cameras import cameras_bp
from dashboard.routes.history_report import history_report_bp
from dashboard.routes.trend_metrics import trend_metrics_bp


app.register_blueprint(auth_bp, url_prefix="/")
app.register_blueprint(overview_bp)
app.register_blueprint(data_logs_bp, url_prefix="/logs")
app.register_blueprint(cameras_bp, url_prefix="/cameras")
app.register_blueprint(history_report_bp, url_prefix="/report")
app.register_blueprint(trend_metrics_bp, url_prefix="/trends")


@app.route("/logout")
def logout():
    session.clear()
    print("[FLASK] User logged out successfully. Redirecting to auth portal...")
    return render_template("base.html")


@app.route("/login", methods=["POST"])
def login():
    username = request.form.get("username", "").strip().lower()
    password = request.form.get("password", "").strip()

    if username == "admin" and password == "password123":
        print("[FLASK] Authentication successful! Redirecting to Overview panel...")
        return redirect(url_for("overview.index"))

    print("[FLASK WARNING] Password mismatch or invalid user.")
    return render_template("base.html", error="Invalid credentials. Try again.")


@app.route("/settings/settings")
def show_settings():
    return render_template("settings.html")


@app.route("/settings/about")
def show_about():
    return render_template("about.html")


if __name__ == "__main__":
    print("[FLASK] Launching local development environment...")
    print("[FLASK] Registered URL Routes:")

    for rule in app.url_map.iter_rules():
        print(f"  -> http://127.0.0.1:5000{rule}")

    app.run(host="127.0.0.1", port=5000, debug=True)