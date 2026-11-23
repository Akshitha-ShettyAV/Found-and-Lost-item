import io
import tempfile
import unittest
from functools import wraps
from pathlib import Path

from flask import Flask, redirect, session
from flask_sqlalchemy import SQLAlchemy

from lost_items import create_lost_items_blueprint


class LostItemsTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        root = Path(self.temp_dir.name)
        self.app = Flask(__name__)
        self.app.config.update(
            SECRET_KEY="test-secret",
            SQLALCHEMY_DATABASE_URI=f"sqlite:///{root / 'test.db'}",
            SQLALCHEMY_TRACK_MODIFICATIONS=False,
            TESTING=True,
        )
        self.db = SQLAlchemy(self.app)

        def login_required(view):
            @wraps(view)
            def wrapped(*args, **kwargs):
                if not session.get("user_id"):
                    return redirect("/login")
                return view(*args, **kwargs)

            return wrapped

        self.blueprint, self.LostItem = create_lost_items_blueprint(
            db=self.db,
            login_required=login_required,
            current_user_id=lambda: session.get("user_id"),
            upload_folder=root / "private_uploads",
        )
        self.app.register_blueprint(self.blueprint)

        @self.app.get("/login")
        def login_page():
            return "login required", 401

        with self.app.app_context():
            self.db.create_all()
        self.client = self.app.test_client()

    def tearDown(self):
        with self.app.app_context():
            self.db.session.remove()
            self.db.engine.dispose()
        self.temp_dir.cleanup()

    def _csrf_token(self):
        response = self.client.get("/report-lost")
        self.assertEqual(response.status_code, 200)
        with self.client.session_transaction() as browser_session:
            return browser_session["lost_items_csrf_token"]

    def _login(self):
        with self.client.session_transaction() as browser_session:
            browser_session["user_id"] = 42

    def _valid_form(self, csrf_token):
        return {
            "csrf_token": csrf_token,
            "item_name": "Green notebook",
            "category": "Books and Notes",
            "description": "Green cover with a white label on the front.",
            "location": "Library, second floor",
            "date_lost": "2026-11-20",
        }

    def test_requires_login(self):
        response = self.client.get("/report-lost")
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.headers["Location"], "/login")

    def test_missing_fields_are_rejected(self):
        self._login()
        token = self._csrf_token()
        response = self.client.post("/report-lost", data={"csrf_token": token})
        self.assertEqual(response.status_code, 400)
        self.assertIn(b"Enter the item&#39;s name", response.data)
        with self.app.app_context():
            self.assertEqual(self.LostItem.query.count(), 0)

    def test_valid_report_is_owned_and_listable(self):
        self._login()
        token = self._csrf_token()
        response = self.client.post("/report-lost", data=self._valid_form(token))
        self.assertEqual(response.status_code, 302)
        with self.app.app_context():
            report = self.LostItem.query.one()
            self.assertEqual(report.user_id, 42)
            self.assertEqual(report.status, "lost")
            self.assertEqual(report.category, "Books and Notes")

    def test_image_is_stored_outside_static_and_served_after_login(self):
        self._login()
        token = self._csrf_token()
        form = self._valid_form(token)
        form["image"] = (io.BytesIO(b"\x89PNG\r\n\x1a\nvalid-test-image"), "notebook.png")
        response = self.client.post("/report-lost", data=form, content_type="multipart/form-data")
        self.assertEqual(response.status_code, 302)
        with self.app.app_context():
            report = self.LostItem.query.one()
            self.assertTrue(report.image_filename)
        image_response = self.client.get(f"/lost-items/uploads/{report.image_filename}")
        try:
            self.assertEqual(image_response.status_code, 200)
            self.assertIn(b"\x89PNG", image_response.data)
        finally:
            image_response.close()

    def test_image_extension_and_contents_must_match(self):
        self._login()
        token = self._csrf_token()
        form = self._valid_form(token)
        form["image"] = (io.BytesIO(b"not an image"), "photo.jpg")
        response = self.client.post("/report-lost", data=form, content_type="multipart/form-data")
        self.assertEqual(response.status_code, 400)
        self.assertIn(b"file contents do not match", response.data)


if __name__ == "__main__":
    unittest.main()