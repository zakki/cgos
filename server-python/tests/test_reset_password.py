import io
import sqlite3
from contextlib import redirect_stdout
from types import SimpleNamespace
from unittest import TestCase

from passlib.context import CryptContext
from reset_password import reset_password


class TestResetPassword(TestCase):
    def setUp(self):
        self.db = sqlite3.connect(":memory:")
        self.db.execute(
            """
            CREATE TABLE password (
                name TEXT,
                pass TEXT,
                games INTEGER,
                rating REAL,
                K REAL,
                created TEXT
            )
            """
        )
        self.cfg = SimpleNamespace(
            hashPassword=False,
            defaultRating=1800.0,
            maxK=200.0,
        )

    def tearDown(self):
        self.db.close()

    def test_reset_does_not_print_password_or_hash(self):
        output = io.StringIO()
        with redirect_stdout(output):
            reset_password(self.cfg, CryptContext(), self.db, "bot", "secret")
            reset_password(self.cfg, CryptContext(), self.db, "bot", "updated-secret")

        self.assertEqual(output.getvalue(), "")
        self.assertEqual(
            self.db.execute("SELECT pass FROM password WHERE name = 'bot'").fetchone()[
                0
            ],
            "updated-secret",
        )
