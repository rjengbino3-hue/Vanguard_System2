
from functools import wraps

from flask import (
    session,
    redirect,
    url_for,
    request,
    jsonify,
)


def login_required(view_function):
    @wraps(view_function)
    def wrapped_view(*args, **kwargs):

        if not session.get("user_id"):
            # API requests should receive JSON, not a login-page redirect.
            if request.path.endswith("/data"):
                return jsonify({
                    "success": False,
                    "error": "Authentication required."
                }), 401

            return redirect(url_for("auth.login_page"))

        return view_function(*args, **kwargs)

    return wrapped_view


def roles_required(*allowed_roles):
    def decorator(view_function):
        @wraps(view_function)
        def wrapped_view(*args, **kwargs):

            if not session.get("user_id"):
                if request.path.endswith("/data"):
                    return jsonify({
                        "success": False,
                        "error": "Authentication required."
                    }), 401

                return redirect(url_for("auth.login_page"))

            user_role = session.get("role")

            if user_role not in allowed_roles:
                if request.is_json or request.path.endswith("/data"):
                    return jsonify({
                        "success": False,
                        "error": "You are not authorized to perform this action."
                    }), 403

                return "Access denied. You do not have permission to view this page.", 403

            return view_function(*args, **kwargs)

        return wrapped_view

    return decorator
