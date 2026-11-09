"""Session based authentication and role guards."""

from functools import wraps
import re

from flask import Blueprint, flash, g, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

from database import execute, query_one, utcnow


bp = Blueprint("auth", __name__)
EMAIL_PATTERN = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


def load_current_user() -> None:
    g.user = None
    user_id = session.get("user_id")
    if user_id:
        g.user = query_one("SELECT id, full_name, email, role FROM users WHERE id = ?", (user_id,))
        if g.user is None:
            session.clear()


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if g.get("user") is None:
            flash("Please sign in to continue.", "warning")
            return redirect(url_for("auth.login"))
        return view(*args, **kwargs)
    return wrapped


def admin_required(view):
    @wraps(view)
    @login_required
    def wrapped(*args, **kwargs):
        if g.user["role"] != "admin":
            flash("Administrator access is required for that page.", "danger")
            return redirect(url_for("analytics.dashboard"))
        return view(*args, **kwargs)
    return wrapped


@bp.route("/register", methods=["GET", "POST"])
def register():
    if g.get("user"):
        return redirect(url_for("analytics.dashboard"))
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")
        if not 2 <= len(name) <= 100:
            flash("Enter a name between 2 and 100 characters.", "danger")
        elif not EMAIL_PATTERN.fullmatch(email) or len(email) > 150:
            flash("Enter a valid email address.", "danger")
        elif len(password) < 8:
            flash("Use a password with at least 8 characters.", "danger")
        elif password != confirm_password:
            flash("The password confirmation does not match.", "danger")
        elif query_one("SELECT id FROM users WHERE email = ?", (email,)):
            flash("An account with that email already exists.", "danger")
        else:
            user_id = execute(
                "INSERT INTO users (full_name, email, password_hash, role, created_at) VALUES (?, ?, ?, 'user', ?)",
                (name, email, generate_password_hash(password), utcnow()),
            )
            session.clear()
            session["user_id"] = user_id
            session.permanent = True
            flash("Your account is ready. You can now submit a report.", "success")
            return redirect(url_for("analytics.dashboard"))
    return render_template("register.html")


@bp.route("/login", methods=["GET", "POST"])
def login():
    if g.get("user"):
        return redirect(url_for("analytics.dashboard"))
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        user = query_one("SELECT * FROM users WHERE email = ?", (email,))
        if user and check_password_hash(user["password_hash"], password):
            session.clear()
            session["user_id"] = user["id"]
            session.permanent = True
            flash(f"Welcome back, {user['full_name'].split()[0]}.", "success")
            return redirect(url_for("analytics.dashboard"))
        flash("Invalid email address or password.", "danger")
    return render_template("login.html")


@bp.post("/logout")
@login_required
def logout():
    session.clear()
    flash("You have been signed out.", "info")
    return redirect(url_for("main.index"))
