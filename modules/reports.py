"""Administrator reporting filters and CSV export using the standard csv module."""

import csv
from io import StringIO

from flask import Blueprint, Response, request, render_template

from database import get_db
from modules.authentication import admin_required


bp = Blueprint("reports", __name__)


def filtered_reports(args):
    where = []
    params = []
    filters = {
        "date_from": args.get("date_from", "").strip(),
        "date_to": args.get("date_to", "").strip(),
        "severity": args.get("severity", "").strip(),
        "location": args.get("location", "").strip(),
        "status": args.get("status", "verified").strip(),
    }
    if filters["date_from"]:
        where.append("date(r.occurred_at) >= date(?)")
        params.append(filters["date_from"])
    if filters["date_to"]:
        where.append("date(r.occurred_at) <= date(?)")
        params.append(filters["date_to"])
    if filters["severity"] in {"Low", "Medium", "High"}:
        where.append("r.severity = ?")
        params.append(filters["severity"])
    if filters["location"]:
        where.append("r.location_name LIKE ?")
        params.append(f"%{filters['location']}%")
    if filters["status"] in {"pending", "verified", "rejected"}:
        where.append("r.status = ?")
        params.append(filters["status"])
    sql = """SELECT r.*, u.full_name AS reporter_name, u.email AS reporter_email
             FROM accident_reports r JOIN users u ON u.id = r.reporter_id"""
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY r.occurred_at DESC, r.id DESC"
    return get_db().execute(sql, params).fetchall(), filters


@bp.get("/reports")
@admin_required
def reports():
    rows, filters = filtered_reports(request.args)
    return render_template("reports.html", reports=rows, filters=filters)


@bp.get("/reports/export.csv")
@admin_required
def export_csv():
    rows, _filters = filtered_reports(request.args)
    output = StringIO(newline="")
    writer = csv.writer(output)
    writer.writerow([
        "Report ID", "Location", "Latitude", "Longitude", "Occurred at", "Accident type", "Vehicle types",
        "Severity", "Casualties", "Status", "Reporter", "Description", "Review notes",
    ])
    for row in rows:
        writer.writerow([
            row["id"], row["location_name"], row["latitude"], row["longitude"], row["occurred_at"],
            row["accident_type"], row["vehicle_types"], row["severity"], row["casualties"], row["status"],
            row["reporter_name"], row["description"], row["review_notes"],
        ])
    response = Response(output.getvalue(), mimetype="text/csv; charset=utf-8")
    response.headers["Content-Disposition"] = "attachment; filename=accident-reports.csv"
    return response
