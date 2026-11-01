
import sys
import os


from dotenv import load_dotenv
from flask import Flask
from datetime import timedelta
from dashboard.auth_utils import login_required
from flask_wtf.csrf import CSRFProtect

# Locate project root
base_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(base_dir)

sys.path.append(project_root)

# Load environment variables from the project root
load_dotenv(os.path.join(project_root, ".env"))

# Require a secure Flask secret key
flask_secret = os.getenv("FLASK_SECRET_KEY")

if not flask_secret:
    raise RuntimeError(
        "FLASK_SECRET_KEY is missing. "
        "Add it to your project root .env file."
    )

# Initialize Flask
app = Flask(
    __name__,
    static_folder=os.path.join(base_dir, "static"),
    template_folder=os.path.join(base_dir, "templates"),
)

# Secure session configuration
app.config["SECRET_KEY"] = flask_secret
app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(hours=8)
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"


# Use secure cookies in production, but allow localhost HTTP testing
is_production = os.getenv("APP_ENV", "development").lower() == "production"
app.config["SESSION_COOKIE_SECURE"] = is_production

# Enable CSRF protection
csrf = CSRFProtect(app)

# Import blueprints
from dashboard.routes.auth import auth_bp
from dashboard.routes.overview import overview_bp
from dashboard.routes.data_logs import data_logs_bp
from dashboard.routes.cameras import cameras_bp
from dashboard.routes.history_report import history_report_bp
from dashboard.routes.trend_metrics import trend_metrics_bp

# Register blueprints
app.register_blueprint(auth_bp, url_prefix="/")
app.register_blueprint(overview_bp)
app.register_blueprint(data_logs_bp, url_prefix="/logs")
app.register_blueprint(cameras_bp, url_prefix="/cameras")
app.register_blueprint(history_report_bp, url_prefix="/report")
app.register_blueprint(trend_metrics_bp, url_prefix="/trends")


# Additional informational pages
@app.route("/settings/settings")
@login_required
def show_settings():
    from flask import render_template
    return render_template("settings.html")


@app.route("/settings/about")
@login_required
def show_about():
    from flask import render_template
    return render_template("about.html")


if __name__ == "__main__":
    print("[FLASK] Launching local development environment...")
    print("[FLASK] Registered URL Routes:")

    for rule in app.url_map.iter_rules():
        print(f" -> http://127.0.0.1:5000{rule}")

    app.run(
        host="127.0.0.1",
        port=5000,
        debug=not is_production
    )
