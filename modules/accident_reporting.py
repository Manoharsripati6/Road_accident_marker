"""Accident submission and report-record views."""

from datetime import datetime, timedelta
from pathlib import Path
import re
from uuid import uuid4

from flask import Blueprint, current_app, flash, g, redirect, render_template, request, url_for
from werkzeug.utils import secure_filename

from database import get_db, query_one, utcnow
from modules.authentication import login_required


bp = Blueprint("reporting", __name__)
ACCIDENT_TYPES = ("Collision", "Pedestrian", "Vehicle rollover", "Single vehicle", "Cyclist", "Other")
SEVERITIES = ("Low", "Medium", "High")


def _normalise_location(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip()).casefold()


def _parse_report_form():
    location_name = re.sub(r"\s+", " ", request.form.get("location_name", "").strip())
    accident_type = request.form.get("accident_type", "")
    severity = request.form.get("severity", "")
    vehicle_types = re.sub(r"\s+", " ", request.form.get("vehicle_types", "").strip())
    description = request.form.get("description", "").strip()
    if not 3 <= len(location_name) <= 200:
        raise ValueError("Location name must be between 3 and 200 characters.")
    if accident_type not in ACCIDENT_TYPES or severity not in SEVERITIES:
        raise ValueError("Choose a valid accident type and severity.")
    if not 2 <= len(vehicle_types) <= 200:
        raise ValueError("Describe at least one involved vehicle or road user.")
    if len(description) > 3000:
        raise ValueError("Description must be 3,000 characters or fewer.")
    try:
        latitude = float(request.form.get("latitude", ""))
        longitude = float(request.form.get("longitude", ""))
        occurred_at = datetime.fromisoformat(request.form.get("occurred_at", ""))
        casualties = int(request.form.get("casualties", "0"))
    except (TypeError, ValueError) as error:
        raise ValueError("Enter valid coordinates, date/time and casualties.") from error
    if not (-90 <= latitude <= 90 and -180 <= longitude <= 180):
        raise ValueError("Coordinates are outside the valid latitude/longitude range.")
    if casualties < 0 or casualties > 10000:
        raise ValueError("Casualties must be between 0 and 10,000.")
    if occurred_at > datetime.now() + timedelta(minutes=5):
        raise ValueError("An accident report cannot be dated in the future.")
    return {
        "location_name": location_name,
        "normalized_name": _normalise_location(location_name),
        "latitude": latitude,
        "longitude": longitude,
        "occurred_at": occurred_at.replace(tzinfo=None).isoformat(timespec="minutes"),
        "accident_type": accident_type,
        "vehicle_types": vehicle_types,
        "severity": severity,
        "casualties": casualties,
        "description": description,
    }


def _save_image():
    image = request.files.get("image")
    if not image or not image.filename:
        return None
    supplied_name = secure_filename(image.filename)
    extension = Path(supplied_name).suffix.lower().lstrip(".")
    if extension not in current_app.config["ALLOWED_IMAGE_EXTENSIONS"] or not image.mimetype.startswith("image/"):
        raise ValueError("Upload a PNG, JPG, GIF or WEBP image only.")
    filename = f"{uuid4().hex}.{extension}"
    image.save(Path(current_app.config["UPLOAD_FOLDER"]) / filename)
    return filename


def _upsert_location(details: dict) -> int:
    db = get_db()
    db.execute(
        """INSERT OR IGNORE INTO accident_locations
           (name, normalized_name, latitude, longitude, created_at) VALUES (?, ?, ?, ?, ?)""",
        (details["location_name"], details["normalized_name"], details["latitude"], details["longitude"], utcnow()),
    )
    return db.execute(
        "SELECT id FROM accident_locations WHERE normalized_name = ? AND latitude = ? AND longitude = ?",
        (details["normalized_name"], details["latitude"], details["longitude"]),
    ).fetchone()["id"]


@bp.route("/report", methods=["GET", "POST"])
@login_required
def report_accident():
    if request.method == "POST":
        try:
            details = _parse_report_form()
            image_filename = _save_image()
            db = get_db()
            location_id = _upsert_location(details)
            now = utcnow()
            db.execute(
                """INSERT INTO accident_reports
                (reporter_id, location_id, location_name, latitude, longitude, occurred_at, accident_type,
                 vehicle_types, severity, casualties, description, image_filename, status, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?, ?)""",
                (
                    g.user["id"], location_id, details["location_name"], details["latitude"], details["longitude"],
                    details["occurred_at"], details["accident_type"], details["vehicle_types"], details["severity"],
                    details["casualties"], details["description"], image_filename, now, now,
                ),
            )
            db.commit()
            flash("Report submitted. It will not affect risk analysis until an administrator verifies it.", "success")
            return redirect(url_for("reporting.records"))
        except ValueError as error:
            flash(str(error), "danger")
    return render_template("report_accident.html", accident_types=ACCIDENT_TYPES, severities=SEVERITIES)


def _record_or_404(report_id: int):
    report = query_one(
        """SELECT r.*, u.full_name AS reporter_name, u.email AS reporter_email,
                  reviewer.full_name AS reviewer_name
           FROM accident_reports r JOIN users u ON u.id = r.reporter_id
           LEFT JOIN users reviewer ON reviewer.id = r.reviewed_by WHERE r.id = ?""",
        (report_id,),
    )
    if not report:
        return None
    if g.user["role"] != "admin" and report["reporter_id"] != g.user["id"]:
        return None
    return report


@bp.get("/records")
@login_required
def records():
    params: list = []
    where = []
    if g.user["role"] != "admin":
        where.append("r.reporter_id = ?")
        params.append(g.user["id"])
    status = request.args.get("status", "").lower()
    if status in {"pending", "verified", "rejected"}:
        where.append("r.status = ?")
        params.append(status)
    sql = """SELECT r.*, u.full_name AS reporter_name FROM accident_reports r
             JOIN users u ON u.id = r.reporter_id"""
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY r.occurred_at DESC, r.id DESC"
    reports = get_db().execute(sql, params).fetchall()
    return render_template("accident_records.html", reports=reports, selected_status=status)


@bp.get("/records/<int:report_id>")
@login_required
def record_detail(report_id: int):
    report = _record_or_404(report_id)
    if not report:
        flash("That report was not found or is not available to you.", "danger")
        return redirect(url_for("reporting.records"))
    return render_template("accident_detail.html", report=report)
