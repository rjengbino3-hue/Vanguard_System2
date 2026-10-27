from flask import Blueprint, render_template, request, redirect, url_for, session


auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/")
def login_page():
    print("[DEBUG] Auth Blueprint: Serving login system (base.html)")
    return render_template("base.html")


@auth_bp.route("/login", methods=["POST"])
def login():
    username = request.form.get("username", "").strip().lower()
    password = request.form.get("password", "").strip()

    if username == "admin" and password == "password123":
        print("[FLASK AUTH] Valid credentials. Routing to dashboard overview...")
        return redirect(url_for("overview.index"))

    print("[FLASK AUTH WARNING] Failed password entry match.")
    return render_template("base.html", error="Invalid credentials. Try again.")


@auth_bp.route("/logout")
def logout():
    session.clear()
    print("[FLASK AUTH] Session cleared out successfully.")
    return redirect(url_for("auth.login_page"))