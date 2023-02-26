# The MIT License
#
# Copyright (C) 2009 Christian Nentwich and contributors
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

import asyncio
import configparser
import datetime
import sys
import time
import os
import sqlite3
import random
import re
import traceback
import json
from typing import Any, List, Tuple, Dict, Optional

from gogame import GoGame, Game, sgf
from .client import Client
from util.logutils import getLogger


# Setup logger
logger = getLogger("cgos_server")

SKIP = 4
ENCODING = "utf-8"

db: sqlite3.Connection
dbrec: Optional[sqlite3.Connection]
cgi: sqlite3.Connection

gme: Dict[int, GoGame] = dict()

defaultRatingAverage = 0.0

badUsers: List[str] = []
leeway: int
workdir: str


class Configs:
    serverName: str
    boardsize: int
    komi: float
    level: int
    portNumber: int
    timeGift: float
    database_state_file: str
    cgi_database: str
    game_archive_database: Optional[str]
    web_data_file: str
    defaultRating: float
    minK: float
    maxK: float
    htmlDir: str
    sgfDir: str
    provisionalAge: float
    establishedAge: float
    killFile: str
    tools_dir: str
    bin_dir: str
    leeway: int
    anchor_match_rate: float
    badUsersFile: str
    moveIntervalBetweenSave: int

    def load(self, path: str) -> None:
        config = configparser.ConfigParser()
        with open(path) as f:
            try:
                config.read_file(f)
                cfg = config["cgos-server"]
            except Exception as e:
                logger.error("Error reading config file", e, str(e))
                sys.exit(0)

        self.serverName = str(cfg["serverName"])
        self.portNumber = int(cfg["portNumber"])
        self.boardsize = int(cfg["boardsize"])
        self.komi = float(cfg["komi"])
        self.level = int(cfg["level"]) * 1000
        self.timeGift = float(cfg["timeGift"])
        self.database_state_file = str(cfg["database_state_file"])
        self.cgi_database = str(cfg["cgi_database"])
        if "game_archive_database" in cfg:
            self.game_archive_database = str(cfg["game_archive_database"])
        else:
            self.game_archive_database = None
        self.web_data_file = str(cfg["web_data_file"])
        self.defaultRating = float(cfg["defaultRating"])
        self.minK = float(cfg["minK"])
        self.maxK = float(cfg["maxK"])
        self.htmlDir = str(cfg["htmlDir"])
        self.sgfDir = str(cfg["sgfDir"])
        self.provisionalAge = float(cfg["provisionalAge"])
        self.establishedAge = float(cfg["establishedAge"])
        self.killFile = str(cfg["killFile"])
        self.tools_dir = str(cfg["tools_dir"])
        self.bin_dir = str(cfg["bin_dir"])
        self.anchor_match_rate = float(cfg.get("anchor_match_rate", "0.10"))
        self.badUsersFile = str(cfg["bad_users_file"])
        self.moveIntervalBetweenSave = int(cfg["moveIntervalBetweenSave"])


cfg: Configs


def now_string() -> str:
    now = datetime.datetime.now(datetime.timezone.utc)
    return now.strftime("%Y-%m-%d %H:%M:%S")


def now_seconds() -> int:
    return time.time_ns() // 1_000_000_000


def now_milliseconds() -> int:
    return time.time_ns() // 1_000_000


def joinMoves(moves: List[Tuple[str, int, Optional[str]]]) -> str:
    return " ".join([f"{m} {t}" for (m, t, i) in moves])


def joinAnalysis(moves: List[Tuple[str, int, Optional[str]]]) -> str:
    return "\n".join([i or "" for (m, t, i) in moves])


def initDatabase() -> None:
    if not os.path.exists(cfg.cgi_database):
        conn = sqlite3.connect(cfg.cgi_database)

        conn.execute("create table games(gid int, w, wr,  b, br,  dte, res)")
        conn.execute("create index white on games(w)")
        conn.execute("create index black on games(b)")

        conn.commit()
        conn.close()

    if cfg.game_archive_database is not None and not os.path.exists(
        cfg.game_archive_database
    ):
        conn = sqlite3.connect(cfg.game_archive_database)
        conn.execute("create table games(gid int, dta, analysis)")
        conn.commit()
        conn.close()
        # conn.execute("ALTER TABLE games ADD COLUMN analysis")

    if not os.path.exists(cfg.database_state_file):

        conn = sqlite3.connect(cfg.database_state_file)

        conn.execute("create table gameid(gid int)")
        conn.execute(
            "create table password(name, pass, games int, rating, K, last_game, primary key(name) )"
        )
        conn.execute(
            "create table games(gid int, w, wr, b, br, dte, wtu, btu, res, final, primary key(gid))"
        )
        conn.execute("create table anchors(name, rating, primary key(name))")
        conn.execute("create table clients(name, count)")
        conn.execute("INSERT into gameid VALUES(1)")

        conn.commit()
        conn.close()


def openDatabase() -> None:
    global db
    global cgi
    global dbrec

    # set up a long timeout for transactions
    try:
        db = sqlite3.connect(cfg.database_state_file, timeout=40000)
    except sqlite3.Error as e:
        logger.error(f"Error opening {cfg.database_state_file} datbase.")
        raise Exception(e)

    try:
        cgi = sqlite3.connect(cfg.cgi_database, timeout=80000)
    except sqlite3.Error as e:
        logger.error(f"Error opening {cfg.cgi_database} datbase.")
        raise Exception(e)

    if cfg.game_archive_database is not None:
        try:
            dbrec = sqlite3.connect(cfg.game_archive_database, timeout=40000)
        except sqlite3.Error as e:
            logger.error(f"Error opening {cfg.game_archive_database} datbase.")
            raise Exception(e)
    else:
        logger.error("Skip game_archive_database")
        dbrec = None


# -------------------------------------------------
# vact - record of an active viewers
# key is a VID (viewer ID),  val is a socket number
# -------------------------------------------------
# obs - a hash indexed by gid - who is viewing?
# obs( gid ) - a list of viewers of this game
class ViewerList:
    vact: Dict[str, Client] = dict()  # key=vid, val=socket

    # obs( gid ) - a list of viewers of this game
    obs: Dict[int, List[str]] = dict()  # index by vid

    def __init__(self) -> None:
        pass

    def add(self, who: str, client: Client) -> None:
        self.vact[who] = client

    def remove(self, who: str) -> None:
        del self.vact[who]

    def addObserver(self, gid: int, who: str) -> None:
        if gid in self.obs:
            if who not in self.obs[gid]:
                self.obs[gid].append(who)
        else:
            self.obs[gid] = [who]

    def removeObservers(self, gid: int) -> None:
        if gid in self.obs:
            del self.obs[gid]

    def sendAll(self, msg: str) -> None:
        for who, v in list(self.vact.items()):
            v.send(msg)
            if not v.alive:
                logger.error(f"[{who}] disconnected")
                self.remove(who)

    def sendObservers(self, gid: int, msg: str) -> None:
        if gid not in self.obs:
            return
        for vk in self.obs[gid]:
            if vk not in self.vact:
                continue
            self.vact[vk].send(msg)


# -------------------------------------------------------------------------
#  act - internal currently active users.
#        A record exists if a user is logged on.
#        this is an array variable:  act(name) = [ list socket  msg_sent ]
# -------------------------------------------------------------------------
#  key is user_name
#  ---------------------
#  0:  socket
#  1:  msg_state
#  2:  gid          (or zero if none is being played)
#  3:  rating
#  4:  k


class ActiveUser:
    sock: Client
    msg_state: str
    gid: int
    rating: float
    k: float
    useAnalyze: bool

    def __init__(
        self,
        sock: Client,
        msg_state: str,
        gid: int = 0,
        rating: float = 0.0,
        k: float = 0.0,
    ) -> None:
        self.sock = sock
        self.msg_state = msg_state
        self.gid = gid
        self.rating = rating
        self.k = k
        self.useAnalyze = False


# -----------------------------------------------
# games - currently active games and their states
#
# -----------------------------------------------
#  key is gid
#  value is Game


act: Dict[str, ActiveUser] = dict()  # users currently logged on
games: Dict[int, Game] = dict()  # currently active games
ratingOf: Dict[str, str] = dict()  # ratings of any player who logs on
viewers = ViewerList()


# a unique and temporary name for each login until a name is established
# ----------------------------------------------------------------------
sid = 0


# send a message to a player without knowing the socket
# -----------------------------------------------------
def nsend(name: str, msg: str) -> None:
    global act
    if name in act:
        sok = act[name].sock
        sok.send(msg)
    else:
        logger.info(f"alert: Cannot find active record for {name}")


# -------------------------------------------------
# send an informational message out to all clients
# -------------------------------------------------
def infoMsg(msg: str) -> None:
    global act

    for (who, v) in list(act.items()):
        if v.msg_state != "protocol":
            soc = v.sock
            if not soc.send(f"info {msg}"):
                logger.error(f"[{who}] disconnected")
                soc.close()
                del act[who]

    # send message to viewing clients also
    # -------------------------------------
    viewers.sendAll(f"info {msg}")


# routines to rate the games
# --------------------------


def expectation(me: float, you: float) -> float:
    x = (you - me) / 400.0
    d: float = 1.0 + pow(10.0, x)
    return 1.0 / d


def newrating(cur_rating: float, opp_rating: float, res: float, K: float) -> float:
    ex = expectation(cur_rating, opp_rating)
    nr = cur_rating + K * (res - ex)
    return nr


# write an SGF game record
# ---------------------------
def seeRecord(game: Game, res: str, dte: Any, tme: str) -> Tuple[str, str]:

    global cfg

    s = ""

    s += f"{tme} {cfg.boardsize} {cfg.komi} {game.w}({game.white_rate}) {game.b}({game.black_rate}) {cfg.level} {joinMoves(game.moves)} "
    s += res

    a = joinAnalysis(game.moves)

    return s, a


def getAnchors() -> Dict[str, float]:
    global db

    anchors = dict()
    for (nme, rat) in db.execute("SELECT name, rating FROM anchors"):
        anchors[nme] = rat
    return anchors


def batchRate() -> None:

    global act
    global ratingOf
    global db
    global cgi

    anchors = getAnchors()

    tme = now_string()

    batch = db.execute('SELECT gid, w, b, res, dte  FROM games WHERE final == "n"')

    kRange = cfg.maxK - cfg.minK

    for gid, w, b, res, dte in batch:
        wr, wk = db.execute(
            "SELECT rating, K FROM password WHERE name = ?", (w,)
        ).fetchone()
        br, bk = db.execute(
            "SELECT rating, K FROM password WHERE name = ?", (b,)
        ).fetchone()

        if wk < cfg.minK:
            wk = cfg.minK
        if bk < cfg.minK:
            bk = cfg.minK

        # calculate white and black K strength (percentage of total K range)
        # used to calculate effective K for individual games and K reduction
        # ------------------------------------------------------------------
        wks = 1.0 - (wk - cfg.minK) / kRange
        bks = 1.0 - (bk - cfg.minK) / kRange

        weK = wk * bks  # white effective K for this game
        beK = bk * wks  # black effective K for this game

        if res[0] == "W":
            wres = 1.0
        elif res[0] == "B":
            wres = 0.0
        else:
            wres = 0.5
        bres = 1.0 - wres

        nwr = newrating(wr, br, wres, weK)
        nbr = newrating(br, wr, bres, beK)

        # reduce K based on strength of opponents K factor
        # but reduce it less if it's already below 32
        # ------------------------------------------------
        if wk <= 32.0:
            rf = 0.02
        else:
            rf = 0.04
        nwK = wk * (1.0 - rf * bks)

        if bk <= 32.0:
            rf = 0.02
        else:
            rf = 0.04
        nbK = bk * (1.0 - rf * wks)

        # limit K to minimum value
        # ------------------------
        if nbK < cfg.minK:
            nbK = cfg.minK
        if nwK < cfg.minK:
            nwK = cfg.minK

        # make sure anchors retain their ratings
        # --------------------------------------
        if w in anchors:
            nwr = anchors[w]
            nwK = cfg.minK
        if b in anchors:
            nbr = anchors[b]
            nbK = cfg.minK

        # update act record too
        # ---------------------
        if w in act:
            act[w].rating = nwr
            act[w].k = nwK
        if b in act:
            act[b].rating = nbr
            act[b].k = nbK
        ratingOf[w] = strRate(nwr, nwK)
        ratingOf[b] = strRate(nbr, nbK)

        wsrate = strRate(nwr, nwK)
        bsrate = strRate(nbr, nbK)

        with db:
            db.execute(
                "UPDATE password SET rating=?, K=?, last_game=?, games=games+1 WHERE name==?",
                (nwr, nwK, tme, w),
            )
            db.execute(
                "UPDATE password SET rating=?, K=?, last_game=?, games=games+1 WHERE name==?",
                (nbr, nbK, tme, b),
            )
            db.execute("""UPDATE games SET final="y" WHERE gid=?""", (gid,))

        cgi.execute(
            "INSERT INTO games VALUES(?, ?, ?, ?, ?, ?, ?)",
            (gid, w, wsrate, b, bsrate, dte, res),
        )

    db.commit()
    cgi.commit()


RE_PASSWORD = re.compile(r"[^\d\w\.-]")


def test_password(password: str) -> str:

    if password.isascii():
        # e  = "[^\d\w\.-]"
        if re.search(RE_PASSWORD, password):
            return "Password must only alphanumeric, underscore, hyphen, period or digits characters."
    else:
        return "Password must consist of only ascii characters."

    if len(password) < 3:
        return "Password must be at least 3 characters."

    if len(password) > 16:
        return "Password limited to 16 characters."

    return ""


RE_NAME = re.compile(r"[^\d\w\.-]")


def valid_name(user_name: str) -> str:

    if user_name.isascii():
        # e = "[^\d\w\.-]"
        if re.search(RE_NAME, user_name):
            return "User name must only alphanumeric, underscore, hyphen, period or digits characters."
    else:
        return "User name must consist of only ascii characters."

    if len(user_name) < 3:
        return "User name must be 3 characters or more."

    if len(user_name) > 18:
        return "User name must be no more than 18 characters long."

    # user "1024" crashed original CGOS.
    if user_name[0].isdigit():
        return "User name must start alphabet. Consisting of only numbers is invalid."

    if user_name in badUsers:
        return "Not removing dead stones, many timeout, changed strength, or many similar programs. Change setting and try another name."

    return ""


# produce a printable rating given rating and K
# ---------------------------------------------
def strRate(elo: float, k: float) -> str:

    r = "%0.0f" % elo

    if elo < 0.0:
        r = "0"
    if k > 16.0:
        r += "?"

    return r


# produce a printable rating from active record
# ---------------------------------------------
def rating(who: str) -> str:

    u = act[who]

    return strRate(u.rating, u.k)


def saveSgf(gid: int, game: Game, sc: str, err: str) -> None:

    dte = game.ctime.strftime("%Y-%m-%d")

    sgfString = sgf(
        game=game,
        serverName=cfg.serverName,
        level=cfg.level,
        boardsize=cfg.boardsize,
        komi=cfg.komi,
        gid=gid,
        res=sc,
        dte=dte,
        err=err,
    )

    dest_dir = os.path.join(
        cfg.htmlDir,
        cfg.sgfDir,
        game.ctime.strftime("%Y"),
        game.ctime.strftime("%m"),
        game.ctime.strftime("%d"),
    )
    os.makedirs(dest_dir, exist_ok=True)  # make directory if it doesn't exist

    with open(f"{dest_dir}/{gid}.sgf", "w") as f:
        f.write(sgfString)


def gameover(gid: int, sc: str, err: str) -> None:
    global games
    global act
    global db
    global dbrec

    del gme[gid]  # free memory of the game object

    game = games[gid]
    logger.info(f"gameover: {gid} {game.w} {game.b} {sc} {err}")

    dte = game.ctime.strftime("%Y-%m-%d")
    tme = game.ctime.strftime("%Y-%m-%d %H:%M")

    if game.w in act:
        nsend(game.w, f"gameover {dte} {sc} {err}")
        act[game.w].msg_state = "gameover"

    if game.b in act:
        nsend(game.b, f"gameover {dte} {sc} {err}")
        act[game.b].msg_state = "gameover"

    wtu = cfg.level - game.white_remaining_time
    btu = cfg.level - game.black_remaining_time

    # send gameover announcements to viewing clients
    # ----------------------------------------------
    viewers.sendAll(f"gameover {gid} {sc} {wtu} {btu}")

    viewers.sendObservers(gid, f"update {gid} {sc}")
    viewers.removeObservers(gid)

    see, see2 = seeRecord(games[gid], sc, dte, tme)

    if dbrec:
        dbrec.execute("INSERT INTO games VALUES(?, ?, ?)", (gid, see, see2))
        dbrec.commit()

    db.execute(
        """INSERT INTO games VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, "n" )""",
        (gid, game.w, game.white_rate, game.b, game.black_rate, tme, wtu, btu, sc),
    )
    db.commit()

    saveSgf(gid, games[gid], sc, err)

    # we can kill the active game record now.
    # ----------------------------------------
    del games[gid]


def viewer_respond(sock: Client, data: str) -> None:

    global games
    global dbrec

    who = sock.id

    # If we can no longer read from sock, close it.
    # ---------------------------------------------
    if len(data) == 0:
        sock.close()
        logger.error(f"[{who}] disconnected")
        viewers.remove(who)
        return

    if data == "quit":
        sock.close()
        logger.info(f"viewer {who} quits")
        viewers.remove(who)
        return

    req, param = data.split(maxsplit=1)

    if req == "observe":
        gid = int(param)

        if gid in games:

            game = games[gid]

            w = f"{game.w}({game.white_rate})"
            b = f"{game.b}({game.black_rate})"

            logger.info(
                f"sending to viewer: game {gid} - - {cfg.boardsize} {cfg.komi} {w} {b} {cfg.level} ..."
            )

            msg = f"setup {gid} - - {cfg.boardsize} {cfg.komi} {w} {b} {cfg.level} {joinMoves(game.moves)}"
            sock.send(msg)

            viewers.addObserver(gid, who)
        else:
            if dbrec:
                rec = dbrec.execute(
                    "SELECT dta FROM games WHERE gid = ?", (gid,)
                ).fetchone()
                if rec:
                    dta = rec[0]
                    sock.send(f"setup {gid} {dta}")
                else:
                    sock.send(f"setup {gid} ?")
            else:
                sock.send(f"setup {gid} ?")


def player_respond(sock: Client, data: str) -> None:
    global act

    who = sock.id
    user = act[who]

    # If we can no longer read from sock, close it.
    # ---------------------------------------------
    if len(data) == 0:
        logger.error(f"[{who}] disconnected")

        sock.close()
        del act[who]
        return

    if data == "quit":
        return _handle_player_quit(sock, data)

    logger.debug(f"handle '{user.msg_state}' '{data}'")

    if user.msg_state == "protocol":
        return _handle_player_protocol(sock, data)
    if user.msg_state == "username":
        return _handle_player_username(sock, data)
    if user.msg_state == "password":
        return _handle_player_password(sock, data)
    if user.msg_state == "gameover":
        return _handle_player_gameover(sock, data)
    if user.msg_state == "genmove":
        return _handle_player_genmove(sock, data)
    if user.msg_state == "ok":
        logger.info(f"[{who}] made illegal respose in ok mode")


def _handle_player_quit(sock: Client, data: str) -> None:
    who = sock.id

    sock.close()
    logger.info(f"user {who} quits")
    del act[who]
    return


def _handle_player_protocol(sock: Client, data: str) -> None:
    global db
    global dbrec

    who = sock.id

    msg = data.strip()

    if msg[0:2] == "v1":
        del act[who]
        viewers.add(who, sock)

        # close down current handler, open a new handler
        # ----------------------------------------------

        logger.info(f"client: {data}")
        cc = db.execute("select count from clients where name = ?", (data,)).fetchone()
        # if  [string is integer -strict $cc]:
        if cc is not None:
            db.execute("update clients set count=count+1 where name = ?", (data,))
        else:
            db.execute("insert into clients values(?, 1)", (data,))
        db.commit()

        logger.info(f"[{who}] logged on as viewer")

        gid: int

        # send out information about a few previous games
        # -----------------------------------------------
        matchList: List[str] = []
        if dbrec:
            for (gid, stuff) in dbrec.execute(
                "select gid, dta from games where gid > (select max(gid) from games) - 40 order by gid"
            ):
                dte, tme, bs, kom, w, b, lev, *lst = stuff.split(" ")
                res = lst[-1]
                matchList.append(f"match {gid} {dte} {tme} {bs} {kom} {w} {b} {res}")

        # send out information about current games
        # ----------------------------------------
        for (gid, rec) in games.items():
            sw = f"{rec.w}({rec.white_rate})"
            sb = f"{rec.b}({rec.black_rate})"
            logger.info(
                f"sending to viewer: match {gid} - - {cfg.boardsize} {cfg.komi} {sw} {sb}"
            )
            matchList.append(f"match {gid} - - {cfg.boardsize} {cfg.komi} {sw} {sb} -")

        sock.send(*matchList)

        return

    if msg[0:2] == "e1":
        parameters = msg.split()
        logger.info(f"client: {data}")
        cc = db.execute("select count from clients where name = ?", (data,)).fetchone()
        # if  [string is integer -strict $cc] :
        if cc is not None:
            db.execute("update clients set count=count+1 where name = ?", (data,))
        else:
            db.execute("insert into clients values(?, 1)", (data,))
        db.commit()
        act[who].useAnalyze = "genmove_analyze" in parameters
        act[who].msg_state = "username"
        sock.send("username")
        return

    sock.send("Error: invalid response")
    del act[who]
    sock.close()
    return


def _handle_player_username(sock: Client, data: str) -> None:
    who = sock.id

    data = data.strip()
    err = valid_name(data)  # returns "" or an error message

    if err == "":
        user_name = data
    else:
        sock.send(f"Error: {err}")
        del act[who]
        sock.close()
        return

    sock.user_name = user_name

    act[who].msg_state = "password"
    sock.send("password")
    return


def _handle_player_password(sock: Client, data: str) -> None:
    global db

    uid = sock.id
    who = sock.user_name

    if who is None:
        sock.send("Error: no user_name")
        sock.close()
        del act[uid]
        return

    pw = data.strip()
    # loginTime = now_seconds()

    err = test_password(pw)

    if err != "":
        sock.send(f"Error: {err}")
        sock.close()
        del act[uid]
        return

    cur = db.execute("SELECT pass, rating, K FROM password WHERE name = ?", (who,))
    res = cur.fetchone()

    if res is None:
        logger.info(f"[{who}] new user")
        db.execute(
            """INSERT INTO password VALUES(?, ?, 0, ?, ?, "2000-01-01 00:00")""",
            (
                who,
                pw,
                defaultRatingAverage,
                cfg.maxK,
            ),
        )
        db.commit()
        cmp_pw = pw
        rat = defaultRatingAverage
        k = cfg.maxK
        ratingOf[who] = strRate(rat, k)
    else:
        cmp_pw, rat, k = res
        ratingOf[who] = strRate(rat, k)

    if cmp_pw != pw:
        sock.send("Sorry, password doesn't match")
        sock.close()
        del act[uid]
        return

    # Handle user who already logged on
    if who in act:
        # cleanup old connection
        xsoc = act[who].sock
        xsoc.send("info another login is being attempted using this user name")
        xsoc.close()
        logger.error(f"Error: user {who} apparently lost old connection")
        del act[who]

    sock.id = who
    client = act[uid]
    del act[uid]

    act[who] = ActiveUser(sock, msg_state="waiting", gid=0, rating=rat, k=k)
    act[who].useAnalyze = client.useAnalyze
    logger.info(f"[{who}] logged on analyze: {act[who].useAnalyze}")

    logger.info(f"is {who} currently playing a game?")

    # determine if there are any games pending
    # ----------------------------------------
    for (gid, inf) in games.items():

        logger.info(f"testing {gid} {inf.w} {inf.b}")

        # is this player involved in a game?
        # ----------------------------------
        if inf.w == who or inf.b == who:
            logger.info("YES!")
            wr = ratingOf[inf.w]
            br = ratingOf[inf.b]

            msg_out = f"setup {gid} {cfg.boardsize} {cfg.komi} {cfg.level} {inf.w}({wr}) {inf.b}({br}) {joinMoves(inf.moves)}"
            logger.info(msg_out)

            # determine who's turn to play
            # ----------------------------
            ply = len(inf.moves)
            if ply & 1:
                ctm = inf.w
            else:
                ctm = inf.b

            # catch up the game
            # ------------------
            sock.send(msg_out)

            act[who].msg_state = "ok"
            act[who].gid = gid

            # determine if we need to send out a genmove command
            # --------------------------------------------------
            if ctm == who:
                if ply & 1:
                    # tr = inf.wrt
                    ct = now_milliseconds()
                    tl = inf.white_remaining_time - (ct - inf.last_move_start_time)
                    sock.send(f"genmove w {tl}")
                    act[who].msg_state = "genmove"
                    return
                else:
                    # tr = inf.black_remaining_time
                    ct = now_milliseconds()
                    tl = inf.black_remaining_time - (ct - inf.last_move_start_time)
                    sock.send(f"genmove b {tl}")
                    act[who].msg_state = "genmove"
                    return


def _handle_player_gameover(sock: Client, data: str) -> None:
    who = sock.id

    msg = data.strip()
    # log "msg recieved from $who is $msg"

    if msg == "ready":
        act[who].msg_state = "waiting"
        act[who].gid = 0
        return
    else:
        act[who].msg_state = "gameover"

    logger.info(f"[{who}] gave improper response to gameover: {msg}")


def _handle_player_genmove(sock: Client, data: str) -> None:
    who = sock.id

    ct = now_milliseconds()
    act[who].msg_state = "ok"  # passive state - not expecting a response

    # does game still exist?
    # ----------------------
    gid = act[who].gid

    # put program in wait state if it has already completed
    # -----------------------------------------------------
    if gid not in games:
        act[who].msg_state = "waiting"
        return

    ctm = gme[gid].colorToMove()  # who's turn to move?
    maybe = ["W+", "B+"][ctm & 1]  # opponent wins if there is an error

    mv = data.strip()
    analysis = None
    if act[who].useAnalyze:
        # parse and validate analyze info
        tokens = mv.split(None, 1)
        mv = tokens[0]
        if len(tokens) > 1:
            #    analysis = re.sub("[^- 0-9a-zA-Z._-]", "", tokens[1])
            try:
                info = json.loads(tokens[1])
                analysis = json.dumps(info, indent=None, separators=(",", ":"))
            except:
                logger.info(f"Bad analysis from {who}, '{tokens[1]}'")
    over = ""

    game = games[gid]
    wrt = game.white_remaining_time
    brt = game.black_remaining_time

    # make time calc, determine if game over for any reason
    # -----------------------------------------------------

    tt = ct - game.last_move_start_time - leeway  # fudge an extra moment

    if tt < 0:
        tt = 0

    if ctm & 1:
        wrt = wrt - tt
        games[gid].white_remaining_time = wrt
        if wrt < 0:
            over = "B+Time"
            gameover(gid, over, "")
            return
    else:
        brt = brt - tt
        games[gid].black_remaining_time = brt
        if brt < 0:
            over = "W+Time"
            gameover(gid, over, "")
            return

    if mv.lower() == "resign":
        err = 0
        over = maybe
        over += "Resign"
        if game.w == who:
            #  nsend $b "play w $mv $wrt"
            vmsg = f"{mv} {wrt}"
        else:
            # nsend $w "play b $mv $brt"
            vmsg = f"{mv} {brt}"
        viewers.sendObservers(gid, f"update {gid} {vmsg}")
        gameover(gid, over, "")
        return
    else:
        err = gme[gid].make(mv)

    if err < 0:
        xerr = err * -1
        # Return: -4  if str_move formatted wrong
        # Return: -3  move to occupied square
        # Return: -2  Position Super Ko move
        # Return: -1  suicide
        err_msg = [
            "huh",
            "suicide attempted",
            "KO attempted",
            "move to occupied point",
            "do not understand syntax",
        ]
        over = maybe
        over += "Illegal"
        gameover(gid, over, err_msg[xerr])
        return

    # record the moves and times
    # --------------------------
    if ctm & 1:
        game.moves.append((mv, wrt, analysis))
    else:
        game.moves.append((mv, brt, analysis))
    games[gid].moves = game.moves

    if game.w == who:
        nsend(game.b, f"play w {mv} {wrt}")
        vmsg = f"{mv} {wrt}"
    else:
        nsend(game.w, f"play b {mv} {brt}")
        vmsg = f"{mv} {brt}"

    viewers.sendObservers(gid, f"update {gid} {vmsg}")

    if (
        cfg.moveIntervalBetweenSave > 0
        and len(game.moves) % cfg.moveIntervalBetweenSave == 0
    ):
        saveSgf(gid, games[gid], "?", "")

    # game over due to natural causes?
    # --------------------------------
    if gme[gid].twopass():
        sc: float = gme[gid].ttScore()
        sc = sc - cfg.komi
        if sc < 0.0:
            sc = -sc
            over = f"W+{sc}"
            gameover(gid, over, "")
            return
        elif sc > 0.0:
            over = f"B+{sc}"
            gameover(gid, over, "")
            return
        else:
            over = "Draw"
            gameover(gid, over, "")
            return

    # game still in progress, start clock and send genmove
    # -----------------------------------------------------
    if game.w == who:
        if game.b in act:
            act[game.b].msg_state = "genmove"
            nsend(game.b, f"genmove b {brt}")
        games[gid].last_move_start_time = now_milliseconds()
    else:
        if game.w in act:
            act[game.w].msg_state = "genmove"
            nsend(game.w, f"genmove w {wrt}")
        games[gid].last_move_start_time = now_milliseconds()


async def accept_connection(
    reader: asyncio.StreamReader, writer: asyncio.StreamWriter
) -> None:

    address = writer.get_extra_info("peername")

    logger.info(f"Connection from {address}")

    # def accept_connection(sock: socket.socket) -> Client:
    global act
    global sid

    # create a default id till we get user name
    # -----------------------------------------
    who = str(sid)
    sid += 1

    client = Client(reader, writer, who)

    act[who] = ActiveUser(client, "protocol", 0, cfg.defaultRating, cfg.maxK)

    readTask = asyncio.create_task(client.readTask())
    writeTask = asyncio.create_task(client.writeTask())
    handleTask = asyncio.create_task(handle_client(client))

    tasks = [readTask, writeTask, handleTask]
    done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)

    logger.debug(f"client ended: {who} cleanup done:{len(done)} pending:{len(pending)}")
    for t in pending:
        try:
            t.cancel()
        except:
            pass

    logger.info(f"disconnected: {who}")


async def handle_client(client: Client) -> None:

    who = client.id

    client.send("protocol genmove_analyze")

    try:
        while client.alive:
            line = await client.readLine()

            logger.debug(f"got new line: {who}/{client.id} {line}")

            if who in viewers.vact:
                logger.debug(f"handle viewer {who}: {line}")
                viewer_respond(client, line)
            else:
                logger.debug(f"handle player {who}: {line}")
                player_respond(client, line)
    except asyncio.CancelledError:
        logger.debug(f"cancelled: {who}")
    except:
        logger.error(f"Unexpected Error: {who}")
        logger.error(traceback.format_exc())
        logger.error(traceback.format_stack())

    if client.id in act and act[client.id].sock is client:
        del act[client.id]


# --------------------------------------------------------
#  Estimate how much time left in current round in seconds
#
#  We will do it the "hard" way because of the forgiveness
#  factor given to each move can create inaccuracies.  The
#  easy way is to to take  round_start_time - (level * 2)
# ---------------------------------------------------------
def estimateRoundTimeLeft() -> int:
    global games

    wctl = 0  # worst case time left
    mtme = now_milliseconds()

    for v in games.values():
        tr = (
            v.white_remaining_time
            + v.black_remaining_time
            - (mtme - v.last_move_start_time)
        )
        if tr > wctl:
            wctl = tr

    return wctl // 1000


#  -----------------------------------------------------------
#  schedule_game
#
#  1. Determine if any games are complete due to time forfeit
#  2. complete and record those games
#  3. If NO games are left, schedule a new round
#  4. set up event loop for next cycle
#  -----------------------------------------------------------

last_game_count = -1


def schedule_games() -> None:

    global SKIP
    global act
    global games
    global last_game_count
    global workdir
    global leeway
    global last_est
    global gme
    global db
    global cgi
    global dbrec

    RANGE = 500.0  # minmum elo range allowed

    # determine if all games are complete
    # -----------------------------------
    ct = now_milliseconds()

    count = 0  # number of active games

    for gid in list(games.keys()):
        rec = games[gid]

        ctm = gme[gid].colorToMove()

        if ctm & 1:
            tr = rec.white_remaining_time
            tu = ct - rec.last_move_start_time - leeway
            if tu < 0:
                tu = 0
            time_left = tr - tu
            if time_left < 0:
                games[gid].white_remaining_time = time_left
                gameover(gid, "B+Time", "")
        else:
            tr = rec.black_remaining_time
            tu = ct - rec.last_move_start_time - leeway
            if tu < 0:
                tu = 0
            time_left = tr - tu
            if time_left < 0:
                games[gid].black_remaining_time = time_left
                gameover(gid, "W+Time", "")

        count += 1

    if count != last_game_count:
        logger.info(f"Games in progress: {count}")
        last_game_count = count

    # send progress message
    # ---------------------
    if True:
        est = estimateRoundTimeLeft()
        estMin = est // 60
        estSec = est % 60

        curTime = now_seconds()
        if curTime - last_est > 60:
            if est > 2:
                infoMsg("Maximum time until next round: %02d:%02d" % (estMin, estSec))
            last_est = curTime

    # should we begin another round of scheduling?
    # --------------------------------------------
    if count == 0:

        logger.info("Batch rating")
        batchRate()

        tmpf = os.path.join(workdir, "dta.cgos.tmp")
        with open(tmpf, "w") as wd:
            # ctme = now_seconds()

            ctme = datetime.datetime.now(datetime.timezone.utc)
            wd.write(ctme.strftime("%Y-%m-%d %H:%M:%S") + "\n")

            # prepare lookup of all players who have played within last 6 months
            # ------------------------------------------------------------------
            atme = ctme - datetime.timedelta(seconds=86400 * 190)
            lutme = atme.strftime("%Y-%m-%d %H:%M:%S")
            for (nme, gms, rat, k, lg) in db.execute(
                "SELECT name, games, rating, K, last_game FROM password WHERE last_game >= ?",
                (lutme,),
            ):
                wd.write(f"u {nme} {gms} {strRate(rat, k)} {lg}\n")

            # recently completed games
            # ------------------------
            atme = ctme - datetime.timedelta(
                seconds=3600 * 4
            )  # get 4 hours worth of games
            lutme = atme.strftime("%Y-%m-%d %H:%M:%S")
            for (gid, w, wr, b, br, dte, wtu, btu, res,) in db.execute(
                "SELECT gid, w, wr, b, br, dte, wtu, btu, res FROM games WHERE dte >= ?",
                (lutme,),
            ):
                wd.write(f"g {gid} {w} {wr} {b} {br} {dte} {wtu} {btu} {res}\n")

            if os.path.exists(cfg.killFile):
                wd.close()
                os.rename(tmpf, cfg.web_data_file)

                db.commit()
                cgi.commit()

                db.close()
                cgi.close()

                if dbrec:
                    dbrec.commit()
                    dbrec.close()

                logger.info("KILL FILE FOUND - EXIT CGOS")
                sys.exit(0)

            # load bad users file
            global badUsers

            badUsers = []
            if os.path.exists(cfg.badUsersFile):
                with open(cfg.badUsersFile, "r") as f:
                    badUsers = f.read().splitlines()
                logger.info(f"sizeof bad_users: {len(badUsers)}")
            else:
                logger.info("bad_users_file is not found.")

            for (name, v) in list(act.items()):
                if v.msg_state == "waiting":
                    if name in badUsers:
                        logger.info(f"found bad user {name}. kick.")
                        del act[name]
                        v.sock.close()

            # dynamically computer ELO RANGE
            # ------------------------------
            lst: List[Tuple[str, float]] = []
            r_sum = 0.0

            for (name, v) in act.items():
                # sock, state, gid, rating = v

                if v.msg_state == "waiting":
                    r = v.rating
                    lst.append((name, r))
                    r_sum += r

            lst.sort(key=lambda e: -e[1])
            max_interval = 0.0

            ll = len(lst)
            e = ll - SKIP

            global defaultRatingAverage
            if ll > 0:
                defaultRatingAverage = r_sum / ll
                logger.info(
                    f"defaultRatingAverage: {defaultRatingAverage}  : playes {ll}"
                )
            else:
                defaultRatingAverage = cfg.defaultRating

            for i in range(e):
                cr = lst[i][1]
                nr = lst[i + SKIP][1]

                diff = cr - nr

                if diff > max_interval:
                    max_interval = diff

            # cover the case where there are very few players
            # -----------------------------------------------
            if e <= 0:
                max_interval = 2000.0

            logger.info(f"maximum skip elo: {max_interval}")
            max_interval = max_interval * 1.50

            if max_interval > RANGE:
                RANGE = max_interval

            logger.info(f"ELO permutation factor to be used: {RANGE}")

            # now permute the players up to RANGE amount
            # ------------------------------------------
            lst = []

            for (name, v) in act.items():
                # sock, state, gid, rating = v

                if v.msg_state == "waiting":
                    r = v.rating + RANGE * random.random()
                    lst.append((name, r))

            lst.sort(key=lambda e: -e[1])

            if len(lst) > 1:

                logger.info(f"will schedule: {len(lst)} players")

                anchors = getAnchors()

                lst_pairs = iter(lst)
                for (aa, bb) in zip(lst_pairs, lst_pairs):

                    if bb is None:
                        continue

                    # set up white and black players
                    # ------------------------------
                    wp = aa[0]  # actual player names
                    bp = bb[0]  # actual player names

                    # delte anchor vs anchor
                    if aa in anchors and bb in anchors:
                        r = random.random()
                        if r > cfg.anchor_match_rate:
                            logger.info(f"delete this match. {wp}, {bp}, r={r}")
                            continue

                    wco = db.execute(
                        "SELECT count(*) FROM games WHERE w==? AND b==?", (wp, bp)
                    ).fetchone()[0]
                    bco = db.execute(
                        "SELECT count(*) FROM games WHERE w==? AND b==?", (bp, wp)
                    ).fetchone()[0]

                    # swap white and black if black has not been played as many times
                    if bco < wco:
                        bp, wp = wp, bp

                    gid = db.execute(
                        "SELECT gid FROM gameid WHERE ROWID=1"
                    ).fetchone()[0]
                    db.execute("UPDATE gameid set gid=gid+1 WHERE ROWID=1")
                    gme[gid] = GoGame(cfg.boardsize)

                    wr = act[wp].rating
                    wk = act[wp].k
                    br = act[bp].rating
                    bk = act[bp].k
                    wr = strRate(wr, wk)
                    br = strRate(br, bk)

                    games[gid] = Game(
                        wp, bp, 0, cfg.level, cfg.level, wr, br, [], ctme
                    )
                    act[wp].gid = gid
                    act[bp].gid = gid
                    msg_out = f"setup {gid} {cfg.boardsize} {cfg.komi} {cfg.level} {wp}({wr}) {bp}({br})"
                    nsend(wp, msg_out)
                    nsend(bp, msg_out)

                    vmsg = f"match {gid} - - {cfg.boardsize} {cfg.komi} {wp}({wr}) {bp}({br}) -"
                    viewers.sendAll(vmsg)

                    logger.info(f"starting {wp} {wr} {bp} {br}")

                db.commit()

                # add a 3 second delay to let all programs complete setup.
                # ------------------------------------------------------

                time.sleep(3000 / 1000)

                view_count = len(viewers.vact)
                logger.info(f"Active viewers: {view_count}")

                # gentlemen, start your clocks!
                # -------------------------------------
                tmeSch = now_string()
                # [clock format [clock seconds] -format "%Y-%m-%d %H:%M:%S" -timezone :UTC]
                for (gid, rec) in games.items():
                    # wp, bp = rec
                    logger.info(
                        f"match-> {rec.w}({ rating(rec.w) })   {rec.b}({ rating(rec.b) })"
                    )
                    nsend(rec.b, f"genmove b {cfg.level}")  # the game's afoot
                    ct = now_milliseconds()
                    games[gid].last_move_start_time = ct
                    act[rec.b].msg_state = "genmove"
                    act[rec.w].msg_state = "ok"
                    # "s" dte tme gid w b x wtl btl wr br
                    wd.write(
                        f"s {tmeSch} {gid} {rec.w} {rec.b} {rec.last_move_start_time} {rec.white_remaining_time} {rec.black_remaining_time} {rec.white_rate} {rec.black_rate}\n"
                    )

        os.rename(tmpf, cfg.web_data_file)


async def schedule_games_task() -> None:

    # after 45000ms schedule_games
    await asyncio.sleep(45.0)

    while True:
        try:
            schedule_games()
        except Exception as e:
            logger.error(f"Error while scheduling game {str(e)}")
            logger.error(traceback.format_exc())

        # every 15 seconds
        await asyncio.sleep(15.0)


last_est = now_seconds()


async def server_main() -> None:
    server = await asyncio.start_server(accept_connection, "", cfg.portNumber)

    addrs = ", ".join(str(sock.getsockname()) for sock in server.sockets)
    logger.info(f"Serving on {addrs}")

    # Create a game scheduling event
    # ------------------------------
    task = asyncio.create_task(schedule_games_task())

    async with server:
        await server.serve_forever()

    task.cancel()


def runServer() -> None:
    global cfg
    global leeway
    global workdir
    global defaultRatingAverage

    # READ the configuration file
    # ---------------------------
    if len(sys.argv) < 2:
        print("Must specify a configuration file.")
        sys.exit(1)
    else:
        cfg = Configs()
        cfg.load(sys.argv[1])
        leeway = int(cfg.timeGift * 1000.0)

        defaultRatingAverage = cfg.defaultRating

        tme = now_string()

        logger.info(f'"{cfg.serverName}" up and running at {tme} GMT')

    # remove any existing kill file
    # -----------------------------
    if os.path.exists(cfg.killFile):
        os.remove(cfg.killFile)

    workdir = os.path.dirname(cfg.web_data_file)
    logger.info(f"datafile:'{cfg.web_data_file}' -> workdir:'{workdir}'")

    # make GameDir directory if it doesn't exist
    # -------------------------------------------
    try:
        os.makedirs(cfg.sgfDir, exist_ok=True)
    except:
        logger.error(f"error making sgfDir: {cfg.sgfDir}")
        sys.exit(1)

    initDatabase()
    openDatabase()

    asyncio.run(server_main())
