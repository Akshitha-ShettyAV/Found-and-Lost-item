import os
import sqlite3
import uuid
from datetime import date

from flask import Flask, flash, redirect, render_template, request, url_for
from werkzeug.utils import secure_filename


ALLOWED_IMAGE_EXTENSIONS = {"jpg", "jpeg", "png", "webp"}
CATEGORIES = [
    "Electronics",
    "Clothing",
    "Books",
    "Bags",
    "Keys",
    "Documents",
    "Other",
]


def create_app(test_config=None):
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_mapping(
        SECRET_KEY=os.environ.get("SECRET_KEY", "dev-only-change-me"),
        DATABASE=os.path.join(app.instance_path, "found_items.db"),
        MAX_CONTENT_LENGTH=5 * 1024 * 1024,
    )
    if test_config:
        app.config.update(test_config)

    os.makedirs(app.instance_path, exist_ok=True)
    os.makedirs(os.path.join(app.static_folder, "uploads"), exist_ok=True)

    connection = sqlite3.connect(app.config["DATABASE"])
    try:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS found_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                item_name TEXT NOT NULL,
                category TEXT NOT NULL,
                description TEXT NOT NULL,
                location TEXT NOT NULL,
                found_date TEXT NOT NULL,
                image_filename TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
    finally:
        connection.close()

    @app.get("/")
    def home():
        return redirect(url_for("report_found"))

    @app.route("/report-found", methods=["GET", "POST"])
    def report_found():
        if request.method == "GET":
            return render_template(
                "report_found.html",
                categories=CATEGORIES,
                today=date.today().isoformat(),
            )

        item_name = request.form.get("item_name", "").strip()
        category = request.form.get("category", "").strip()
        description = request.form.get("description", "").strip()
        location = request.form.get("location", "").strip()
        found_date = request.form.get("found_date", "").strip()
        image = request.files.get("image")

        errors = []
        if not item_name or len(item_name) > 100:
            errors.append("Enter an item name with no more than 100 characters.")
        if category not in CATEGORIES:
            errors.append("Choose a valid category.")
        if not description or len(description) > 2000:
            errors.append("Enter a description with no more than 2,000 characters.")
        if not location or len(location) > 200:
            errors.append("Enter a found location with no more than 200 characters.")
        try:
            parsed_date = date.fromisoformat(found_date)
            if parsed_date > date.today():
                errors.append("The found date cannot be in the future.")
        except ValueError:
            errors.append("Enter a valid found date.")

        image_extension = None
        if not image or not image.filename:
            errors.append("Upload a photo of the found item.")
        else:
            safe_name = secure_filename(image.filename)
            if not safe_name or "." not in safe_name:
                errors.append("Choose a valid image file.")
            else:
                image_extension = safe_name.rsplit(".", 1)[1].lower()
                if image_extension not in ALLOWED_IMAGE_EXTENSIONS:
                    errors.append("Image must be JPG, PNG, or WebP format.")
                image.stream.seek(0, os.SEEK_END)
                if image.stream.tell() == 0:
                    errors.append("The uploaded image cannot be empty.")
                image.stream.seek(0)

        if errors:
            for error in errors:
                flash(error, "error")
            return render_template(
                "report_found.html",
                categories=CATEGORIES,
                today=date.today().isoformat(),
                form=request.form,
            ), 400

        image_filename = f"{uuid.uuid4().hex}.{image_extension}"
        image.save(os.path.join(app.static_folder, "uploads", image_filename))

        connection = sqlite3.connect(app.config["DATABASE"])
        try:
            connection.execute(
                """
                INSERT INTO found_items
                    (item_name, category, description, location, found_date, image_filename)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    item_name,
                    category,
                    description,
                    location,
                    found_date,
                    image_filename,
                ),
            )
            connection.commit()
        finally:
            connection.close()

        flash("Found item report submitted successfully.", "success")
        return redirect(url_for("report_found"))

    @app.errorhandler(413)
    def file_too_large(_error):
        flash("The image must be smaller than 5 MB.", "error")
        return render_template(
            "report_found.html",
            categories=CATEGORIES,
            today=date.today().isoformat(),
        ), 413

    return app


app = create_app()


if __name__ == "__main__":
    app.run(debug=True)
