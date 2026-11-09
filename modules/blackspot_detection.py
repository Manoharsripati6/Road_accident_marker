"""Pure-Python spatial clustering and persistence for verified accident reports."""

from __future__ import annotations

from math import asin, cos, radians, sin, sqrt
from typing import Iterable

from database import get_db, setting, utcnow


EARTH_RADIUS_METERS = 6_371_008.8
SEVERITY_WEIGHTS = {"Low": 1, "Medium": 2, "High": 3}


def haversine_meters(lat_a: float, lon_a: float, lat_b: float, lon_b: float) -> float:
    """Great-circle distance between two WGS84 points in metres."""
    d_lat = radians(lat_b - lat_a)
    d_lon = radians(lon_b - lon_a)
    a = sin(d_lat / 2) ** 2 + cos(radians(lat_a)) * cos(radians(lat_b)) * sin(d_lon / 2) ** 2
    return 2 * EARTH_RADIUS_METERS * asin(sqrt(a))


def _connected_components(reports: list, radius_meters: int) -> list[list]:
    """Join all radius-neighbours, including density-connected chains."""
    parent = list(range(len(reports)))

    def find(index: int) -> int:
        while parent[index] != index:
            parent[index] = parent[parent[index]]
            index = parent[index]
        return index

    def union(first: int, second: int) -> None:
        root_a, root_b = find(first), find(second)
        if root_a != root_b:
            parent[root_b] = root_a

    for i, report in enumerate(reports):
        for j in range(i + 1, len(reports)):
            other = reports[j]
            if haversine_meters(report["latitude"], report["longitude"], other["latitude"], other["longitude"]) <= radius_meters:
                union(i, j)

    grouped: dict[int, list] = {}
    for index, report in enumerate(reports):
        grouped.setdefault(find(index), []).append(report)
    return list(grouped.values())


def classify_risk(members: Iterable, minimum_cluster_size: int) -> tuple[float, str]:
    members = list(members)
    severity_score = sum(SEVERITY_WEIGHTS[item["severity"]] for item in members)
    casualty_score = sum(item["casualties"] for item in members) * 0.5
    score = severity_score + casualty_score
    # Thresholds scale with the configured minimum. A qualifying low-severity
    # cluster remains low risk, and isolated reports are never passed here.
    if score >= minimum_cluster_size * 2.8 or sum(item["severity"] == "High" for item in members) >= 2:
        return score, "High"
    if score >= minimum_cluster_size * 1.8:
        return score, "Medium"
    return score, "Low"


def detect_blackspots(reports: list, radius_meters: int, minimum_cluster_size: int) -> list[dict]:
    spots = []
    for members in _connected_components(reports, radius_meters):
        if len(members) < minimum_cluster_size:
            continue
        score, risk_level = classify_risk(members, minimum_cluster_size)
        spots.append(
            {
                "latitude": sum(item["latitude"] for item in members) / len(members),
                "longitude": sum(item["longitude"] for item in members) / len(members),
                "members": members,
                "accident_count": len(members),
                "high_count": sum(item["severity"] == "High" for item in members),
                "medium_count": sum(item["severity"] == "Medium" for item in members),
                "low_count": sum(item["severity"] == "Low" for item in members),
                "casualties": sum(item["casualties"] for item in members),
                "risk_score": round(score, 1),
                "risk_level": risk_level,
            }
        )
    return sorted(spots, key=lambda item: (item["risk_score"], item["accident_count"]), reverse=True)


def current_parameters() -> tuple[int, int]:
    return int(setting("cluster_radius_meters", "500")), int(setting("minimum_cluster_size", "3"))


def refresh_blackspots() -> list[dict]:
    """Rebuild derived records from verified reports after data/configuration changes."""
    db = get_db()
    reports = db.execute(
        "SELECT id, latitude, longitude, severity, casualties FROM accident_reports WHERE status = 'verified'"
    ).fetchall()
    radius_meters, minimum_cluster_size = current_parameters()
    spots = detect_blackspots(reports, radius_meters, minimum_cluster_size)
    db.execute("DELETE FROM risk_classifications")
    db.execute("DELETE FROM black_spots")
    now = utcnow()
    for spot in spots:
        cursor = db.execute(
            """INSERT INTO black_spots
            (center_latitude, center_longitude, radius_meters, accident_count, high_count, medium_count,
             low_count, casualties, risk_score, risk_level, generated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                spot["latitude"], spot["longitude"], radius_meters, spot["accident_count"],
                spot["high_count"], spot["medium_count"], spot["low_count"], spot["casualties"],
                spot["risk_score"], spot["risk_level"], now,
            ),
        )
        black_spot_id = cursor.lastrowid
        db.executemany(
            "INSERT INTO risk_classifications (black_spot_id, accident_report_id, risk_level, risk_score) VALUES (?, ?, ?, ?)",
            [(black_spot_id, member["id"], spot["risk_level"], spot["risk_score"]) for member in spot["members"]],
        )
    db.commit()
    return spots
