"""Configuration for the Smart Accident Black Spot Mapping System."""

import os
from pathlib import Path
import secrets

from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY") or secrets.token_hex(32)
    DATABASE = os.getenv("DATABASE_PATH", str(BASE_DIR / "instance" / "accidents.db"))
    UPLOAD_FOLDER = str(BASE_DIR / "static" / "uploads")
    MAX_CONTENT_LENGTH = 5 * 1024 * 1024  # 5 MiB
    ALLOWED_IMAGE_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp"}
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = os.getenv("SESSION_COOKIE_SECURE", "false").lower() == "true"
    PERMANENT_SESSION_LIFETIME = 60 * 60 * 8
    ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "admin@roadsafe.local").strip().lower()
    ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "ChangeMe123!")
    ADMIN_NAME = os.getenv("ADMIN_NAME", "Road Safety Administrator")
