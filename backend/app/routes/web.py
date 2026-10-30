from pathlib import Path

from flask import Blueprint, send_from_directory

web_bp = Blueprint("web", __name__)
FRONTEND_DIR = Path(__file__).resolve().parents[3] / "frontend"


@web_bp.get("/")
def index():
    return send_from_directory(FRONTEND_DIR, "index.html")


@web_bp.get("/<path:asset>")
def frontend_asset(asset):
    return send_from_directory(FRONTEND_DIR, asset)
