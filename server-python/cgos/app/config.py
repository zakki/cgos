# The MIT License
#
# Copyright (C) 2009 Don Dailey and Jason House
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

import configparser
import sys
from enum import Enum
from typing import Optional

from util.logutils import getLogger
from gogame import KoRule


# Setup logger
logger = getLogger("cgos_server.client")


class MatchMode(Enum):
    AUTO = 0
    ADMIN = 1


class Configs:
    serverName: str
    rule: str
    boardsize: int
    komi: float
    koRule: KoRule
    level: int
    portNumber: int
    timeGift: float
    database_state_file: str
    game_archive_database: Optional[str]
    web_data_file: str
    defaultRating: float
    minK: float
    maxK: float
    htmlDir: str
    htmlInfoMsg: str
    sgfDir: str
    compressSgf: bool
    provisionalAge: float
    establishedAge: float
    killFile: str
    tools_dir: str
    bin_dir: str
    leeway: int
    anchor_match_rate: float
    badUsersFile: str
    moveIntervalBetweenSave: int
    hashPassword: bool
    matchMode: MatchMode

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
        self.rule = str(cfg["rule"])
        self.boardsize = int(cfg["boardsize"])
        self.komi = float(cfg["komi"])
        if "ko" in cfg:
            try:
                self.koRule = KoRule[cfg["ko"]]
            except:
                logger.error(f"Bad ko rule {cfg['ko']}")
                sys.exit(1)
        else:
            self.koRule = KoRule.POSITIONAL

        self.level = int(cfg["level"]) * 1000
        self.timeGift = float(cfg["timeGift"])
        self.database_state_file = str(cfg["database_state_file"])
        if "game_archive_database" in cfg:
            self.game_archive_database = str(cfg["game_archive_database"])
        else:
            self.game_archive_database = None
        self.web_data_file = str(cfg["web_data_file"])
        self.defaultRating = float(cfg["defaultRating"])
        self.minK = float(cfg["minK"])
        self.maxK = float(cfg["maxK"])
        self.htmlDir = str(cfg["htmlDir"])
        self.htmlInfoMsg = str(cfg["htmlInfoMsg"])
        self.sgfDir = str(cfg["sgfDir"])
        if "compressSgf" in cfg:
            self.compressSgf = cfg.getboolean("compressSgf")
        else:
            self.compressSgf = False
        self.provisionalAge = float(cfg["provisionalAge"])
        self.establishedAge = float(cfg["establishedAge"])
        self.killFile = str(cfg["killFile"])
        self.tools_dir = str(cfg["tools_dir"])
        self.bin_dir = str(cfg["bin_dir"])
        self.anchor_match_rate = float(cfg.get("anchor_match_rate", "0.10"))
        self.badUsersFile = str(cfg["bad_users_file"])
        self.moveIntervalBetweenSave = int(cfg["moveIntervalBetweenSave"])
        if "hashPassword" in cfg:
            self.hashPassword = cfg.getboolean("hashPassword")
        else:
            self.hashPassword = False

        self.matchMode = MatchMode.AUTO
        if "matchMode" in cfg:
            try:
                self.matchMode = MatchMode[cfg["matchMode"]]
            except:
                logger.error(f"Bad match mode {cfg['matchMode']}")
                sys.exit(1)
        logger.info(f"Match mode {self.matchMode}")
