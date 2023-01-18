# The MIT License
#
# Copyright (c) 2022 Kensuke Matsuzaki
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

import logging
import sqlite3
import sys

from typing import Any, Dict, Optional, List, Tuple

from functools import lru_cache

from pydantic import BaseModel
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

import config

# TODO
sys.path.append("../../server-python/cgos")
from gogame import Game, sgf

# Setup logger
logger = logging.getLogger("cgos_viewer_server")
logger.setLevel(logging.INFO)

logHandler = logging.StreamHandler()
logHandler.setLevel(logging.INFO)
formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logHandler.setFormatter(formatter)
logger.addHandler(logHandler)


games: Dict[int, Game] = dict()  # currently active games


@lru_cache()
def get_settings():
    return config.Settings()


def open_db(cfg: config.Settings) -> sqlite3.Connection:
    try:
        return sqlite3.connect(cfg.database_state_file, timeout=40000)
    except sqlite3.Error as e:
        logger.error(f"Error opening {cfg.database_state_file} datbase.")
        raise Exception(e)


def open_dbrec(cfg: config.Settings) -> sqlite3.Connection:
    try:
        return sqlite3.connect(cfg.game_archive_database, timeout=40000)
    except sqlite3.Error as e:
        logger.error(f"Error opening {cfg.game_archive_database} datbase.")
        raise Exception(e)


def open_cgi(cfg: config.Settings) -> sqlite3.Connection:
    try:
        return sqlite3.connect(cfg.cgi_database, timeout=80000)
    except sqlite3.Error as e:
        logger.error(f"Error opening {cfg.cgi_database} datbase.")
        raise Exception(e)


app = FastAPI()
print("static file", get_settings().htmlDir)
app.mount("/static", StaticFiles(directory=get_settings().htmlDir), name="static")


class Match(BaseModel):

    gid: int
    date: Optional[str]
    time: Optional[str]
    board_size: int
    komi: float
    white: str
    black: str
    result: Optional[str]
    moves: Optional[List[Tuple[str, int, str]]] = None


@app.get("/")
def read_root() -> Any:
    return {"Hello": "World"}


@app.get("/match/{match_id}")
def read_item(match_id: int) -> Any:

    if match_id in games:
        cfg = get_settings()

        game = games[match_id]

        w = f"{game.w}({game.wrate})"
        b = f"{game.b}({game.brate})"

        logger.info(
            f"sending to viewer: game {match_id} - - {cfg.boardsize} {cfg.komi} {w} {b} {cfg.level} ..."
        )

        m = Match(
            gid=match_id,
            # date=dte,
            # time=tme,
            board_size=cfg.boardsize,
            komi=cfg.komi,
            white=w,
            black=b,
            # result=res,
            moves=[(m, int(t), i or "") for (m, t, i) in game.mvs],
        )
        return m
        # msg = f"setup {gid} - - {cfg.boardsize} {cfg.komi} {w} {b} {cfg.level} {joinMoves(game.mvs)}"
    else:
        with open_dbrec(get_settings()) as dbrec:
            rec = dbrec.execute(
                "SELECT dta, analysis FROM games WHERE gid = ?", (match_id,)
            ).fetchone()
            if rec:
                dta = rec[0]
                if rec[1]:
                    analysis = rec[1].splitlines()
                else:
                    analysis = None

                dte, tme, bs, kom, w, b, lev, *lst = dta.split(" ")
                res = lst[-1]
                moves = []
                for i in range(len(lst[:-1]) // 2):
                    a = ""
                    if analysis and i < len(analysis):
                        a = analysis[i]
                    moves.append((lst[i * 2], int(lst[i * 2 + 1]), a))
                m = Match(
                    gid=match_id,
                    date=dte,
                    time=tme,
                    board_size=bs,
                    komi=kom,
                    white=w,
                    black=b,
                    result=res,
                    moves=moves,
                )
                return m
            else:
                return None


@app.get("/matches/")
def read_matches() -> List[Match]:

    cfg = get_settings()

    # send out information about a few previous games
    # -----------------------------------------------
    results: List[Match] = []
    with open_dbrec(get_settings()) as dbrec:
        for (gid, stuff) in dbrec.execute(
            "select gid, dta from games where gid > (select max(gid) from games) - 40 order by gid"
        ):
            dte, tme, bs, kom, w, b, lev, *lst = stuff.split(" ")
            res = lst[-1]
            m = Match(
                gid=gid,
                dte=dte,
                tme=tme,
                board_size=bs,
                komi=kom,
                white=w,
                black=b,
                result=res,
            )
            results.append(m)
            # sock.send(f"match {gid} {dte} {tme} {bs} {kom} {w} {b} {res}")

    # send out information about current games
    # ----------------------------------------
    for (gid, rec) in games.items():
        sw = f"{rec.w}({rec.wrate})"
        sb = f"{rec.b}({rec.brate})"
        logger.info(
            f"sending to viewer: match {gid} - - {cfg.boardsize} {cfg.komi} {sw} {sb}"
        )
        m = Match(
            gid=gid,
            # dte=None,
            # tme=None,
            board_size=cfg.boardsize,
            komi=cfg.komi,
            white=sw,
            black=sb,
            # result=None,
        )
        # sock.send(f"match {gid} - - {cfg.boardsize} {cfg.komi} {sw} {sb} -")

    return results
