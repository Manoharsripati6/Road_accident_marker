"""Rule-based safety actions derived from verified data rather than static copy."""

from database import query_all, query_one


def generate_recommendations() -> list[dict]:
    total = query_one("SELECT COUNT(*) AS count FROM accident_reports WHERE status = 'verified'")["count"]
    if total == 0:
        return [{
            "title": "Build a verified evidence base",
            "detail": "No verified reports are available yet. Validate reports before issuing location-specific safety actions.",
            "tone": "neutral",
        }]

    results = []
    pedestrian = query_one(
        "SELECT COUNT(*) AS count FROM accident_reports WHERE status = 'verified' AND accident_type = 'Pedestrian'"
    )["count"]
    if pedestrian >= 2:
        results.append({"title": "Prioritise safer pedestrian crossings", "detail": f"{pedestrian} verified pedestrian crashes were recorded. Review crossings, refuge islands and footpath continuity.", "tone": "warning"})

    nighttime = query_one(
        """SELECT COUNT(*) AS count FROM accident_reports WHERE status = 'verified'
           AND (CAST(strftime('%H', occurred_at) AS INTEGER) >= 19 OR CAST(strftime('%H', occurred_at) AS INTEGER) < 5)"""
    )["count"]
    if nighttime >= 2:
        results.append({"title": "Improve night-time visibility", "detail": f"{nighttime} verified crashes occurred between 19:00 and 05:00. Audit lighting, markings and retroreflective signs.", "tone": "info"})

    collisions = query_one(
        "SELECT COUNT(*) AS count FROM accident_reports WHERE status = 'verified' AND accident_type = 'Collision'"
    )["count"]
    if collisions >= 2:
        results.append({"title": "Apply traffic-calming measures", "detail": f"{collisions} verified collisions indicate a recurring conflict pattern. Assess speed management and turning controls.", "tone": "danger"})

    locations = query_all(
        """SELECT location_name, COUNT(*) AS count FROM accident_reports
           WHERE status = 'verified' GROUP BY location_name HAVING COUNT(*) >= 2
           ORDER BY count DESC LIMIT 3"""
    )
    if locations:
        names = ", ".join(row["location_name"] for row in locations)
        total_at_locations = sum(row["count"] for row in locations)
        results.append({"title": "Review recurring locations", "detail": f"{total_at_locations} verified crashes recur at {names}. Conduct a site inspection for intersection geometry and sight-distance issues.", "tone": "warning"})

    high = query_one(
        "SELECT COUNT(*) AS count FROM accident_reports WHERE status = 'verified' AND severity = 'High'"
    )["count"]
    if high:
        results.append({"title": "Escalate high-severity investigation", "detail": f"{high} verified high-severity crashes require focused engineering and enforcement review.", "tone": "danger"})

    return results or [{
        "title": "Continue targeted monitoring",
        "detail": f"{total} verified report(s) are available, but no recommendation trigger has reached its evidence threshold yet.",
        "tone": "neutral",
    }]
