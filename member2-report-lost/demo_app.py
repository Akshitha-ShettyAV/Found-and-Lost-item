"""Local preview only. Replace its demo session login with portal auth."""

from __future__ import annotations

import os
from functools import wraps
from pathlib import Path

from flask import Flask, redirect, session, url_for
from flask_sqlalchemy import SQLAlchemy

from lost_items import create_lost_items_blueprint


db = SQLAlchemy()


def demo_login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("demo_user_id"):
            return redirect(url_for("demo_home"))
        return view(*args, **kwargs)

    return wrapped


def create_app() -> Flask:
    app = Flask(__name__, instance_relative_config=True)
    Path(app.instance_path).mkdir(parents=True, exist_ok=True)
    app.config.update(
        SECRET_KEY=os.environ.get("FLASK_SECRET_KEY", "local-demo-only-change-before-deploy"),
        SQLALCHEMY_DATABASE_URI="sqlite:///lost_items_demo.db",
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        MAX_CONTENT_LENGTH=6 * 1024 * 1024,
        LOST_ITEMS_HOME_URL="/",
    )
    db.init_app(app)

    blueprint, _ = create_lost_items_blueprint(
        db=db,
        login_required=demo_login_required,
        current_user_id=lambda: session.get("demo_user_id"),
        upload_folder=Path(app.instance_path) / "private_uploads" / "lost_items",
    )
    app.register_blueprint(blueprint)

    @app.get("/")
    def demo_home():
        if session.get("demo_user_id"):
            return redirect(url_for("lost_items.report_lost"))
        return """<!doctype html><html lang="en"><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Campus Find local preview</title>
<body style="font:16px sans-serif;max-width:560px;margin:12vh auto;padding:24px;color:#21332d">
<h1>Campus Find local preview</h1><p>This demo creates a local test session only.</p>
<form method="post" action="/demo-login"><button type="submit">Continue as demo user</button></form>
</body></html>"""

    @app.post("/demo-login")
    def demo_login():
        session["demo_user_id"] = 1
        return redirect(url_for("lost_items.report_lost"))

    @app.post("/demo-logout")
    def demo_logout():
        session.clear()
        return redirect(url_for("demo_home"))

    with app.app_context():
        db.create_all()

    return app


app = create_app()


if __name__ == "__main__":
    app.run(debug=True)