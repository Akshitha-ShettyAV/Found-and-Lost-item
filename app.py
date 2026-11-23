import os
import re
import sqlite3
from datetime import datetime
from pathlib import Path

from flask import Flask, jsonify, render_template, request


app = Flask(__name__)
app.config["DATABASE"] = os.environ.get(
    "CAMPUS_DATABASE", str(Path(app.root_path) / "instance" / "campus.db")
)

FIELD_ALIASES = {
    "name": ("item_name", "name", "title", "item"),
    "category": ("category", "item_category", "type_category"),
    "location": ("location", "lost_location", "found_location", "place", "where_found"),
    "date": ("reported_date", "date_reported", "created_at", "date", "report_date"),
    "description": ("description", "details", "item_description", "comments"),
    "keywords": ("keywords", "tags", "search_terms"),
    "image": ("image", "image_path", "image_url", "photo", "photo_path", "photo_url"),
    "contact": ("contact", "contact_info", "email", "phone", "owner_contact"),
    "status": ("item_type", "report_type", "lost_found", "type", "status"),
    "id": ("id", "item_id"),
}
LOST_WORDS = ("lost", "missing")
FOUND_WORDS = ("found", "recovered")


def _normalized(value):
    return re.sub(r"[^a-z0-9]+", "", str(value or "").lower())


def _quote_identifier(identifier):
    return '"' + identifier.replace('"', '""') + '"'


def _connect_database():
    database = Path(app.config["DATABASE"])
    if not database.is_file():
        return None
    try:
        connection = sqlite3.connect(database.resolve().as_uri() + "?mode=ro", uri=True)
        connection.row_factory = sqlite3.Row
        return connection
    except sqlite3.Error:
        app.logger.exception("Unable to open the campus database read-only")
        raise


def _find_column(columns, aliases):
    normalized_columns = {_normalized(column): column for column in columns}
    for alias in aliases:
        if _normalized(alias) in normalized_columns:
            return normalized_columns[_normalized(alias)]
    return None


def _classify_table(table_name, row, status_column):
    name = _normalized(table_name)
    has_lost_name = any(word in name for word in LOST_WORDS)
    has_found_name = any(word in name for word in FOUND_WORDS)
    if has_lost_name != has_found_name:
        return "Lost" if has_lost_name else "Found"

    status = _normalized(row.get(status_column)) if status_column else ""
    if any(word in status for word in LOST_WORDS):
        return "Lost"
    if any(word in status for word in FOUND_WORDS):
        return "Found"
    return None


def _category_group(value):
    category = _normalized(value)
    for known in ("electronics", "books", "accessories", "documents"):
        if known in category:
            return known.title()
    return "Others"


def _location_group(value):
    location = _normalized(value)
    for known in ("library", "classroom", "canteen"):
        if known in location:
            return known.title()
    if "parking" in location:
        return "Parking Area"
    return "Other Locations"


def _item_date(value):
    value = str(value or "").strip()
    if not value:
        return ""
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).isoformat()
    except ValueError:
        return value


def _read_items():
    connection = _connect_database()
    if connection is None:
        return []

    try:
        tables = connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' "
            "AND name NOT LIKE 'sqlite_%'"
        ).fetchall()
        items = []
        for (table_name,) in tables:
            column_info = connection.execute(
                "PRAGMA table_info(" + _quote_identifier(table_name) + ")"
            ).fetchall()
            columns = [row[1] for row in column_info]
            mapping = {
                key: _find_column(columns, aliases)
                for key, aliases in FIELD_ALIASES.items()
            }
            if not mapping["name"]:
                continue

            primary_key = next((row[1] for row in column_info if row[5]), None)
            identifier_column = mapping["id"] or primary_key
            query = "SELECT * FROM " + _quote_identifier(table_name)
            if not identifier_column:
                query = (
                    "SELECT rowid AS __browse_rowid__, * FROM "
                    + _quote_identifier(table_name)
                )
            for row in connection.execute(query):
                record = dict(row)
                item_type = _classify_table(table_name, record, mapping["status"])
                if not item_type:
                    continue
                category = record.get(mapping["category"]) if mapping["category"] else ""
                location = record.get(mapping["location"]) if mapping["location"] else ""
                date = record.get(mapping["date"]) if mapping["date"] else ""
                identifier = (
                    record.get(identifier_column)
                    if identifier_column
                    else record["__browse_rowid__"]
                )
                items.append(
                    {
                        "id": str(identifier),
                        "source": table_name,
                        "name": str(record.get(mapping["name"]) or "Unnamed item"),
                        "category": str(category or "Others"),
                        "categoryGroup": _category_group(category),
                        "location": str(location or "Location not provided"),
                        "locationGroup": _location_group(location),
                        "date": _item_date(date),
                        "description": str(
                            record.get(mapping["description"]) or "No description provided."
                        )
                        if mapping["description"]
                        else "No description provided.",
                        "keywords": str(record.get(mapping["keywords"]) or "")
                        if mapping["keywords"]
                        else "",
                        "image": str(record.get(mapping["image"]) or "")
                        if mapping["image"]
                        else "",
                        "contact": str(record.get(mapping["contact"]) or "")
                        if mapping["contact"]
                        else "",
                        "type": item_type,
                    }
                )
        return sorted(items, key=lambda item: item["date"], reverse=True)
    except sqlite3.Error:
        app.logger.exception("Unable to read items from the campus database")
        raise
    finally:
        connection.close()


def _filter_items(items, search="", item_type="", category="", location=""):
    search_terms = search.strip().lower()
    filtered = []
    for item in items:
        searchable = " ".join(
            (
                item["name"],
                item["category"],
                item["location"],
                item["description"],
                item["keywords"],
            )
        ).lower()
        if search_terms and search_terms not in searchable:
            continue
        if item_type and item["type"].lower() != item_type.lower():
            continue
        if category and item["categoryGroup"].lower() != category.lower():
            continue
        if location and item["locationGroup"].lower() != location.lower():
            continue
        filtered.append(item)
    return filtered


@app.get("/")
@app.get("/browse")
def browse_items():
    return render_template("browse.html")


@app.get("/api/items")
def browse_items_api():
    try:
        items = _read_items()
    except sqlite3.Error:
        return jsonify({"items": [], "error": "Items could not be loaded from the database."}), 500
    return jsonify(
        {
            "items": _filter_items(
                items,
                search=request.args.get("search", ""),
                item_type=request.args.get("type", ""),
                category=request.args.get("category", ""),
                location=request.args.get("location", ""),
            ),
            "databaseAvailable": Path(app.config["DATABASE"]).is_file(),
        }
    )


@app.get("/api/items/<source>/<item_id>")
def item_details_api(source, item_id):
    try:
        item = next(
            (
                candidate
                for candidate in _read_items()
                if candidate["source"] == source and candidate["id"] == item_id
            ),
            None,
        )
    except sqlite3.Error:
        return jsonify({"error": "Item details could not be loaded from the database."}), 500
    if item is None:
        return jsonify({"error": "The requested item was not found."}), 404
    return jsonify({"item": item})


if __name__ == "__main__":
    app.run(debug=os.environ.get("FLASK_DEBUG") == "1")
