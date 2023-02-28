# The MIT License
#
# Copyright (C) 2009 Don Dailey and Jason House
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

import os
import sys
import datetime
import re
import sqlite3
import time
from typing import Any, Dict, List, Tuple

from util.timeutils import now_string
from app.cgos import Configs


def log(msg: str) -> None:
    tme = now_string()
    print(f"{tme} | {msg}")


rating: Dict[str, str] = {}
db: sqlite3.Connection


def formatSgfPath(dte: str, gid: str) -> str:
    vsgfpath = f"{cfg.boardsize}x{cfg.boardsize}/{cfg.sgfDir}/{dte[0:4]}/{dte[5:7]}/{dte[8:10]}/{gid}.sgf"
    return vsgfpath


def crosstable(who: str) -> None:

    global rating

    count: Dict[str, int] = {}
    wins: Dict[str, int] = {}
    draws: Dict[str, int] = {}
    arate: Dict[str, Tuple[str, str]] = {}
    brate: Dict[str, Tuple[str, str]] = {}

    print(f"building for {who}")

    with db:
        wgms = db.execute(
            "SELECT gid, b, br, dte, wr, wtu, res FROM games WHERE w=? ORDER BY gid",
            (who,),
        ).fetchall()
        bgms = db.execute(
            "SELECT gid, w, wr, dte, br, btu, res FROM games WHERE b=? ORDER BY gid",
            (who,),
        ).fetchall()

    for (gid, opp, r, dte, my_r, my_time, res) in wgms:
        if opp not in count:
            count[opp] = 0
            wins[opp] = 0
            draws[opp] = 0

        d = 0
        w = 0
        if res[0] == "W":
            w = 1
        elif res[0] == "B":
            w = 0
        else:
            d = 1

        count[opp] += 1
        wins[opp] += w
        draws[opp] += d

        arate[opp] = (gid, r)
        brate[opp] = (gid, r)

    for (gid, opp, r, dte, my_r, my_time, res) in bgms:
        # puts "bgsm: $gid $opp $r $my_r $my_time $res $dte"
        if opp not in count:
            count[opp] = 0
            wins[opp] = 0
            draws[opp] = 0

        d = 0
        w = 0

        if res[0] == "B":
            w = 1
        elif res[0] == "W":
            w = 0
        else:
            d = 1

        count[opp] += 1
        wins[opp] += w
        draws[opp] += d

        brate[opp] = (gid, r)
        if opp not in arate:
            arate[opp] = (gid, r)

    olst = count.keys()

    lst: List[List[Any]] = []

    for n in olst:
        ga = arate[n][0]
        gb = brate[n][0]

        if ga > gb:
            r = arate[n][1]
        else:
            r = brate[n][1]

        winp = 100.0 * ((wins[n] + draws[n] * 0.5) / (count[n] + 0.0))

        match = re.search("(-?\\d+)", str(r))
        if not match:
            raise ValueError(f"error:{r}")
        rr = int(match[1])

        lst.append(["%6d" % rr, n, "%7.2f" % winp, wins[n], draws[n], count[n]])

    lst.sort(key=lambda e: -int(e[0]))

    now = datetime.datetime.now(datetime.timezone.utc)
    date = now.strftime("%Y-%m-%d %T")

    # put the css here
    # --------------------------------------
    rpt = f"""<html>
    <title>Crosstable for {who}</title>
    <head>
    <style type="text/css">
    table.solid {{border-style:solid ; border-width: 1px 1px 1px 1px }}
    tr.solid {{border-style:solid ; border-width: 1px 1px 1px 1px }}
    .centeredImage {{text-align:center; margin-top:0px; margin-botom:0px; padding:0px;}}
    </style>
    </head>

    <body BGCOLOR="#ECECEA" TEXT="#001000" LINK="#406040" ALINK="#80B080" VLINK="#406040"><p>
    <p class="centeredImage"><img src="../images/cgosLogo.jpg"></p>
    """

    # append rpt "<FONT COLOR=\"\#004000\"></FONT>\n"

    if who in rating:
        rat = rating[who]
    else:
        rat = "??"

    rpt += f"""<H3 ALIGN=CENTER>Cross-table of results for {who}</H3>
    <H3 ALIGN=CENTER>Rated: {rat}</H3>
    <H4 ALIGN=CENTER>as of {date}</H4>
    <p>&nbsp;<p>

    <center><table class=solid cellspacing=0 justify=center>
    <colgroup span=4><col width=210></col><col width=90></col><col width=120></col><col width=90></col></colgroup>

    <tr BGCOLOR="#708070" style="color:white">
    <th align=left>Opponent</th>
    <th align=left>Rating</th>
    <th align=left>Result</th>
    <th align=left>Percent</th>
    </tr>
    </table>

    <p style="margin: 3px">
    """

    tog = ["#e0e0e0", "#ffffff"]
    tcc = 0

    rpt += """<center><table class=solid cellspacing=0 justify=center style="font-family;verdana;font-size:80%">
    <colgroup span=4><col width=210></col><col width=90><col width=120></col><col width=90></col></colgroup>
    """

    for rec in lst:
        rat, opp, winp, twins, tdraws, tgames = rec
        rpt += f"<tr bgcolor='{tog[tcc]}'>"
        if tdraws == 0:
            rpt += f"<td>{opp}</td><td>{rat}</td><td class=solid>{twins} / {tgames}</td><td class=solid>{winp}</td></tr>\n"
        else:
            rpt += f"<td>{opp}</td><td>{rat}</td><td class=solid>{twins} / {tdraws} / {tgames}</td><td class=solid>{winp}</td></tr>\n"
        tcc = tcc ^ 1

    rpt += "</table></center>\n"

    view_num = 300
    v_n = (view_num * 7) - 1  # SELECT gid, b, br, dte, wr, my_time, res  ... 7 list

    wgms_short = wgms[-v_n:]
    bgms_short = bgms[-v_n:]

    listgame = []
    for (gid, opp, r, dte, my_r, my_time, res) in wgms_short:
        listgame.append([int(gid), opp, r, my_r, my_time, *dte.split(" "), res, "W"])
    for (gid, opp, r, dte, my_r, my_time, res) in bgms_short:
        listgame.append([int(gid), opp, r, my_r, my_time, *dte.split(" "), res, "B"])

    listgamesort = listgame.copy()
    listgamesort.sort(key=lambda e: -int(e[0]))  # [lsort -decreasing $listgame]

    list_num = len(listgamesort)
    dsp_num = view_num
    if dsp_num > list_num:
        dsp_num = list_num

    loop = 0

    tog = ["#f0f0e0" "#c8d0c8"]
    rpt += f"""<center><h3>Recent {dsp_num} Games</h3>
    <table class=solid cellspacing=0 justify=center style="font-family;verdana;font-size:80%">
    <colgroup span=5><col width=210></col><col width=100><col width=100></col><col width=70></col><col width=70></col></colgroup>
    <tr><th align=left>Opponent</th><th align=left>Opp rating</th><th align=left>Result</th><th align=left>Time</th><th align=left>Rating</th><th align=left>Game</th></tr>
    """
    for rec in listgamesort:
        gid, opp, r, my_r, my_time, dte, dte2, res, col = rec
        sgfpath = f"../{cfg.sgfDir}/{dte[0:4]}/{dte[5:7]}/{dte[8:10]}/{gid}.sgf"
        vsgfpath = formatSgfPath(dte, gid)

        w0 = ""
        w1 = ""
        if res[2] == "T":
            w0 = "<B>"
            w1 = "</B>"
        winner = ""
        if res[0] == col:
            winner = "winner"

        if res[0] == "D":
            rpt += '<tr bgcolor="#ccff33">'
        elif winner == "":
            rpt += '<tr bgcolor="#ffcccc">'
        else:
            rpt += '<tr bgcolor="#f0f0e0">'

        t = my_time / 1000
        ti = "%02d:%02d" % (t // 60, t % 60)

        rpt += f'<td>{opp}</td><td>{r}</td><td>{w0} {res} {w1}</td><td>{ti}</td><td>{my_r}</td><td><a href="{sgfpath}">{gid}</a> <a href="../../viewer.cgi?{vsgfpath}">View</a></td></tr>\n'
        #        append rpt "<td>$opp</td><td>$r</td><td>$w0 $res $w1</td><td>$my_r</td><td><a href=\"$sgfpath\">$gid</a></td></tr>\n"
        #        append rpt "<td>$opp</td><td>$rat</td><td class=solid>$twins / $tdraws / $tgames</td><td class=solid>$winp</td></tr>\n"
        loop += 1
        if loop >= view_num:
            break
        tcc = tcc ^ 1

    rpt += "</table></center>\n"
    rpt += "<p>&nbsp;<p>\n"
    #   foreach {gid opp r dte res} $bgms {        append rpt "$gid / $opp / $r / $res / $dte\n<br>" }

    rpt += "<H4 align=center>"
    rpt += '<a href="../standings.html">Returns to Current Standings Page.</a>'
    rpt += "</H4><br>"
    rpt += "</body>\n"
    rpt += "</hmtl>\n"

    # return

    print(f"trying to open and write: {cfg.htmlDir}/cross/{who}.html")
    os.makedirs(f"{cfg.htmlDir}/cross/", exist_ok=True)
    with open(f"{cfg.htmlDir}/cross/{who}.html", "w") as f:
        f.write(rpt)


def buildWebPage() -> None:
    global tmpfile
    global pageName
    global rating

    now = datetime.datetime.now(datetime.timezone.utc)
    right_now = now.strftime("%Y-%m-%d %H:%M:%S %Z")

    f = open(cfg.web_data_file, "r")
    os.makedirs(os.path.dirname(tmpfile), exist_ok=True)
    wf = open(tmpfile, "w")

    tme = now.strftime("%Y-%m-%d %H:%M")

    players: List[List[Any]] = []
    gms: List[List[Any]] = []
    sch: List[List[Any]] = []
    active: Dict[str, str] = {}
    bcr: Dict[str, int] = {}

    # read in the data
    # ----------------

    for s in f:
        if s[0] == "u":
            dmy, nme, cnt, rat, dte, tme = s.split(" ")
            m = re.search("(-?\\d+)\\?", rat)
            usr: List[Any]
            if m:
                usr = [int(m[1]), 0, nme, cnt, dte, tme]
                players.append(usr)
            else:
                usr = [rat, 1, nme, cnt, dte, tme]
                players.append(usr)

        if s[0] == "g":
            dmy, gid, w, wr, b, br, dte, tme, wtl, btl, res = s.split(" ")
            gms.append([gid, w, wr, b, br, f"{dte} {tme}", wtl, btl, res])
            bcr[w] = 1
            bcr[b] = 1

        if s[0] == "s":
            dmy, dte, tme, gid, w, b, x, wtl, btl, wr, br = s.split(" ")
            sch.append([gid, w, wr, b, br, f"{dte} {tme}"])
            active[w] = gid
            active[b] = gid

    wf.write(
        f"""<html>
    <title>{cfg.serverName}</title>
    <head>
    <style type="text/css">
    table.solid {{border-style:solid ; border-width: 1px 1px 1px 1px }}
    tr.solid {{border-style:solid ; border-width: 1px 1px 1px 1px }}
    .centeredImage {{text-align:center; margin-top:0px; margin-botom:0px; padding:0px;}}
    </style>
    </head>

    <body BGCOLOR="#ECECEA" TEXT="#001000" LINK="#002000" ALINK="#507050" VLINK="#002000"><p>
    <p class="centeredImage"><img src="images/cgosLogo.jpg"></p>
    <FONT COLOR="002000"><H3 ALIGN=CENTER>{cfg.htmlInfoMsg}</H3></FONT>
    <P>
    <FONT COLOR=\"002000\"><H4 ALIGN=CENTER>Last Update: {right_now}</H4></FONT>
    <P>

    <center><H5>
    <a href="bayes.html">BayesElo</a> is more accurate.<br>
    <a href="http://senseis.xmp.net/?ComputerGoServer">Sensei's Computer Go Server Page</a></H5></center>

    <p><p>

    <center><table border=1 cellpadding=4 cellspacing=0 justify=center style="font-family;verdana;font-size:90%">
    <tr BGCOLOR="#708070" style="color:white"><th>Game</th><th>Program Name</th><th>Rating</th><th>Games Played</th><th>Last Game</th></tr>
    """
    )

    cur_time = datetime.datetime.now(datetime.timezone.utc)
    # provisional age
    pcut = (cur_time - datetime.timedelta(days=cfg.provisionalAge)).strftime(
        "%Y-%m-%d %H:%M:%S"
    )
    # established age
    ecut = (cur_time - datetime.timedelta(days=cfg.establishedAge)).strftime(
        "%Y-%m-%d %H:%M:%S"
    )

    players.sort(key=lambda e: -int(e[0]))
    for rec in players:
        rat, k, nme, cnt, dte, tme = rec

        dtime = f"{dte} {tme}"

        if k == 0:
            print(f"{nme} -> {dtime}")
            print(f"{nme} -> {pcut}\n")

            # provisionally rated player
            if dtime < pcut:
                print(f"{nme} being excluded")
                continue

        if k == 1:
            if dtime < ecut:
                continue

        bg = "#ffffff"
        if k == 0:
            bg = "#ffff80"
            rat = f"{rat}?"

        if nme in active:
            status = active[nme]
        else:
            status = "&mdash;"

        wf.write(f'<tr bgcolor="{bg}"><td align=center>{status}</td>')
        wf.write(
            f'<td><a href="cross/{nme}.html">{nme}</a></td><td>{rat}</td><td align=center>{cnt}</td><td>{dte} {tme}</td></tr>'
        )

    wf.write(
        """</table></center>
    <P>&nbsp;<P>"""
    )

    # -------------------------------------------------------------------------------------------------------------------

    wf.write(
        """<H4 ALIGN=CENTER>Recent Games</H4>
    <center><table class=solid cellspacing=0 justify=center style="font-family;verdana;font-size:90%">
    <colgroup span=5><col width=80></col><col width=200></col><col width=80></col>
    <col width=200></col><col width=80></col><col width=110></col></colgroup>

    <tr BGCOLOR="#708070" style="color:white">
    <th align=center>Game</th>
    <th align=left>White</th>
    <th align=left>Time</th>
    <th align=left>Black</th>
    <th align=left>Time</th>
    <th align=left>Result</th>
    </tr>
    </table></center>

    <p style="margin: 3px">

    <center><table class=solid cellspacing=0 justify=center style="font-family;verdana;font-size:75%">
    <colgroup span=5><col width=80></col><col width=200></col><col width=80></col>
    <col width=200></col><col width=80><col width=110></col></colgroup>
    """
    )

    # set tog [list "\#f0f0d0" "\#c0d0c0" ]
    tog = ["#f0f0e0", "#c8d0c8"]
    tcc = 0

    # insert games being played in this round
    # ---------------------------------------
    for rec in sch:
        gid, w, wr, b, br, dte = rec
        wn = f"{w}({wr})"
        bn = f"{b}({br})"

        res = "- playing ..."
        # set  tme "&mdash;"
        tw = "&mdash;"
        tb = "&mdash;"

        vsgfpath = formatSgfPath(dte, gid)

        wf.write(
            f"""<tr bgcolor="{tog[tcc]}">
<td align=center>{gid}</td><td>{wn}</td><td>{tw}</td><td>{bn}</td><td>{tb}</td>
<td>{res} <a href="../../viewer.cgi?{vsgfpath}">View</a></td></tr>
"""
        )

        tcc = tcc ^ 1

    # insert games from previous rounds here
    # ---------------------------------------

    gms.sort(key=lambda e: -int(e[0]))
    for rec in gms:
        gid, w, wr, b, br, tme, wtl, btl, res = rec
        wn = f"{w}({wr})"
        bn = f"{b}({br})"

        tw_ = int(wtl) // 1000
        tb_ = int(btl) // 1000

        tw = "%02d:%02d" % (tw_ // 60, tw_ % 60)
        tb = "%02d:%02d" % (tb_ // 60, tb_ % 60)

        wf.write(f'<tr bgcolor="{tog[tcc]}">')

        sgfpath = formatSgfPath(tme, gid)

        res_col = f"{res}"
        if res[2] == "T":
            res_col = f'<b><font color="red">{res}</font></b>'

        if res[0] == "W":
            wf.write(
                f'<td align=center><a href="{sgfpath}">{gid}</a></td><td><b>{wn}</b></td><td>{tw}</td><td>{bn}</td><td>{tb}</td><td>{res_col}</td></tr>\n'
            )
        else:
            wf.write(
                f'<td align=center><a href="{sgfpath}">{gid}</a></td><td>{wn}</td><td>{tw}</td><td><b>{bn}</b></td><td>{tb}</td><td>{res_col}</td></tr>\n'
            )

        tcc = tcc ^ 1

    wf.write("</table>\n")

    if cfg.boardsize == 19:
        wf.write(
            """<H5>LZ_05db_ELFv2_p800 has been fixed at 3670(from 3102) to match <a href="bayes.html">BayesElo</a>. (2020-06-11)<br>
        <font color="blue">Real-time game viewer</font> is available on <a href="https://deepleela.com/cgos">DeepLeela</a></H5>"""
        )

    wf.write("</center></body>")

    # ---------------------------------------------------------------------------------------------------------

    wf.write("</html>")

    wf.close()

    os.rename(tmpfile, pageName)

    for n in bcr.keys():
        print(f"ready crosstable {n}")
        #        if n == "Gnugo-3.7.10-a1" && cfg.boardsize == 9:
        #            continue

        crosstable(n)

    print("crosstable end...")


if len(sys.argv) < 2:
    print("Must specify a configuration file.")
    sys.exit(1)
else:
    cfg = Configs()
    cfg.load(sys.argv[1])


# set up a long timeout for transactions
try:
    db = sqlite3.connect(cfg.database_state_file, timeout=40000)
except sqlite3.Error as e:
    print(f"Error opening {cfg.database_state_file} datbase.")
    raise Exception(e)

try:
    cgi = sqlite3.connect(cfg.cgi_database, timeout=80000)
except sqlite3.Error as e:
    print(f"Error opening {cfg.cgi_database} datbase.")
    raise Exception(e)


def update_ratings():
    global rating

    for (nme, rat, k) in db.execute("SELECT name, rating, K FROM password"):

        rat = int(rat + 0.5)

        if k <= 16.0:
            rating[nme] = rat
        else:
            rating[nme] = f"{rat}?"


tmpfile = f"{cfg.htmlDir}/standings.tmp"
pageName = f"{cfg.htmlDir}/standings.html"

ct = 0.0
count = 0

while True:
    x = os.path.getmtime(cfg.web_data_file)

    print(cfg.web_data_file)

    if x != ct:
        count += 1
        # puts "$count) File changed!"

        update_ratings()
        buildWebPage()

        ct = x

    time.sleep(28000 / 1000)
