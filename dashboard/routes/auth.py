
import os

from flask import (
    Blueprint,
    render_template,
    request,
    redirect,
    url_for,
    session,
)
from supabase import create_client
from src.database import get_supabase


auth_bp = Blueprint("auth", __name__)


def get_auth_client():
    """
    Create a separate Supabase client for authentication.
    This prevents login operations from changing the
    authentication state of the main database client.
    """
    supabase_url = os.getenv("SUPABASE_URL")
    publishable_key = os.getenv("SUPABASE_PUBLISHABLE_KEY")

    if not supabase_url:
        raise RuntimeError("SUPABASE_URL is not configured.")

    if not publishable_key:
        raise RuntimeError("SUPABASE_PUBLISHABLE_KEY is not configured.")

    return create_client(supabase_url, publishable_key)


@auth_bp.route("/")
def login_page():

    if session.get("user_id"):
        return redirect(url_for("overview.index"))

    return render_template("base.html")


@auth_bp.route("/login", methods=["POST"])
def login():

    login_id = request.form.get("username", "").strip().lower()
    password = request.form.get("password", "")

    if not login_id or not password:
        return render_template(
            "base.html",
            error="Please enter your login ID and password."
        )

    try:
        # 1. Authenticate credentials through Supabase Auth.
        auth_client = get_auth_client()

        auth_response = auth_client.auth.sign_in_with_password({
            "email": login_id,
            "password": password,
        })

        user = auth_response.user

        if not user:
            return render_template(
                "base.html",
                error="Invalid login ID or password."
            )

        # 2. Retrieve the corresponding Vanguard user profile.
        database = get_supabase()

        profile_response = (
            database.table("user_profiles")
            .select("id, login_id, full_name, role, is_active")
            .eq("id", str(user.id))
            .maybe_single()
            .execute()
        )

        profile = profile_response.data

        # 3. Reject accounts without a valid profile.
        if not profile:
            auth_client.auth.sign_out()

            return render_template(
                "base.html",
                error="Your account is not registered in Vanguard. Contact the administrator."
            )

        # 4. Check whether the account is active.
        if not profile.get("is_active", False):
            auth_client.auth.sign_out()

            return render_template(
                "base.html",
                error="Your account is inactive. Contact the administrator."
            )

        # 5. Establish the Flask session.
        session.clear()
        session.permanent = True

        session["user_id"] = str(user.id)
        session["login_id"] = profile["login_id"]
        session["full_name"] = profile["full_name"]
        session["role"] = profile["role"]

        print(
            f"[AUTH] Successful login: "
            f"{profile['login_id']} ({profile['role']})"
        )

        return redirect(url_for("overview.index"))

    except Exception:
        # Do not expose internal errors or credentials to users.
        print("[AUTH] Login failed.")

        return render_template(
            "base.html",
            error="Invalid login ID or password."
        )


@auth_bp.route("/logout", methods=["POST"])
def logout():

    session.clear()

    print("[AUTH] User logged out.")

    return redirect(url_for("auth.login_page"))
