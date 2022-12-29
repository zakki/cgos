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

import traceback
import configparser
import datetime
import sys
import time
import os
import sqlite3
import socket
import random
import re
import select
import logging
from typing import Any, List, Tuple

from ..gogame import GoGame, Game, sgf


# Setup logger
logger = logging.getLogger("cgos_server")
logger.setLevel(logging.INFO)
logHandler = logging.StreamHandler()
logHandler.setLevel(logging.INFO)
formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logHandler.setFormatter(formatter)
logger.addHandler(logHandler)


SKIP = 4
ENCODING = "utf-8"

db: sqlite3.Connection
dbrec: sqlite3.Connection
cgi: sqlite3.Connection

gme: dict[int, GoGame] = dict()


class Configs:
    serverName: str
    boardsize: int
    komi: float
    level: int
    portNumber: int
    timeGift: float
    database_state_file: str
    cgi_database: str
    game_archive_database: str
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
        self.game_archive_database = str(cfg["game_archive_database"])
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


def now_string() -> str:
    now = datetime.datetime.now(datetime.timezone.utc)
    return now.strftime("%Y-%m-%d %H:%M:%S")


def now_seconds() -> int:
    return time.time_ns() // 1_000_000_000


def now_milliseconds() -> int:
    return time.time_ns() // 1_000_000


def joinMoves(mvs: List[Tuple[str, int]]) -> str:
    return " ".join([f"{m} {t}" for (m, t) in mvs])


# READ the configuration file
# ---------------------------
if len(sys.argv) < 2:
    print("Must specify a configuration file.")
    sys.exit(1)
else:
    cfg = Configs()
    cfg.load(sys.argv[1])
    leeway = int(cfg.timeGift * 1000.0)

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


def initDatabase() -> None:
    if not os.path.exists(cfg.cgi_database):
        conn = sqlite3.connect(cfg.cgi_database)

        conn.execute("create table games(gid int, w, wr,  b, br,  dte, res)")
        conn.execute("create index white on games(w)")
        conn.execute("create index black on games(b)")

        conn.close()

    if not os.path.exists(cfg.game_archive_database):
        conn = sqlite3.connect(cfg.game_archive_database)
        conn.execute("create table games(gid int, dta)")
        conn.close()

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

    try:
        dbrec = sqlite3.connect(cfg.game_archive_database, timeout=40000)
    except sqlite3.Error as e:
        logger.error(f"Error opening {cfg.game_archive_database} datbase.")
        raise Exception(e)


class Socket:
    def __init__(self, s: socket.socket) -> None:
        self._socket = s
        self._socketfile = self._socket.makefile("rw", encoding=ENCODING)
        self.fileno = s.fileno()

    def write(self, message: str) -> None:
        logger.debug(f"S -> {id.get(self, '<unknown>')}: '{message}'")
        self._socketfile.write(message + "\n")
        self._socketfile.flush()

    def read(self) -> str:
        line = self._socketfile.readline()
        logger.debug(f"S <- {id.get(self, '<unknown>')}: '{line}'")
        line = line.strip()
        return line

    def close(self) -> None:
        try:
            self._socketfile.close()
            self._socket.close()
        except Exception as e:
            logger.error(str(e))


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
    sock: Socket
    msg_state: str
    gid: int
    rating: float
    k: float

    def __init__(
        self,
        sock: Socket,
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


# -----------------------------------------------
# games - currently active games and their states
#
# -----------------------------------------------
#  key is gid
#  value is Game


# -------------------------------------------------
# vact - record of an active viewers
# key is a VID (viewer ID),  val is a socket number
# -------------------------------------------------
# obs - a hash indexed by gid - who is viewing?
# obs( gid ) - a list of viewers of this game

act: dict[str, ActiveUser] = dict()  # users currently logged on
games: dict[int, Game] = dict()  # currently active games
id: dict[Socket, str] = dict()  # map sockets to user names
ratingOf: dict[str, str] = dict()  # ratings of any player who logs on
obs: dict[int, List[str]] = dict()  # index by vid
vact: dict[str, Socket] = dict()  # key=vid, val=socket
sockets: dict[int, Socket] = dict()  # map raw socket to socket


# a unique and temporary name for each login until a name is established
# ----------------------------------------------------------------------
sid = 0


def send(sock: Socket, msg: str) -> None:
    try:
        sock.write(msg)
    except:
        who = id.get(sock, "<unknown>")
        logger.error(f"alert: Socket crash for user: {who}")
        logger.error(traceback.format_exc())
        logger.error(traceback.format_stack())


# send a message to a player without knowing the socket
# -----------------------------------------------------
def nsend(name: str, msg: str) -> None:
    global act
    if name in act:
        sok = act[name].sock
        sok.write(msg)
    else:
        logger.info(f"alert: Cannot find active record for {name}")


# -------------------------------------------------
# send an informational message out to all clients
# -------------------------------------------------
def infoMsg(msg: str) -> None:
    global act
    global vact

    for v in act.values():
        if v.msg_state != "protocol":
            soc = v.sock
            send(soc, f"info {msg}")

    # send message to viewing clients also
    # -------------------------------------
    for v2 in vact.values():
        send(v2, f"info {msg}")


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
def seeRecord(gid: int, res: str, dte: Any, tme: str) -> str:

    # global boardsize
    # global komi
    # obal level
    global games

    game = games[gid]

    s = ""

    s += f"{tme} {cfg.boardsize} {cfg.komi} {game.w}({game.wrate}) {game.b}({game.brate}) {cfg.level} {joinMoves(game.mvs)} "
    s += res

    return s


def batchRate() -> None:

    global act
    global ratingOf
    global db
    global cgi

    anchors = dict()

    tme = now_string()

    for (nme, rat) in db.execute("SELECT name, rating FROM anchors"):
        anchors[nme] = rat

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
        else:
            wres = 0.0
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


def test_password(password: str) -> str:

    if password.isascii():
        # e  = "[^\d\w\.-]"
        if re.search(r"[^\d\w\.-]", password):
            return "Password must only alphanumeric, underscore, hyphen, period or digits characters."
    else:
        return "Password must consist of only ascii characters."

    if len(password) < 3:
        return "Password must be at least 3 characters."

    if len(password) > 16:
        return "Password limited to 16 characters."

    return ""


def valid_name(user_name: str) -> str:

    if user_name.isascii():
        # e = "[^\d\w\.-]"
        if re.search(r"[^\d\w\.-]", user_name):
            return "User name must only alphanumeric, underscore, hyphen, period or digits characters."
    else:
        return "User name must consist of only ascii characters."

    if len(user_name) < 3:
        return "User name must be 3 characters or more."

    if len(user_name) > 18:
        return "User name must be no more than 18 characters long."

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


def gameover(gid: int, sc: str, err: str) -> None:
    global games
    global act
    global vact
    global obs
    global id
    global db
    global dbrec

    del gme[gid]  # free memory of the game object

    game = games[gid]
    logger.info(f"gameover: {gid} {game.w} {game.b} {sc} {err}")

    ctime = datetime.datetime.now(datetime.timezone.utc)

    dte = ctime.strftime("%Y-%m-%d")
    tme = ctime.strftime("%Y-%m-%d %H:%M")

    if game.w in act:
        nsend(game.w, f"gameover {dte} {sc} {err}")
        act[game.w].msg_state = "gameover"

    if game.b in act:
        nsend(game.b, f"gameover {dte} {sc} {err}")
        act[game.b].msg_state = "gameover"

    wtu = cfg.level - game.wrt
    btu = cfg.level - game.brt

    # send gameover announcements to viewing clients
    # ----------------------------------------------
    for v in vact.values():
        try:
            send(v, f"gameover {gid} {sc} {wtu} {btu}")
        except:
            pass

    if gid in obs:
        for vk in obs[gid]:
            try:
                send(vact[vk], f"update {gid} {sc}")
            except:
                pass
        del obs[gid]

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
    see = seeRecord(gid, sc, dte, tme)

    dest_dir = os.path.join(
        cfg.htmlDir,
        cfg.sgfDir,
        ctime.strftime("%Y"),
        ctime.strftime("%m"),
        ctime.strftime("%d"),
    )
    os.makedirs(dest_dir, exist_ok=True)  # make directory if it doesn't exist

    dbrec.execute("INSERT INTO games VALUES(?, ?)", (gid, see))
    db.execute(
        """INSERT INTO games VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, "n" )""",
        (gid, game.w, game.wrate, game.b, game.brate, tme, wtu, btu, sc),
    )
    with open(f"{dest_dir}/{gid}.sgf", "w") as f:
        f.write(sgfString)

    # we can kill the active game record now.
    # ----------------------------------------
    del games[gid]


def viewer_respond(sock: Socket) -> None:

    global vact
    global id
    global games
    global obs
    global dbrec

    who = id[sock]

    # If we can no longer read from sock, close it.
    # ---------------------------------------------
    try:
        data = sock.read()
        if not data:
            raise Exception()
    except:
        sock.close()

        logger.error(f"[{who}] disconnected")

        del vact[who]
        del id[sock]
        del sockets[sock.fileno]
        return

    if data == "quit":
        sock.close()
        logger.info(f"viewer {who} quits")
        del vact[who]
        del id[sock]
        return

    req, param = data.split(maxsplit=1)

    if req == "observe":
        gid = int(param)

        if gid in games:

            game = games[gid]

            w = f"{game.w}({game.wrate})"
            b = f"{game.b}({game.brate})"

            logger.info(
                f"sending to viewer: game {gid} - - {cfg.boardsize} {cfg.komi} {w} {b} {cfg.level} ..."
            )

            msg = f"setup {gid} - - {cfg.boardsize} {cfg.komi} {w} {b} {cfg.level} {joinMoves(game.mvs)}"
            send(sock, msg)

            if gid in obs:
                if who not in obs[gid]:
                    obs[gid].append(who)
            else:
                obs[gid] = [who]
        else:
            rec = dbrec.execute(
                "SELECT dta FROM games WHERE gid = ?", (gid,)
            ).fetchone()
            if rec:
                dta = rec[0]
                send(sock, f"setup {gid} {dta}")
            else:
                send(sock, f"setup {gid} ?")


def player_respond(sock: Socket) -> None:
    global act
    global id
    global games
    global ratingOf
    global leeway
    global sid
    global vact
    global obs

    who = id[sock]
    user = act[who]

    # If we can no longer read from sock, close it.
    # ---------------------------------------------
    try:
        data = sock.read()
        if not data:
            raise Exception()
    except:
        logger.error(f"[{who}] disconnected")

        del act[who]
        del id[sock]
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


def _handle_player_quit(sock: Socket, data: str) -> None:
    who = id[sock]

    sock.close()
    logger.info(f"user {who} quits")
    del act[who]
    del id[sock]
    return


def _handle_player_protocol(sock: Socket, data: str) -> None:
    global db
    global dbrec

    who = id[sock]

    msg = data.strip()

    if msg[0:2] == "v1":
        del act[who]
        vact[who] = sock

        # close down current handler, open a new handler
        # ----------------------------------------------

        with db:
            logger.info(f"client: {data}")
            cc = db.execute("select count from clients where name = ?", (data,))
            # if  [string is integer -strict $cc]:
            if cc is not None:
                db.execute("update clients set count=count+1 where name = ?", (data,))
            else:
                db.execute("insert into clients values(?, 1)", (data,))

        logger.info(f"[{who}] logged on as viewer")

        gid: int

        # send out information about a few previous games
        # -----------------------------------------------
        for (gid, stuff) in dbrec.execute(
            "select gid, dta from games where gid > (select max(gid) from games) - 40 order by gid"
        ):
            dte, tme, bs, kom, w, b, lev, *lst = stuff.split(" ")
            res = lst[-1]
            send(sock, f"match {gid} {dte} {tme} {bs} {kom} {w} {b} {res}")

        # send out information about current games
        # ----------------------------------------
        for (gid, rec) in games.items():
            sw = f"{rec.w}({rec.wrate})"
            sb = f"{rec.b}({rec.brate})"
            logger.info(
                f"sending to viewer: match {gid} - - {cfg.boardsize} {cfg.komi} {sw} {sb}"
            )
            send(sock, f"match {gid} - - {cfg.boardsize} {cfg.komi} {sw} {sb} -")

        return

    if msg[0:2] == "e1":
        with db:
            logger.info(f"client: {data}")
            cc = db.execute("select count from clients where name = ?", (data,))
            # if  [string is integer -strict $cc] :
            if cc == 0:
                db.execute("update clients set count=count+1 where name = ?", (data,))
            else:
                db.execute("insert into clients values(?, 1)", (data,))
        act[who].msg_state = "username"
        send(sock, "username")
        return

    send(sock, "Error: invalid response")
    del act[who]
    del id[sock]
    try:
        sock.close()
    except:
        pass
    return


def _handle_player_username(sock: Socket, data: str) -> None:
    who = id[sock]

    data = data.strip()
    err = valid_name(data)  # returns "" or an error message

    if err == "":
        user_name = data
    else:
        send(sock, f"Error: {err}")
        del act[who]
        del id[sock]
        try:
            sock.close()
        except:
            pass

        return

    # -------------------------------------------------------------------------------------------------------
    # I think this fixes the connection bug.  When a user logs on, but the system believes he is already
    # logged on,  test to see if there is a connection by sending an informational message to old connection.
    # If this fails, then we can properly shut down the old connection and allow the new login.
    #
    # I hesitate to simply close the old connection no matter what since the password has not yet been
    # entered and so getting this right would require a bit more bookeeping.
    # -------------------------------------------------------------------------------------------------------
    if user_name in act:
        # test old connection
        xsoc = act[user_name].sock
        err_occur = False
        try:
            send(xsoc, "info another login is being attempted using this user name")
        except:
            err_occur = True
        if err_occur:
            try:
                xsoc.close()
            except:
                pass
            logger.error(f"Error: user {user_name} apparently lost old connection")
            del act[user_name]
            del id[xsoc]
        else:
            send(sock, "Error: You are already logged on!  Closing connection.")
            del act[who]
            del id[sock]
            try:
                sock.close()
            except:
                pass
            return

    id[sock] = user_name
    del act[who]
    act[user_name] = ActiveUser(sock, "password", 0, 0, 0)
    send(sock, "password")
    return


def _handle_player_password(sock: Socket, data: str) -> None:
    global db

    who = id[sock]

    pw = data.strip()
    # loginTime = now_seconds()

    err = test_password(pw)

    if err != "":
        send(sock, f"Error: {err}")
        try:
            sock.close()
        except:
            pass
        del act[who]
        del id[sock]
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
                cfg.defaultRating,
                cfg.maxK,
            ),
        )
        cmp_pw = pw
        rat = cfg.defaultRating
        k = cfg.maxK
        ratingOf[who] = strRate(rat, k)
    else:
        cmp_pw, rat, k = res
        ratingOf[who] = strRate(rat, k)

    if cmp_pw != pw:
        send(sock, "Sorry, password doesn't match")
        try:
            sock.close()
        except:
            pass
        del act[who]
        del id[sock]
        return

    logger.info(f"[{who}] logged on")

    act[who].rating = rat
    act[who].k = k
    act[who].msg_state = "waiting"

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

            msg_out = f"setup {gid} {cfg.boardsize} {cfg.komi} {cfg.level} {inf.w}({wr}) {inf.b}({br}) {joinMoves(inf.mvs)}"
            logger.info(msg_out)

            # determine who's turn to play
            # ----------------------------
            ply = len(inf.mvs)
            if ply & 1:
                ctm = inf.w
            else:
                ctm = inf.b

            # catch up the game
            # ------------------
            send(sock, msg_out)

            act[who].msg_state = "ok"
            act[who].gid = gid

            # determine if we need to send out a genmove command
            # --------------------------------------------------
            if ctm == who:
                if ply & 1:
                    # tr = inf.wrt
                    ct = now_milliseconds()
                    tl = inf.wrt - (ct - inf.lmst)
                    send(sock, f"genmove w {tl}")
                    act[who].msg_state = "genmove"
                    return
                else:
                    # tr = inf.brt
                    ct = now_milliseconds()
                    tl = inf.brt - (ct - inf.lmst)
                    send(sock, f"genmove b {tl}")
                    act[who].msg_state = "genmove"
                    return


def _handle_player_gameover(sock: Socket, data: str) -> None:
    who = id[sock]

    msg = data.strip()
    # log "msg recieved from $who is $msg"

    if msg == "ready":
        act[who].msg_state = "waiting"
        act[who].gid = 0
        return
    else:
        act[who].msg_state = "gameover"

    logger.info(f"[{who}] gave improper response to gameover: {msg}")


def _handle_player_genmove(sock: Socket, data: str) -> None:
    who = id[sock]

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
    over = ""

    # w, b, lmst, wrt, brt, wrate, brate, mvs = games[gid]
    game = games[gid]
    wrt = game.wrt
    brt = game.brt

    # make time calc, determine if game over for any reason
    # -----------------------------------------------------

    tt = ct - game.lmst - leeway  # fudge an extra moment

    if tt < 0:
        tt = 0

    if ctm & 1:
        wrt = wrt - tt
        games[gid].wrt = wrt
        if wrt < 0:
            over = "B+Time"
            gameover(gid, over, "")
            return
    else:
        brt = brt - tt
        games[gid].brt = brt
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
        if gid in obs:
            for s in obs[gid]:
                try:
                    send(vact[s], f"update {gid} {vmsg}")
                except:
                    pass
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
        game.mvs.append((data, wrt))
    else:
        game.mvs.append((data, brt))
    games[gid].mvs = game.mvs

    if game.w == who:
        nsend(game.b, f"play w {mv} {wrt}")
        vmsg = f"{mv} {wrt}"
    else:
        nsend(game.w, f"play b {mv} {brt}")
        vmsg = f"{mv} {brt}"

    if gid in obs:
        for s in obs[gid]:
            try:
                send(vact[s], f"update {gid} {vmsg}")
            except:
                pass

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
        else:
            over = f"B+{sc}"
            gameover(gid, over, "")
            return

    # game still in progress, start clock and send genmove
    # -----------------------------------------------------
    if game.w == who:
        if game.b in act:
            act[game.b].msg_state = "genmove"
            nsend(game.b, f"genmove b {brt}")
        games[gid].lmst = now_milliseconds()
    else:
        if game.w in act:
            act[game.w].msg_state = "genmove"
            nsend(game.w, f"genmove w {wrt}")
        games[gid].lmst = now_milliseconds()


def accept_connection(sock: Socket) -> None:
    global act
    global sid
    global defaultRating
    global id
    global maxK

    # fconfigure $sock -blocking 0 -buffering line
    # sock._socket.setblocking(False)

    # create a default id till we get user name
    # -----------------------------------------
    who = str(sid)
    sid += 1

    id[sock] = who

    act[who] = ActiveUser(sock, "protocol", 0, cfg.defaultRating, cfg.maxK)

    # Set up handler to "respond" when a message comes in
    # ---------------------------------------------------
    # TODO
    # fileevent $sock readable [list player_respond $sock]

    send(sock, "protocol")


def rcmp(a, b) -> int:
    a1 = a[1]
    b1 = b[1]

    if a1 < b1:
        return 1
    elif a1 > b1:
        return -1
    else:
        return 0


# --------------------------------------------------------
#  Estimate how much time left in current round in seconds
#
#  We will do it the "hard" way because of the forgiveness
#  factor given to each move can create inaccuracies.  The
#  easy way is to to take  round_start_time - (level * 2)
# ---------------------------------------------------------
def estimateRoundTimeLeft() -> int:
    global games
    global level

    wctl = 0  # worst case time left
    mtme = now_milliseconds()

    for v in games.values():
        tr = v.wrt + v.brt - (mtme - v.lmst)
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
    global vact
    global games
    global last_game_count
    global workdir
    global leeway
    global last_est
    global gme
    global db

    RANGE = 500.0  # minmum elo range allowed

    # determine if all games are complete
    # -----------------------------------
    ct = now_milliseconds()

    count = 0  # number of active games

    for (gid, rec) in games.items():

        # w, b, lmst, wrt, brt, wrate, brate, mvs = rec

        ctm = gme[gid].colorToMove()

        if ctm & 1:
            tr = rec.wrt
            tu = ct - rec.lmst - leeway
            if tu < 0:
                tu = 0
            time_left = tr - tu
            if time_left < 0:
                games[gid].wrate = time_left
                gameover(gid, "B+Time", "")
                count += 1  # so that we get to recyle
            else:
                count += 1
        else:
            tr = rec.brt
            tu = ct - rec.lmst - leeway
            if tu < 0:
                tu = 0
            time_left = tr - tu
            if time_left < 0:
                games[gid].brate = time_left
                gameover(gid, "W+Time", "")
                count += 1  # so that we get to recyle
            else:
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
                db.close()
                logger.info("KILL FILE FOUND - EXIT CGOS")
                sys.exit(0)

            # dynamically computer ELO RANGE
            # ------------------------------
            lst: List[Tuple[str, float]] = []

            for (name, v) in act.items():
                # sock, state, gid, rating = v

                if v.msg_state == "waiting":
                    r = v.rating
                    lst.append((name, r))

            lst.sort(key=lambda e: e[1])
            max_interval = 0.0

            ll = len(lst)
            e = ll - SKIP

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

            lst.sort(key=lambda e: e[1])

            if len(lst) > 1:

                logger.info(f"will schedule: {len(lst)} players")

                lst_pairs = iter(lst)
                for (aa, bb) in zip(lst_pairs, lst_pairs):

                    if bb is not None:

                        # set up white and black players
                        # ------------------------------
                        wp = aa[0]  # actual player names
                        bp = bb[0]  # actual player names

                        wco = db.execute(
                            "SELECT count(*) FROM games WHERE w==? AND b==?", (wp, bp)
                        ).fetchone()[0]
                        bco = db.execute(
                            "SELECT count(*) FROM games WHERE w==? AND b==?", (bp, wp)
                        ).fetchone()[0]

                        # swap white and black if black has not been played as many times
                        if bco < wco:
                            tmp = bp
                            bp = wp
                            wp = tmp

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

                        games[gid] = Game(wp, bp, 0, cfg.level, cfg.level, wr, br, [])
                        act[wp].gid = gid
                        act[bp].gid = gid
                        msg_out = f"setup {gid} {cfg.boardsize} {cfg.komi} {cfg.level} {wp}({wr}) {bp}({br})"
                        nsend(wp, msg_out)
                        nsend(bp, msg_out)

                        vmsg = f"match {gid} - - {cfg.boardsize} {cfg.komi} {wp}({wr}) {bp}({br}) -"
                        for vv in vact.values():
                            send(vv, vmsg)

                        logger.info(f"starting {wp} {wr} {bp} {br}")

                # add a 5 second delay to let all programs complete setup.
                # ------------------------------------------------------

                time.sleep(3000 / 1000)

                view_count = len(vact)
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
                    games[gid].lmst = ct
                    act[bp].msg_state = "genmove"
                    act[wp].msg_state = "ok"
                    wd.write(f"s {tmeSch} {gid} {rec}")

        os.rename(tmpf, cfg.web_data_file)

    # after idle [list after 15000 schedule_games]    ;# every 15 seconds
    # t = threading.Timer(15.0, schedule_games)
    # t.start()


last_est = now_seconds()


def server_loop() -> None:
    # Create our server on the expected port
    # ------------------------------------------
    server_addr = ("", cfg.portNumber)
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.bind(server_addr)
    server_socket.listen(5)

    # Create a game scheduling event
    # ------------------------------

    # after 45000ms schedule_games
    time_schedule_games = now_seconds() + 45.0

    # the event loop
    read_list: List[socket.socket] = [server_socket]
    timeout = 1.0
    try:
        while True:
            readable: List[socket.socket]
            read_list = [server_socket]
            read_list += [s._socket for s in id.keys()]
            readable, writable, errored = select.select(read_list, [], [], timeout)
            for s in readable:
                if s is server_socket:
                    client_socket, address = server_socket.accept()
                    read_list.append(client_socket)
                    logger.info(f"Connection from {address}")
                    sock = Socket(client_socket)
                    sockets[sock.fileno] = sock
                    accept_connection(sock)
                else:
                    # print(f"Recv client {s.fileno()} in {sockets.keys()}")
                    if s.fileno() in sockets:
                        sock = sockets[s.fileno()]
                        who = id[sock]
                        # print(f"Recv client from {who}")

                        if who in vact:
                            # print(f"handle viewer {who}")
                            viewer_respond(sock)
                        else:
                            # print(f"handle player {who}")
                            player_respond(sock)

            if now_seconds() >= time_schedule_games:
                schedule_games()
                # every 15 seconds
                time_schedule_games = now_seconds() + 15.0
    finally:
        server_socket.close()


if __name__ == "__main__":

    try:
        initDatabase()
        openDatabase()
    except Exception:
        logger.error(traceback.format_exc())
        sys.exit(1)

    server_loop()
