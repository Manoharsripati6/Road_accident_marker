"""Dashboard, charts, Leaflet data and black-spot analysis views."""

from flask import Blueprint, g, jsonify, render_template

from database import query_all, query_one
from modules.authentication import login_required
from modules.blackspot_detection import current_parameters
from modules.recommendations import generate_recommendations


bp = Blueprint("analytics", __name__)


def _chart_rows(sql: str) -> tuple[list[str], list[int]]:
    rows = query_all(sql)
    return [row["label"] for row in rows], [row["value"] for row in rows]


def overview() -> dict:
    severity_labels, severity_values = _chart_rows(
        """SELECT severity AS label, COUNT(*) AS value FROM accident_reports
           WHERE status = 'verified' GROUP BY severity
           ORDER BY CASE severity WHEN 'Low' THEN 1 WHEN 'Medium' THEN 2 ELSE 3 END"""
    )
    type_labels, type_values = _chart_rows(
        """SELECT accident_type AS label, COUNT(*) AS value FROM accident_reports
           WHERE status = 'verified' GROUP BY accident_type ORDER BY value DESC, label LIMIT 6"""
    )
    monthly_labels, monthly_values = _chart_rows(
        """SELECT strftime('%Y-%m', occurred_at) AS label, COUNT(*) AS value FROM accident_reports
           WHERE status = 'verified' GROUP BY strftime('%Y-%m', occurred_at)
           ORDER BY label DESC LIMIT 12"""
    )
    monthly_labels.reverse()
    monthly_values.reverse()
    return {
        "total": query_one("SELECT COUNT(*) AS count FROM accident_reports WHERE status = 'verified'")["count"],
        "blackspots": query_one("SELECT COUNT(*) AS count FROM black_spots")["count"],
        "high_risk": query_one("SELECT COUNT(*) AS count FROM black_spots WHERE risk_level = 'High'")["count"],
        "severity_labels": severity_labels or ["Low", "Medium", "High"],
        "severity_values": severity_values or [0, 0, 0],
        "type_labels": type_labels or ["No verified data"],
        "type_values": type_values or [0],
        "monthly_labels": monthly_labels or ["No verified data"],
        "monthly_values": monthly_values or [0],
    }


@bp.get("/dashboard")
@login_required
def dashboard():
    summary = overview()
    if g.user["role"] == "admin":
        summary["pending"] = query_one("SELECT COUNT(*) AS count FROM accident_reports WHERE status = 'pending'")["count"]
    else:
        summary["pending"] = query_one(
            "SELECT COUNT(*) AS count FROM accident_reports WHERE status = 'pending' AND reporter_id = ?", (g.user["id"],)
        )["count"]
    recent = query_all(
        """SELECT id, location_name, occurred_at, accident_type, severity FROM accident_reports
           WHERE status = 'verified' ORDER BY occurred_at DESC LIMIT 6"""
    )
    return render_template("dashboard.html", summary=summary, recent=recent, recommendations=generate_recommendations())


@bp.get("/analytics")
@login_required
def analytics():
    summary = overview()
    locations = query_all(
        """SELECT location_name, COUNT(*) AS accident_count, SUM(casualties) AS casualties
           FROM accident_reports WHERE status = 'verified'
           GROUP BY location_name ORDER BY accident_count DESC, casualties DESC LIMIT 10"""
    )
    hours = query_all(
        """SELECT printf('%02d:00', CAST(strftime('%H', occurred_at) AS INTEGER)) AS label, COUNT(*) AS value
           FROM accident_reports WHERE status = 'verified' GROUP BY strftime('%H', occurred_at) ORDER BY label"""
    )
    summary["hour_labels"] = [row["label"] for row in hours] or ["No verified data"]
    summary["hour_values"] = [row["value"] for row in hours] or [0]
    return render_template("analytics.html", summary=summary, locations=locations, recommendations=generate_recommendations())


@bp.get("/blackspots")
@login_required
def blackspots():
    spots = query_all("SELECT * FROM black_spots ORDER BY CASE risk_level WHEN 'High' THEN 1 WHEN 'Medium' THEN 2 ELSE 3 END, risk_score DESC")
    radius, minimum = current_parameters()
    return render_template("blackspots.html", spots=spots, radius=radius, minimum=minimum)


@bp.get("/map")
@login_required
def accident_map():
    return render_template("map.html")


@bp.get("/api/map-data")
@login_required
def map_data():
    accidents = query_all(
        """SELECT id, location_name, latitude, longitude, occurred_at, accident_type, severity, casualties
           FROM accident_reports WHERE status = 'verified' ORDER BY occurred_at DESC"""
    )
    spots = query_all("SELECT * FROM black_spots ORDER BY risk_score DESC")
    return jsonify({
        "accidents": [{
            "id": row["id"], "location": row["location_name"], "lat": row["latitude"], "lng": row["longitude"],
            "date": row["occurred_at"], "type": row["accident_type"], "severity": row["severity"], "casualties": row["casualties"],
        } for row in accidents],
        "blackspots": [{
            "id": row["id"], "latitude": row["center_latitude"], "longitude": row["center_longitude"],
            "radius": row["radius_meters"], "count": row["accident_count"], "highCount": row["high_count"],
            "risk": row["risk_level"], "score": row["risk_score"], "casualties": row["casualties"],
        } for row in spots],
    })
