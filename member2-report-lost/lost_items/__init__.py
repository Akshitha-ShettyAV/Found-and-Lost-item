from __future__ import annotations

import hmac
import re
import secrets
import uuid
from datetime import date
from pathlib import Path
from typing import Any, Callable

from flask import (
    Blueprint,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    send_from_directory,
    session,
    url_for,
)


CATEGORIES = (
    "Electronics",
    "Books and Notes",
    "ID Cards",
    "Bags",
    "Accessories",
    "Clothing",
    "Other",
)
MAX_IMAGE_BYTES = 5 * 1024 * 1024
ALLOWED_IMAGE_EXTENSIONS = {".jpg": b"\xff\xd8\xff", ".jpeg": b"\xff\xd8\xff", ".png": b"\x89PNG\r\n\x1a\n"}


def create_lost_items_blueprint(
    db: Any,
    login_required: Callable,
    current_user_id: Callable[[], int],
    upload_folder: str | Path,
) -> tuple[Blueprint, type]:
    """Create the lost-item page against the host app's DB and authentication."""
    uploads_path = Path(upload_folder).resolve()
    uploads_path.mkdir(parents=True, exist_ok=True)

    class LostItem(db.Model):
        __tablename__ = "lost_items"

        id = db.Column(db.Integer, primary_key=True)
        user_id = db.Column(db.Integer, nullable=False, index=True)
        item_name = db.Column(db.String(120), nullable=False)
        category = db.Column(db.String(40), nullable=False, index=True)
        description = db.Column(db.Text, nullable=False)
        location = db.Column(db.String(160), nullable=False, index=True)
        date_lost = db.Column(db.Date, nullable=False, index=True)
        image_filename = db.Column(db.String(80), nullable=True)
        status = db.Column(db.String(20), nullable=False, default="lost", index=True)
        created_at = db.Column(db.DateTime, nullable=False, default=db.func.now())

    blueprint = Blueprint(
        "lost_items",
        __name__,
        template_folder="templates",
        static_folder="static",
        static_url_path="/lost-items/static",
    )

    def page_context(**extra: Any) -> dict[str, Any]:
        return {
            "categories": CATEGORIES,
            "home_url": current_app.config.get("LOST_ITEMS_HOME_URL", "/"),
            "today": date.today().isoformat(),
            **extra,
        }

    @blueprint.route("/report-lost", methods=["GET", "POST"])
    @login_required
    def report_lost():
        if not current_user_id():
            return "Authentication required", 401

        errors: dict[str, str] = {}
        values = {
            field: request.form.get(field, "").strip()
            for field in ("item_name", "category", "description", "location", "date_lost")
        }

        if request.method == "POST":
            sent_token = request.form.get("csrf_token", "")
            saved_token = session.get("lost_items_csrf_token", "")
            if not saved_token or not hmac.compare_digest(sent_token, saved_token):
                errors["form"] = "Your form expired. Refresh the page and try again."

            if not values["item_name"]:
                errors["item_name"] = "Enter the item's name."
            elif len(values["item_name"]) > 120:
                errors["item_name"] = "Use 120 characters or fewer."

            if values["category"] not in CATEGORIES:
                errors["category"] = "Choose a category from the list."

            if not values["description"]:
                errors["description"] = "Add a few identifying details."
            elif len(values["description"]) > 2000:
                errors["description"] = "Use 2,000 characters or fewer."

            if not values["location"]:
                errors["location"] = "Enter where you last saw the item."
            elif len(values["location"]) > 160:
                errors["location"] = "Use 160 characters or fewer."

            lost_date = None
            try:
                lost_date = date.fromisoformat(values["date_lost"])
                if lost_date > date.today():
                    errors["date_lost"] = "The date lost cannot be in the future."
            except ValueError:
                errors["date_lost"] = "Choose a valid date."

            image = request.files.get("image")
            image_filename = None
            image_bytes = None
            if image and image.filename:
                extension = Path(image.filename).suffix.lower()
                signature = ALLOWED_IMAGE_EXTENSIONS.get(extension)
                if not signature:
                    errors["image"] = "Upload a JPG, JPEG, or PNG image."
                else:
                    image_bytes = image.stream.read(MAX_IMAGE_BYTES + 1)
                    if len(image_bytes) > MAX_IMAGE_BYTES:
                        errors["image"] = "Choose an image smaller than 5 MB."
                    elif not image_bytes.startswith(signature):
                        errors["image"] = "The file contents do not match a JPG, JPEG, or PNG image."
                    else:
                        image_filename = f"{uuid.uuid4().hex}{extension}"

            if errors:
                return render_template(
                    "report_lost.html",
                    **page_context(values=values, errors=errors, csrf_token=csrf_token()),
                ), 400

            saved_image_path = uploads_path / image_filename if image_filename else None
            try:
                if saved_image_path and image_bytes is not None:
                    with saved_image_path.open("xb") as uploaded_file:
                        uploaded_file.write(image_bytes)

                report = LostItem(
                    user_id=current_user_id(),
                    item_name=values["item_name"],
                    category=values["category"],
                    description=values["description"],
                    location=values["location"],
                    date_lost=lost_date,
                    image_filename=image_filename,
                    status="lost",
                )
                db.session.add(report)
                db.session.commit()
            except Exception:
                db.session.rollback()
                if saved_image_path:
                    saved_image_path.unlink(missing_ok=True)
                current_app.logger.exception("Could not save lost-item report")
                errors["form"] = "We could not save your report. Please try again."
                return render_template(
                    "report_lost.html",
                    **page_context(values=values, errors=errors, csrf_token=csrf_token()),
                ), 500

            session.pop("lost_items_csrf_token", None)
            flash("Your lost-item report has been submitted.", "success")
            return redirect(url_for("lost_items.report_lost"))

        return render_template(
            "report_lost.html",
            **page_context(values=values, errors=errors, csrf_token=csrf_token()),
        )

    def csrf_token() -> str:
        if "lost_items_csrf_token" not in session:
            session["lost_items_csrf_token"] = secrets.token_urlsafe(32)
        return session["lost_items_csrf_token"]

    @blueprint.route("/lost-items/uploads/<filename>")
    @login_required
    def uploaded_image(filename: str):
        if not current_user_id() or not re.fullmatch(r"[0-9a-f]{32}\.(?:jpg|jpeg|png)", filename):
            return "Not found", 404
        return send_from_directory(uploads_path, filename, max_age=0)

    return blueprint, LostItem