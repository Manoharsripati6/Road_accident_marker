"""End-to-end smoke tests for the critical RoadSafe workflows."""

from datetime import datetime
import os
import tempfile
import unittest

from app import create_app
from database import query_one
from modules.blackspot_detection import detect_blackspots


class RoadSafeWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.database_path = os.path.join(self.temp_dir.name, "test.db")
        self.app = create_app({
            "TESTING": True,
            "SECRET_KEY": "test-secret",
            "DATABASE": self.database_path,
            "UPLOAD_FOLDER": os.path.join(self.temp_dir.name, "uploads"),
            "ADMIN_EMAIL": "admin@test.local",
            "ADMIN_PASSWORD": "StrongAdminPass1!",
            "ADMIN_NAME": "Test Administrator",
        })
        self.client = self.app.test_client()

    def tearDown(self):
        self.temp_dir.cleanup()

    def csrf(self, page):
        self.client.get(page)
        with self.client.session_transaction() as session:
            return session["csrf_token"]

    def test_registration_submission_validation_map_and_export(self):
        token = self.csrf("/register")
        response = self.client.post("/register", data={
            "csrf_token": token, "name": "Asha Reporter", "email": "asha@example.test",
            "password": "SecurePass1!", "confirm_password": "SecurePass1!",
        })
        self.assertEqual(response.status_code, 302)

        occurred_at = datetime.now().replace(microsecond=0).isoformat(timespec="minutes")
        report_token = self.csrf("/report")
        for latitude, longitude, severity in ((12.97160, 77.59460, "High"), (12.97200, 77.59420, "Medium"), (12.97125, 77.59490, "High")):
            response = self.client.post("/report", data={
                "csrf_token": report_token, "location_name": "Central Junction", "latitude": latitude,
                "longitude": longitude, "occurred_at": occurred_at, "accident_type": "Collision",
                "vehicle_types": "Car, motorcycle", "severity": severity, "casualties": "1", "description": "Test incident.",
            })
            self.assertEqual(response.status_code, 302)

        with self.app.app_context():
            self.assertEqual(query_one("SELECT COUNT(*) AS count FROM accident_reports")["count"], 3)
            self.assertEqual(query_one("SELECT COUNT(*) AS count FROM accident_reports WHERE status = 'pending'")["count"], 3)

        logout_token = self.csrf("/dashboard")
        self.client.post("/logout", data={"csrf_token": logout_token})
        login_token = self.csrf("/login")
        response = self.client.post("/login", data={
            "csrf_token": login_token, "email": "admin@test.local", "password": "StrongAdminPass1!",
        })
        self.assertEqual(response.status_code, 302)

        admin_token = self.csrf("/admin")
        for report_id in (1, 2, 3):
            response = self.client.post(f"/admin/accidents/{report_id}/review", data={
                "csrf_token": admin_token, "status": "verified", "review_notes": "Evidence reviewed.",
            })
            self.assertEqual(response.status_code, 302)

        with self.app.app_context():
            self.assertEqual(query_one("SELECT COUNT(*) AS count FROM accident_reports WHERE status = 'verified'")["count"], 3)
            self.assertEqual(query_one("SELECT COUNT(*) AS count FROM black_spots")["count"], 1)

        for page in ("/dashboard", "/map", "/blackspots", "/analytics", "/records", "/admin", "/admin/settings", "/admin/users", "/reports"):
            self.assertEqual(self.client.get(page).status_code, 200, page)
        map_data = self.client.get("/api/map-data").get_json()
        self.assertEqual(len(map_data["accidents"]), 3)
        self.assertEqual(len(map_data["blackspots"]), 1)
        export = self.client.get("/reports/export.csv?status=verified")
        self.assertEqual(export.status_code, 200)
        self.assertIn(b"Central Junction", export.data)

    def test_detector_ignores_isolated_accident(self):
        reports = [
            {"id": 1, "latitude": 12.9716, "longitude": 77.5946, "severity": "High", "casualties": 1},
            {"id": 2, "latitude": 12.9720, "longitude": 77.5942, "severity": "Medium", "casualties": 0},
            {"id": 3, "latitude": 12.9712, "longitude": 77.5950, "severity": "High", "casualties": 2},
            {"id": 4, "latitude": 13.4000, "longitude": 78.1000, "severity": "High", "casualties": 4},
        ]
        spots = detect_blackspots(reports, radius_meters=500, minimum_cluster_size=3)
        self.assertEqual(len(spots), 1)
        self.assertEqual(spots[0]["accident_count"], 3)
        self.assertEqual(spots[0]["risk_level"], "High")


if __name__ == "__main__":
    unittest.main()
