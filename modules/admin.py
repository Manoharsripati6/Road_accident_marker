"""Administrator validation, report management and detector configuration."""

from datetime import datetime

from flask import Blueprint, flash, g, redirect, render_template, request, url_for

from database import get_db, query_all, query_one, set_setting, utcnow
from modules.accident_reporting import ACCIDENT_TYPES, SEVERITIES, _parse_report_form, _save_image, _upsert_location
from modules.authentication import admin_required
from modules.blackspot_detection import current_parameters, refresh_blackspots


bp = Blueprint("admin", __name__, url_prefix="/admin")


@bp.get("")
@admin_required
def dashboard():
    reports = query_all(
        """SELECT r.*, u.full_name AS reporter_name FROM accident_reports r
           JOIN users u ON u.id = r.reporter_id ORDER BY
           CASE r.status WHEN 'pending' THEN 0 WHEN 'verified' THEN 1 ELSE 2 END, r.created_at DESC"""
    )
    counts = {
        "pending": query_one("SELECT COUNT(*) AS count FROM accident_reports WHERE status = 'pending'")["count"],
        "verified": query_one("SELECT COUNT(*) AS count FROM accident_reports WHERE status = 'verified'")["count"],
        "users": query_one("SELECT COUNT(*) AS count FROM users WHERE role = 'user'")["count"],
        "spots": query_one("SELECT COUNT(*) AS count FROM black_spots")["count"],
    }
    return render_template("admin_dashboard.html", reports=reports, counts=counts)


@bp.post("/accidents/<int:report_id>/review")
@admin_required
def review_accident(report_id: int):
    status = request.form.get("status", "")
    notes = request.form.get("review_notes", "").strip()
    if status not in {"verified", "rejected"}:
        flash("Choose Verify or Reject for the report.", "danger")
    elif len(notes) > 500:
        flash("Review notes must be 500 characters or fewer.", "danger")
    elif not query_one("SELECT id FROM accident_reports WHERE id = ?", (report_id,)):
        flash("Report not found.", "danger")
    else:
        db = get_db()
        db.execute(
            """UPDATE accident_reports SET status = ?, review_notes = ?, reviewed_by = ?, reviewed_at = ?, updated_at = ?
               WHERE id = ?""",
            (status, notes, g.user["id"], utcnow(), utcnow(), report_id),
        )
        db.commit()
        refresh_blackspots()
        flash(f"Report #{report_id} marked {status} and black spots recalculated.", "success")
    return redirect(url_for("admin.dashboard"))


@bp.route("/accidents/<int:report_id>/edit", methods=["GET", "POST"])
@admin_required
def edit_accident(report_id: int):
    report = query_one("SELECT * FROM accident_reports WHERE id = ?", (report_id,))
    if not report:
        flash("Report not found.", "danger")
        return redirect(url_for("admin.dashboard"))
    if request.method == "POST":
        try:
            details = _parse_report_form()
            image_filename = _save_image() or report["image_filename"]
            location_id = _upsert_location(details)
            db = get_db()
            db.execute(
                """UPDATE accident_reports SET location_id = ?, location_name = ?, latitude = ?, longitude = ?,
                    occurred_at = ?, accident_type = ?, vehicle_types = ?, severity = ?, casualties = ?, description = ?,
                    image_filename = ?, updated_at = ? WHERE id = ?""",
                (location_id, details["location_name"], details["latitude"], details["longitude"], details["occurred_at"],
                 details["accident_type"], details["vehicle_types"], details["severity"], details["casualties"],
                 details["description"], image_filename, utcnow(), report_id),
            )
            db.commit()
            refresh_blackspots()
            flash(f"Report #{report_id} updated and analysis refreshed.", "success")
            return redirect(url_for("admin.dashboard"))
        except ValueError as error:
            flash(str(error), "danger")
    return render_template("edit_accident.html", report=report, accident_types=ACCIDENT_TYPES, severities=SEVERITIES)


@bp.post("/accidents/<int:report_id>/delete")
@admin_required
def delete_accident(report_id: int):
    db = get_db()
    if not db.execute("DELETE FROM accident_reports WHERE id = ?", (report_id,)).rowcount:
        flash("Report not found.", "danger")
    else:
        db.commit()
        refresh_blackspots()
        flash(f"Report #{report_id} deleted and analysis refreshed.", "success")
    return redirect(url_for("admin.dashboard"))


@bp.route("/settings", methods=["GET", "POST"])
@admin_required
def settings():
    if request.method == "POST":
        try:
            radius = int(request.form.get("cluster_radius_meters", ""))
            minimum = int(request.form.get("minimum_cluster_size", ""))
            if not 50 <= radius <= 5000:
                raise ValueError("Detection radius must be between 50 and 5,000 metres.")
            if not 2 <= minimum <= 20:
                raise ValueError("Minimum cluster size must be between 2 and 20 reports.")
            set_setting("cluster_radius_meters", str(radius))
            set_setting("minimum_cluster_size", str(minimum))
            refresh_blackspots()
            flash("Detection parameters saved and all black spots recalculated.", "success")
            return redirect(url_for("admin.settings"))
        except ValueError as error:
            flash(str(error), "danger")
    radius, minimum = current_parameters()
    return render_template("admin_settings.html", radius=radius, minimum=minimum)


@bp.get("/users")
@admin_required
def users():
    users = query_all(
        """SELECT u.id, u.full_name, u.email, u.role, u.created_at, COUNT(r.id) AS report_count
           FROM users u LEFT JOIN accident_reports r ON r.reporter_id = u.id
           GROUP BY u.id ORDER BY u.role DESC, u.created_at DESC"""
    )
    return render_template("admin_users.html", users=users)
