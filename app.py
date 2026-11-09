"""RoadSafe: Smart Accident Black Spot Mapping System."""

from datetime import datetime
import os
import secrets
from pathlib import Path

from flask import Blueprint, Flask, abort, flash, g, redirect, render_template, request, session, url_for

from config import Config
from database import close_db, ensure_admin, get_db, init_db as initialize_database, utcnow
from modules import accident_reporting, admin, analytics, authentication, reports
from modules.blackspot_detection import refresh_blackspots


main = Blueprint("main", __name__)


@main.get("/")
def index():
    if g.get("user"):
        return redirect(url_for("analytics.dashboard"))
    return render_template("index.html")


def create_app(test_config=None):
    app = Flask(__name__, instance_relative_config=False)
    app.config.from_object(Config)
    if test_config:
        app.config.update(test_config)
    Path(app.config["UPLOAD_FOLDER"]).mkdir(parents=True, exist_ok=True)

    app.teardown_appcontext(close_db)
    app.register_blueprint(main)
    app.register_blueprint(authentication.bp)
    app.register_blueprint(accident_reporting.bp)
    app.register_blueprint(admin.bp)
    app.register_blueprint(analytics.bp)
    app.register_blueprint(reports.bp)

    @app.before_request
    def bind_user_and_verify_csrf():
        authentication.load_current_user()
        if request.method == "POST":
            expected = session.get("csrf_token", "")
            supplied = request.form.get("csrf_token", "")
            if not expected or not supplied or not secrets.compare_digest(expected, supplied):
                abort(400, "Your form session expired. Please refresh the page and try again.")

    @app.context_processor
    def inject_template_helpers():
        def csrf_token():
            if "csrf_token" not in session:
                session["csrf_token"] = secrets.token_urlsafe(32)
            return session["csrf_token"]
        return {"csrf_token": csrf_token}

    @app.template_filter("display_datetime")
    def display_datetime(value):
        if not value:
            return "—"
        try:
            return datetime.fromisoformat(value).strftime("%d %b %Y, %H:%M")
        except (TypeError, ValueError):
            return value

    @app.errorhandler(400)
    def bad_request(error):
        return render_template("error.html", code=400, message=getattr(error, "description", "Invalid request.")), 400

    @app.errorhandler(413)
    def upload_too_large(_error):
        flash("The image is too large. Uploads are limited to 5 MiB.", "danger")
        return redirect(request.referrer or url_for("reporting.report_accident"))

    @app.errorhandler(404)
    def not_found(_error):
        return render_template("error.html", code=404, message="The page you requested does not exist."), 404

    with app.app_context():
        initialize_database()
        ensure_admin()
        refresh_blackspots()

    @app.cli.command("init-db")
    def init_db_command():
        """Initialise the SQLite schema and configured administrator."""
        initialize_database()
        ensure_admin()
        refresh_blackspots()
        print("SQLite schema is ready and the configured administrator exists.")

    @app.cli.command("seed-demo")
    def seed_demo_command():
        """Insert realistic verified data once, for evaluating the dashboard."""
        db = get_db()
        if db.execute("SELECT COUNT(*) AS count FROM accident_reports").fetchone()["count"]:
            print("Seed skipped: accident reports already exist.")
            return
        admin_user = db.execute("SELECT id FROM users WHERE role = 'admin' ORDER BY id LIMIT 1").fetchone()
        now = utcnow()
        examples = [
            ("Central Junction", 12.97160, 77.59460, "2026-01-12T20:10", "Collision", "Car, Motorcycle", "High", 2, "Night-time turning collision."),
            ("Central Junction", 12.97210, 77.59420, "2026-02-03T21:25", "Pedestrian", "Car, Pedestrian", "High", 1, "Pedestrian struck while crossing."),
            ("Central Junction", 12.97090, 77.59500, "2026-03-18T19:40", "Collision", "Bus, Motorcycle", "Medium", 1, "Side impact near the signal."),
            ("Market Road Crossing", 12.93520, 77.62460, "2026-04-10T08:35", "Pedestrian", "Auto rickshaw, Pedestrian", "Medium", 1, "Crossing conflict at market entrance."),
            ("Market Road Crossing", 12.93560, 77.62410, "2026-05-22T18:50", "Collision", "Car, Scooter", "Medium", 0, "Rear-end collision in congestion."),
            ("Airport Link Road", 12.99420, 77.67390, "2026-06-14T14:15", "Single vehicle", "Car", "Low", 0, "Vehicle left the carriageway."),
        ]
        for name, latitude, longitude, occurred_at, accident_type, vehicles, severity, casualties, description in examples:
            normalised = " ".join(name.lower().split())
            db.execute(
                "INSERT OR IGNORE INTO accident_locations (name, normalized_name, latitude, longitude, created_at) VALUES (?, ?, ?, ?, ?)",
                (name, normalised, latitude, longitude, now),
            )
            location_id = db.execute(
                "SELECT id FROM accident_locations WHERE normalized_name = ? AND latitude = ? AND longitude = ?",
                (normalised, latitude, longitude),
            ).fetchone()["id"]
            db.execute(
                """INSERT INTO accident_reports
                (reporter_id, location_id, location_name, latitude, longitude, occurred_at, accident_type, vehicle_types,
                 severity, casualties, description, status, reviewed_by, reviewed_at, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'verified', ?, ?, ?, ?)""",
                (admin_user["id"], location_id, name, latitude, longitude, occurred_at, accident_type, vehicles,
                 severity, casualties, description, admin_user["id"], now, now, now),
            )
        db.commit()
        refresh_blackspots()
        print("Demo reports inserted and black spots calculated.")

    return app


app = create_app()


if __name__ == "__main__":
    app.run(debug=os.getenv("FLASK_DEBUG", "false").lower() == "true")
