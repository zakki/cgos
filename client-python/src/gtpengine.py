"""
Copyright (C) 2009 Christian Nentwich and contributors

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""

import json
import logging
import logging.handlers
import os
import subprocess
import sys
import time
from typing import Any, Dict, List, Optional, Tuple

from common import Colour


class EngineConnectorError(Exception):
    def __init__(self, msg):
        self._msg = msg

    def __str__(self):
        return repr(self._msg)


def encodeOwnership(ownership: List[float]) -> str:
    CHARS = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/"

    def encode(r: float) -> str:
        i = max(0, min((r + 1) / 2, 1))
        # i = r
        return CHARS[round(i * 62)]

    return "".join([encode(f) for f in ownership])


class AnalyzeResultParser:

    NUMBER_ATTRIBUTES = ["visits", "winrate", "prior", "lcb", "prior", "lcb", "utility", "scoreMean", "scoreStdev", "scoreLead", "scoreSelfplay", "utilityLcb", "weight", "order", "pvEdgeVisits", "movesOwnership", "movesOwnershipStdev",]

    def __init__(self, tokens: List[str], logger: logging.Logger, convertLz = False):
        self.tokens = tokens
        self.pos = 0
        self.convertLz = convertLz
        self.logger = logger
        self.sendsCustomAttributes = False

    def _next(self) -> str:
        t = self.tokens[self.pos]
        self.pos += 1
        return t

    def _has_next(self) -> bool:
        return self.pos < len(self.tokens)

    def _lookahead(self) -> Optional[str]:
        if self.pos < len(self.tokens):
            return self.tokens[self.pos]
        return None

    def _nextNumber(self):
        t = self._next()
        try:
            return int(t)
        except ValueError:
            return float(t)

    def _parseInfo(self) -> Dict:
        m: Dict[str, Any] = dict()
        while True:
            t = self._lookahead()
            if t is None or t == "info" or t == "ownership":
                return m
            t = self._next()

            if t not in ["move", "winrate", "score", "scoreLead", "pv", "prior", "visits"]:
                if self.sendsCustomAttributes:
                    if "custom" not in m:
                        m["custom"] = dict()
                    if t in AnalyzeResultParser.NUMBER_ATTRIBUTES:
                        m["custom"][t] = self._nextNumber()
                    else:
                        m["custom"][t] = self._next()
                else:
                    v = self._next()
                    self.logger.debug(f"skip custom attribute {t} {v}")
                continue

            if t == "pv":
                pv = []
                while True:
                    t = self._next()
                    pv.append(t)
                    t = self._lookahead()
                    if t is None or t == "info" or t == "ownership":
                        if len(pv) > 1:
                            m["pv"] = " ".join(pv[1:])
                        return m

            if t == "winrate" or t == "prior":
                f = self._nextNumber()
                if self.convertLz:
                    m[t] = f / 10000
                else:
                    m[t] = f
            elif t == "scoreLead":
                m["score"] = self._nextNumber()
            elif t in AnalyzeResultParser.NUMBER_ATTRIBUTES:
                m[t] = self._nextNumber()
            else:
                m[t] = self._next()

    def _parseOwnership(self) -> str:
        l: List[float] = []
        while self._has_next():
            l.append(self._nextNumber())
        return encodeOwnership(l)

    def parse(self) -> Dict:
        info: Dict[str, Any] = dict()
        info["moves"] = []
        totalVisits = 0
        while self._has_next():
            t = self._next()
            if t == "info":
                m = self._parseInfo()
                if "visits" in m:
                    totalVisits += m["visits"]
                info["moves"].append(m)
            elif t == "ownership":
                info["ownership"] = self._parseOwnership()
            else:
                self.logger.info(f"skip unknown element {t} {self._lookahead()}")

        # Calculate root win-rate and score weighted average
        if totalVisits > 0:
            winrate = 0
            hasWinrate = False
            score = 0
            hasScore = False
            for m in info["moves"]:
                if "visits" not in m:
                    continue
                if "winrate" in m:
                    winrate += m["winrate"] * m["visits"] / totalVisits
                    hasWinrate = True
                if "score" in m:
                    score += m["score"] * m["visits"] / totalVisits
                    hasScore = True
            info["visits"] = totalVisits
            if hasWinrate:
                info["winrate"] = winrate
            if hasScore:
                info["score"] = score

        return info


class GTPTools(object):
    """
    Static utilities for converting GTP colours and coordinates to canonical representations.
    """

    __LEGAL_COORDINATES = "abcdefghjklmnopqrstuvwxyz"

    @staticmethod
    def convertConstantToColour(constant):
        """Convert a constant from the Colour class to a GTP colour"""
        return {Colour.WHITE: "W", Colour.BLACK: "B"}[constant]

    @staticmethod
    def convertXYToCoordinate(self, xy):
        """Convert an (x,y) tuple to a GTP board coordinate."""
        (x, y) = xy
        return GTPTools.__LEGAL_COORDINATES[x - 1]

    @staticmethod
    def convertColourToConstant(colourstr):
        """Convert a GTP coordinate to a constant from the Colour class"""
        try:
            colourstr = colourstr.lower()
            const = {
                "w": Colour.WHITE,
                "white": Colour.WHITE,
                "b": Colour.BLACK,
                "black": Colour.BLACK,
            }[colourstr]
            return const
        except KeyError:
            raise EngineConnectorError("Invalid GTP player colour: '" + colourstr + "'")

    @staticmethod
    def convertCoordinateToXY(coordstr):
        """Convert a GTP board coordinate to an (x,y) tuple"""
        try:
            column = GTPTools.__LEGAL_COORDINATES.index(coordstr[0].lower()) + 1
            row = int(coordstr[1:])
            return (column, row)
        except ValueError as IndexError:
            raise EngineConnectorError("Invalid coordinate: '" + coordstr + "'")


class EngineConnector(object):
    """
    EngineConnector is the interface to a GTP engine, whether that engine is creating
    moves or just observing by receiving play commands.

    The "notify" methods are used to send commands to the engine and check responses.
    It is safe to give time handling commands to the engine - the connector will only
    issue them if the engine supports it. The "notifyCGOS" methods call cgos GTP extensions.

    Call connect() to launch the engine before using it. When done, the engine is given
    a "quit" command and if it fails to respond in time, it is killed using the OS.
    """

    MANDATORY_PLAYING_COMMANDS = [
        "boardsize",
        "clear_board",
        "komi",
        "play",
        "genmove",
        "quit",
    ]
    """ Mandatory commands for an engine that can play a game. """

    MANDATORY_OBSERVE_COMMANDS = ["boardsize", "clear_board", "komi", "play", "quit"]
    """ Mandatory commands for an engine that can observe a game (like GoGUI). """

    def __init__(
        self, programCommandLine: str, name: str,
        logger: str = "EngineConnector", logfile: Optional[str] = "engine.log"
    ):
        self._programCommandLine = programCommandLine
        self._name = name
        self._subprocess = None
        self._supportedCommands: List[str] = []

        self.logger = logging.getLogger(logger)
        self.logger.setLevel(logging.DEBUG)

        if len(self.logger.handlers) == 0:
            self.formatter = logging.Formatter(
                "%(asctime)s - %(levelname)s: %(message)s"
            )

            if logfile is not None:
                logdir = os.path.dirname(logfile)
                if logdir != '':
                    os.makedirs(logdir, exist_ok=True)
                self.handler = logging.FileHandler(logfile)
                self.handler.setLevel(logging.DEBUG)
                self.handler.setFormatter(self.formatter)

                self.logger.addHandler(self.handler)

            # Log info output to console
            handler = logging.StreamHandler(sys.stdout)
            handler.setLevel(logging.INFO)

            formatter = logging.Formatter("%(asctime)s: %(message)s")
            handler.setFormatter(formatter)

            self.logger.addHandler(handler)

    def __del__(self):
        self.shutdown()

    def connect(self, mandatoryCommands=MANDATORY_PLAYING_COMMANDS):
        """
        Launch the GTP engine as a sub-process. Will throw an EngineConnectorError if
        this fails. This will also use GTP list_commands to check the capabilities of the
        engine.
        """
        self.logger.info(
            "Starting GTP engine, command line: " + self._programCommandLine
        )
        if sys.platform == "win32":
            args = self._programCommandLine
        else:
            args = self._programCommandLine.split()
        self._subprocess = subprocess.Popen(
            args, stdin=subprocess.PIPE, stdout=subprocess.PIPE, shell=False, text=True
        )
        time.sleep(1)
        self._findSupportedCommands(mandatoryCommands)

    def getName(self):
        return self._name

    def shutdown(self):
        """
        Shut down the GTP engine using the 'quit' command, or kill it if it does not
        support that or takes too long.
        """
        if self._subprocess is not None and self._subprocess.poll() is None:
            self.logger.info(
                "Shutting down GTP engine, command line: " + self._programCommandLine
            )
            self._sendNoResponseCommand("quit")

            for i in range(5):
                time.sleep(0.5)
                if self._subprocess.poll() is None:
                    self.logger.info("Sending terminate")
                    self._subprocess.terminate()
                    break

            self._subprocess = None

    def hasTimeControl(self):
        """
        Return true if the engine supports time management.
        """
        return (
            "time_left" in self._supportedCommands
            and "time_settings" in self._supportedCommands
        )

    def getGenmoveAnalyzeMode(self) -> Optional[str]:
        """
        Return true if the engine supports time management.
        """
        if "cgos-genmove_analyze" in self._supportedCommands:
            return "cgos"
        if "kata-genmove_analyze" in self._supportedCommands:
            return "kata"
        if "lz-genmove_analyze" in self._supportedCommands:
            return "lz"
        return None

    def notifyBoardSize(self, size):
        self._sendNoResponseCommand("boardsize " + str(size))

    def notifyKomi(self, komi):
        self._sendNoResponseCommand("komi " + str(komi))

    def notifyClearBoard(self):
        self._sendNoResponseCommand("clear_board")

    def notifyTimeSettings(self, totalTimeMSec):
        if self.hasTimeControl():
            self._sendNoResponseCommand(
                "time_settings " + str(int(totalTimeMSec / 1000)) + " 0 0"
            )

    def notifyTimeLeft(self, gtpColour, timemsec):
        """
        Notify the engine using the 'time_left' command, *if* the engine supports
        it.
        """
        if self.hasTimeControl():
            self._sendNoResponseCommand(
                "time_left " + gtpColour + " " + str(int(timemsec / 1000)) + " 0"
            )

    def notifyPlay(self, gtpColour, gtpCoord):
        """
        Notify the engine using the 'play' command. The colour is a GTP move
        colour and coord a GTP coordinate.
        """
        self._sendNoResponseCommand("play " + gtpColour + " " + gtpCoord)

    def requestGenMove(self, gtpColour) -> Tuple[str, Optional[str]]:
        """
        Request move generation from the engine for a particular colour. The colour
        is in GTP format and the result will be a GTP coordinate (including 'pass' or
        'resign')
        """
        mode = self.getGenmoveAnalyzeMode()
        if mode in ["cgos", "kata", "lz"]:
            if mode == "cgos":
                move, analysis = self.genmoveCgos(gtpColour)
            elif mode == "kata":
                move, analysis = self.genmoveKata(gtpColour)
            elif mode == "lz":
                move, analysis = self.genmoveLz(gtpColour)
            else:
                raise EngineConnectorError("Invalid genmove mode: " + mode)
            if move is None:
                self.logger.error("no move")
                raise Exception("no move")
            self.logger.debug(f"move: {move} analysis: {analysis}")
            return move.lower(), analysis
        else:
            result = self._sendListResponseCommand("genmove " + gtpColour)
            if len(result) == 0:
                raise EngineConnectorError("Received invalid response to genmove")
            return result[0].lower(), None

    def genmoveCgos(self, gtpColour: str) -> Tuple[Optional[str], Optional[str]]:
        result = self._sendListResponseCommand("cgos-genmove_analyze " + gtpColour)
        self.logger.debug("genmove_analyze: " + "#".join(result))
        move: Optional[str] = None
        analysis: Optional[str] = None
        for line in result:
            if line.startswith("play "):
                move = line.split(" ")[-1]
                break
            else:
                analysis = line
        return move, analysis

    def genmoveKata(self, gtpColour: str) -> Tuple[Optional[str], Optional[str]]:
        result = self._sendListResponseCommand("kata-genmove_analyze " + gtpColour + " ownership true")
        self.logger.debug("genmove_analyze: " + "#".join(result))
        move: Optional[str] = None
        analysis: Optional[str] = None
        for line in result:
            if line.startswith("play "):
                move = line.split(" ")[-1]
                break
            else:
                analysis = line
        if analysis is not None:
            tokens = analysis.split(" ")
            info = AnalyzeResultParser(tokens, self.logger, False).parse()
            analysis = json.dumps(info, indent=None, separators=(',', ':'))
        return move, analysis

    def genmoveLz(self, gtpColour: str) -> Tuple[Optional[str], Optional[str]]:
        # Leela Zero doesn't output info unless interval mode
        result = self._sendListResponseCommand("lz-genmove_analyze " + gtpColour + " 100000")
        self.logger.debug("genmove_analyze: " + "#".join(result))
        move: Optional[str] = None
        analysis: Optional[str] = None
        for line in result:
            if line.startswith("play "):
                move = line.split(" ")[-1]
                break
            else:
                analysis = line
        if analysis is not None:
            tokens = analysis.split(" ")
            info = AnalyzeResultParser(tokens, self.logger, True).parse()
            analysis = json.dumps(info, indent=None)
        return move, analysis


    def notifyCGOSOpponentName(self, name):
        """
        Send cgos-opponent_name to engine.
        """
        if "cgos-opponent_name" in self._supportedCommands:
            self._sendNoResponseCommand("cgos-opponent_name " + name)

    def notifyCGOSOpponentRating(self, rating):
        """
        Send cgos-opponent_rating to engine.
        """
        if "cgos-opponent_rating" in self._supportedCommands:
            self._sendNoResponseCommand("cgos-opponent_rating " + rating)

    def notifyCGOSGameover(self, result):
        """
        Sent cgos-gameover to engine. The calling function must format this
        into B+x.y, B+Resign, B+Time or B+Forfeit to make it SGF compliant.
        """
        if "cgos-gameover" in self._supportedCommands:
            self._sendNoResponseCommand("cgos-gameover " + result)

    def _findSupportedCommands(self, mandatoryCommands):
        """
        Fill the _supportedCommands list with GTP commands. All commands in
        'mandatoryCommands' must be present or an exception is thrown.
        """
        self._supportedCommands = self._sendListResponseCommand("list_commands")

        for cmd in mandatoryCommands:
            if not (cmd in self._supportedCommands):
                raise EngineConnectorError(
                    "Mandatory GTP command not implemented: " + cmd
                )

    def _sendNoResponseCommand(self, commandString):
        """
        Send a GTP command to the engine. The command must be one that requires only a
        success / failure response and no output.

        If the engine returns an error, EngineConnectorError is raised.
        """
        self._sendRawGTPCommand(commandString)

    def _sendListResponseCommand(self, commandString):
        """
        Send a GTP command to the engine. The command must be one that requires only a
        line-separated list as a response. The lines are returned as an array, with
        whitespace stripped.

        If the engine returns an error, EngineConnectorError is raised.
        """
        return self._sendRawGTPCommand(commandString)

    def _sendRawGTPCommand(self, commandString):
        """
        Send a GTP command to the engine and return everything up to the next blank
        line as the response. If the response is malformed, EngineConnectorError is raised.

        Don't call this even within this class. Use the other send methods for specific
        command types (list response, etc.)
        """
        if self._subprocess.poll() is not None:
            raise EngineConnectorError("Cannot send GTP command. Engine has terminated")

        self.logger.debug("Sending: " + commandString)
        self._subprocess.stdin.write(commandString + "\n")
        self._subprocess.stdin.flush()

        response = []
        error = None

        while True:
            line = self._subprocess.stdout.readline()

            if len(line.strip()) == 0:
                break

            if line[0] == "=":
                line = line[1:]
            elif line[0] == "?":
                error = line[1:].strip()

            line = line.strip()
            if len(line) > 0:
                response.append(line)

        self.logger.debug("Response: " + str(response))

        if error is not None:
            raise EngineConnectorError("GTP command rejected: " + error)

        return response
