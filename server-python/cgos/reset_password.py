# The MIT License
#
# Copyright (c) 2023 Kensuke Matsuzaki
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.

import sys

import sqlite3
from passlib.context import CryptContext

from app.config import Configs

if __name__ == "__main__":

    cfg = Configs()
    cfg.load(sys.argv[1])

    passctx = CryptContext()
    passctx.load_path(sys.argv[1])

    who = sys.argv[2]
    pw = sys.argv[3]

    db = sqlite3.connect(cfg.database_state_file)

    if cfg.hashPassword:
        pw_store = passctx.hash(pw)
    else:
        pw_store = pw

    cur = db.execute("SELECT pass, rating, K FROM password WHERE name = ?", (who,))
    res = cur.fetchone()

    if res is None:
        print(f"insert user:{who} hash:{pw_store}")
        db.execute(
            """INSERT INTO password VALUES(?, ?, 0, ?, ?, "2000-01-01 00:00")""",
            (
                who,
                pw_store,
                cfg.defaultRating,
                cfg.maxK,
            ),
        )
    else:
        print(f"update user:{who} hash:{pw_store}")
        db.execute(
            "UPDATE password set pass=? WHERE name=?",
            (
                pw_store,
                who,
            ),
        )

    db.commit()
