"""
Copyright for initial code (C) 2009 Christian Nentwich. See contributors
file.

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

import socket
import sys
import traceback
import time
import logging
import logging.handlers
import os
import os.path
import string
import random
from typing import Optional

from gtpengine import EngineConnector, EngineConnectorError, GTPTools
from sgf import SGFGame, SGFMove
from config import ConfigFile, ConfigSection


ENCODING = "utf-8"

class CGOSClientError(Exception):
    def __init__(self, msg):
        self._msg = msg

    def __str__(self):
        return repr(self._msg)


class CGOSClient(object):
    """
    Main CGOS client class. This requires an initialized and connected engine as
    a parameter. It will then connect to CGOS and play until it finds a kill file
    in place.

    This class uses reflection to implement CGOS command. The "_handle_" methods
    are followed by CGOS command name.

    See _handlerloop for the command dispatcher, mainloop for the reconnect/play loop.
    """

    CLIENT_ID = "e1 cgosPython 0.3.1 beta"

    __TIME_CHECKPOINT_FREQUENCY = 60 * 30
    """ How often to output stats, etc., in seconds """

    def __init__(self, engineConfigurationSections: ConfigSection,
                 killFileName: str = "kill.txt",
                 logFileName: Optional[str] = None):
        """
        Initialise the client, without connecting anything yet
          - engineConfigurationSections is a list of ConfigSection objects containing
            engine parameters. An engine will be chosen from there.
          - killFileName is the file to look for when deciding whether to shut down
        """
        self._engineConfigs = engineConfigurationSections
        self._engine = None  # Currently playing engine
        self._currentEngineIndex = (
            -1
        )  # Index in configuration sections of current engine
        self._currentEngineGamesLeft = (
            0  # Number of games the current engine has left before switching
        )

        self._killFileName = killFileName  # File that will trigger shutdown

        self._finished = False  # Should the main loop quit
        self._engineSwitching = (
            False  # Should the handler loop quit to allow an engine switch
        )

        self._socketfile = None

        self._server = None  # Server host name (engine dependent)
        self._port = None  # Server port (engine dependent)
        self._username = None  # User name (engine dependent)
        self._password = None  # Password (engine dependent)

        self._gameInProgress = False  # Currently between setup and gameover?
        self._engineColour = (
            "black"  # Which colour is the local engine playing in a game?
        )

        self._wonGames = (
            0  # Stats about how many games were won/lost during this session
        )
        self._lostGames = 0

        self._timeStarted = time.localtime()  # Will not change
        self._timeCheckPoint = (
            time.localtime()
        )  # Last time checkpoint for outputting stats, mail, etc.

        self._observer = None  # GTP observer, if any - already connected
        self._sgfDirectory = None  # Directory to store SGF. Leave None to disable.

        # movecount is only used for periodically outputting information messages
        self._movecount = 0

        self._useAnalyze = False

        self.logger = logging.getLogger("cgosclient.CGOSClient")
        self.logger.setLevel(logging.DEBUG)

        # Logger
        formatter = logging.Formatter("%(asctime)s - %(levelname)s: %(message)s")
        handler: logging.Handler

        # Log debug output to file
        if logFileName is not None:
            os.makedirs(os.path.dirname(logFileName), exist_ok=True)
            handler = logging.FileHandler(logFileName)
            handler.setLevel(logging.DEBUG)

            handler.setFormatter(formatter)

            self.logger.addHandler(handler)

        # Log info output to console
        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(logging.INFO)

        formatter = logging.Formatter("%(asctime)s: %(message)s")
        handler.setFormatter(formatter)

        self.logger.addHandler(handler)

    def connect(self):
        self.logger.info(
            "Attempting to connect to server '"
            + self._server
            + "', port "
            + str(self._port)
        )

        self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

        try:
            self._socket.connect((self._server, self._port))
        except Exception as e:
            self.logger.error("Connection failed: " + str(e))
            raise CGOSClientError("Connection failed: " + str(e))

        self._socketfile = self._socket.makefile("rw", encoding=ENCODING)
        self._finished = False

        self.logger.info("Connected")

    def disconnect(self):
        self.logger.info("Disconnecting")
        if self._socketfile is not None:
            self._socketfile.close()
            self._socket.close()

    #    def _chooseEngineIndexAtRandom(self):
    #        '''
    #        Pick an engine from the configuration file at random, given the weights of
    #        all engines.
    #        '''
    #        if len(self._engineConfigs) == 1: return 0
    #
    #        # Normalise weights to [0.0, 1.0]
    #        priorities = map(lambda x : int(x.getValue("Priority")), self._engineConfigs)
    #        totalPriorities = reduce(lambda x,y: x+y, priorities)
    #
    #        normalisedPriorities = map(lambda x : float(x)/totalPriorities, priorities)
    #
    #        chosenEngineIndex = 0
    #        cumulativeSum = 0.0
    #        randomIndex = random.random()
    #
    #        for idx in xrange(len(normalisedPriorities)):
    #            if randomIndex > cumulativeSum and randomIndex <= cumulativeSum + normalisedPriorities[idx]:
    #                chosenEngineIndex = idx
    #                break
    #            cumulativeSum += normalisedPriorities[idx]
    #
    #        return chosenEngineIndex

    def _respond(self, message):
        if self._socket is not None:
            self.logger.debug("Responding: " + message)
            self._socketfile.write(message + "\n")
            self._socketfile.flush()

    def _handle_info(self, parameters):
        """Event handler: "info". Ignored."""
        self.logger.info("Server info: " + (" ".join(parameters)))
        self._checkTimeCheckpoint()

    def _handle_protocol(self, parameters):
        """Event handler: "protocol" command. No parameters."""
        self._useAnalyze = "genmove_analyze" in parameters
        if self._useAnalyze:
            self._respond(CGOSClient.CLIENT_ID + " genmove_analyze")
        else:
            self._respond(CGOSClient.CLIENT_ID)


    def _handle_username(self, parameters):
        """Event handler: "username" command. No parameters."""
        self._respond(self._username)

    def _handle_password(self, parameters):
        """Event handler: "password" command. No parameters."""
        self._respond(self._password)

    def _handle_setup(self, parameters):
        """
        Event handler: "setup" command to prepare for game.
        Expects the following parameters:
          - Game id
          - Board size
          - Komi
          - Game time per player in msec
          - Program A name, with optional rating, e.g. "program(1800)"
          - Program B name, with optional rating

        The parameters may be followed by an alternating list of moves/time pairs,
        starting with black, to place on the board.

        Example: setup 1 19 7.5 1800000 programA(1800?) programB(1800?) E5 1700000 H3 1600000
        """
        if len(parameters) < 6:
            raise CGOSClientError("'setup' command requires at least 6 parameters")

        self._gameInProgress = True

        # Parse the parameters, and cut apart the rank and player names
        gameId = parameters[0]
        boardSize = parameters[1]
        komi = parameters[2]
        gameTimeMSec = int(parameters[3])
        programA = parameters[4]
        programB = parameters[5]

        programARank = ""
        programBRank = ""
        if "(" in programA:
            programARank = programA[programA.find("(") : programA.rfind(")")].strip(
                "()"
            )
            programA = programA[: programA.find("(")]
        if "(" in programB:
            programBRank = programB[programB.find("(") : programB.rfind(")")].strip(
                "()"
            )
            programB = programB[: programB.find("(")]

        # Log some information
        opponent = programA
        opponentRank = programARank
        engineRank = programBRank
        self._engineColour = "black"

        if self._username == programA:
            opponent = programB
            opponentRank = programBRank
            engineRank = programARank
            self._engineColour = "white"

        self.logger.info(
            "Starting game against "
            + opponent
            + "("
            + opponentRank
            + '). Local engine ("'
            + self._engine.getName()
            + '", rated '
            + engineRank
            + ") is playing "
            + self._engineColour
            + "."
        )

        if len(parameters) > 6:
            self.logger.info(
                "This is a restart. Catching up "
                + str((len(parameters) - 6) // 2)
                + " moves"
            )

        # Set up the engine through GTP. Also observer, if registered
        self._movecount = 0
        self._engine.notifyBoardSize(boardSize)
        self._engine.notifyKomi(komi)
        self._engine.notifyTimeSettings(gameTimeMSec)
        self._engine.notifyCGOSOpponentName(opponent)
        self._engine.notifyCGOSOpponentRating(opponentRank)
        self._engine.notifyClearBoard()

        if self._observer is not None:
            self._observer.notifyBoardSize(boardSize)
            self._observer.notifyKomi(komi)
            self._observer.notifyClearBoard()

        # SGF
        self._sgfGame = SGFGame(boardSize, komi)
        self._sgfGame.setBlack(programB)
        self._sgfGame.setWhite(programA)
        self._sgfGame.setMainTimeLimit(int(gameTimeMSec / 1000))

        # If there are more than 6 parameters, we need to notify the engine of moves to catch up on
        if len(parameters) > 6:
            colour = "b"

            for i in range(6, len(parameters), 2):
                coord = parameters[i].lower()
                time = parameters[i + 1]

                self._handle_play([colour, coord, time])

                if colour == "b":
                    colour = "w"
                else:
                    colour = "b"

    def _handle_play(self, parameters):
        """
        Event handler: "play" command. Expects:
          - GTP colour
          - GTP coordinate
          - Time left in msec
        """
        if len(parameters) != 3:
            raise CGOSClientError("'play' command requires 3 parameters")

        colour = parameters[0]
        coord = parameters[1].lower()
        timeMSec = int(parameters[2])

        self._engine.notifyPlay(colour, coord)

        if self._observer is not None:
            self._observer.notifyPlay(colour, coord)

        if coord == "pass":
            move = SGFMove.getPassMove(
                GTPTools.convertColourToConstant(colour), int(timeMSec / 1000)
            )
        else:
            move = SGFMove(
                GTPTools.convertCoordinateToXY(coord),
                GTPTools.convertColourToConstant(colour),
                int(timeMSec / 1000),
            )

        self._sgfGame.addMove(move)

    def _handle_genmove(self, parameters):
        """
        Event handler: "genmove". Expects:
          - GTP colour
          - Time left in msec
        """
        if len(parameters) != 2:
            raise CGOSClientError("'play' command requires 2 parameters")

        self._movecount += 1
        if self._movecount % 10 == 0:
            self.logger.info(
                'Engine "'
                + self._engine.getName()
                + '" playing '
                + self._engineColour
                + ". "
                + str(self._movecount)
                + " moves generated. "
                + "Time left: "
                + str(int(parameters[1]) // 1000)
                + " sec"
            )

        colour = parameters[0]
        timeMSec = int(parameters[1])

        self._engine.notifyTimeLeft(colour, timeMSec)
        result, analyzeInfo = self._engine.requestGenMove(colour)
        response = result.lower()
        if self._useAnalyze and analyzeInfo is not None:
            response += " " + analyzeInfo

        self._respond(response)

        # Observer (other than resign)
        if self._observer is not None and result != "resign":
            self._observer.notifyPlay(colour, result)

        # Update SGF (resign move does not get recorded)
        if result == "resign":
            move = None
        elif result == "pass":
            move = SGFMove.getPassMove(
                GTPTools.convertColourToConstant(colour), int(timeMSec / 1000)
            )
        else:
            move = SGFMove(
                GTPTools.convertCoordinateToXY(result),
                GTPTools.convertColourToConstant(colour),
                int(timeMSec / 1000),
            )

        if move is not None:
            self._sgfGame.addMove(move)

    def _handle_gameover(self, parameters):
        """
        Event handler: "gameover". Expects:
          - A date
          - The result (unparsed) e.g. "B+Resign"
        """
        result = parameters[1]
        self.logger.info("Game over. Result: " + result)

        if self._engineColour[0] == result.lower()[0]:
            self.logger.info("Local engine won :-)")
            self._wonGames += 1
        else:
            self.logger.info("Local engine lost :'(")
            self._lostGames += 1

        self._gameInProgress = False

        if "+Resign" in result:
            self._sgfGame.setScoreResign(GTPTools.convertColourToConstant(result[0]))
            self._engine.notifyCGOSGameover(result)
        elif "+Time" in result:
            self._sgfGame.setScoreTimeWin(GTPTools.convertColourToConstant(result[0]))
            self._engine.notifyCGOSGameover(result)
        elif "+Illegal" in result:
            self._sgfGame.setScoreForfeit(GTPTools.convertColourToConstant(result[0]))
            self._engine.notifyCGOSGameover(result[0] + "Forfeit")
        else:
            try:
                score = float(result[2:])
                self._sgfGame.setScore(
                    GTPTools.convertColourToConstant(result[0]), score
                )
            except Exception:
                pass
            self._engine.notifyCGOSGameover(result)

        if self._sgfDirectory is not None:
            fileName = time.strftime("%Y-%m-%d-%H-%M-%S", time.localtime())

            ascii = set(string.ascii_letters).union(set(string.digits))
            ascii.add("-_")

            blackName = "".join(ch for ch in self._sgfGame.getBlack() if ch in ascii)
            whiteName = "".join(ch for ch in self._sgfGame.getWhite() if ch in ascii)

            fileName = fileName + "-" + blackName + "-" + whiteName + ".sgf"
            self.logger.info("Saving SGF file: " + fileName)

            self._sgfGame.save(os.path.join(self._sgfDirectory, fileName))

        # Have to check kill file here too - so we don't tell the server we are ready
        # before quitting
        self._checkKillFile()

        if not (self._finished):
            self.pickNewEngine()
        if not (self._finished) and not (self._engineSwitching):
            self._respond("ready")

        self._checkTimeCheckpoint()

    def _handlerloop(self):
        """
        Read from CGOS socket and dispatch to handlers. This uses reflection on the
        class to handle CGOS commands. Handler methods start with "_handle_" and
        continue with the CGOS command name.

        All handler methods are passed an array of parameters by this loop.

        This loop will exit with an exception if the socket fails or an engine or
        client error occurs. Calling methods will have to handle this.
        """
        while not (self._finished) and not (self._engineSwitching):
            line = self._socketfile.readline()
            if len(line) == 0:
                self.logger.error("Empty response")
                self._finished = True
                return

            line = line.strip()

            self.logger.debug("Server sent: " + line)

            if len(line) == 0:
                self.logger.debug("Empty line received from CGOS server")
                continue

            if line.startswith("Error:"):
                self.logger.error("CGOS Error: " + line[6:])
                self._finished = True
                return

            splitline = line.split(None, 1)

            commandHandler = "_handle_" + splitline[0]

            try:
                handler = getattr(self, commandHandler)
            except AttributeError:
                self.logger.error("Unsupported CGOS command, '" + splitline[0] + "'")
                raise CGOSClientError("Unsupported command: " + splitline[0])
            else:
                parameters = []
                if len(splitline) > 1:
                    parameters = splitline[1].split()

                try:
                    result = handler(parameters)
                except CGOSClientError as e:
                    self.logger.error(str(e))
                    raise

            if not (self._gameInProgress):
                self._checkKillFile()

        if self._engineSwitching:
            self._respond("quit")
            self.disconnect()

    def _checkKillFile(self):
        """
        Check if the kill file exists and set _finished to true if yes.
        """
        self._finished = os.path.exists(self._killFileName)
        if self._finished:
            self.logger.info("Kill file found. Shutting down connection and engines.")

    def _checkTimeCheckpoint(self):
        """
        Check if the last time checkpoint was more than half an hour away, and
        perform maintenance tasks if necessary (information output, etc).

        This should not be called from time-sensitive parts like genmove, but from
        info messages, gameover, etc.
        """
        currentTime = time.mktime(time.localtime())
        duration = currentTime - time.mktime(self._timeCheckPoint)

        if duration > CGOSClient.__TIME_CHECKPOINT_FREQUENCY:
            self._timeCheckPoint = time.localtime()

            duration = currentTime - time.mktime(self._timeStarted)
            self.logger.info(
                "Client up for "
                + str(int(duration) // 3600)
                + " hours, "
                + str((int(duration) // 60) % 60)
                + " mins, "
                + str(int(duration) % 60)
                + " seconds. "
                + "Local engines won "
                + str(self._wonGames)
                + " games, lost "
                + str(self._lostGames)
                + "."
            )

    def isConnected(self):
        return self._server is not None

    def mainloop(self):
        """
        Main loop - keep trying to connect to CGOS, with reasonable wait times. Once connected,
        invoke the handler loop.

        If the engine crashes or something severe happens, the CGOS connection is closed and
        the loop exits. If a kill file is found (see killFileName parameter to constructor),
        an orderly shutdown is performed.
        """
        self._finished = False

        while not (self._finished):
            self._engineSwitching = False

            connected = False
            retries = 1
            while not (connected):
                try:
                    self.connect()
                    connected = True
                except Exception:
                    self.logger.error(
                        "Could not connect to " + self._server + ". Will try again."
                    )
                    time.sleep(30 + int(random.random() * 5))
                    retries += 1

            try:
                self._handlerloop()
            except socket.error as e:
                self.logger.error("Socket error: " + str(e))
                self.disconnect()
            except CGOSClientError as e:
                self.logger.error(str(e))
                return
            except EngineConnectorError as e:
                self.logger.error("GTP engine error: " + str(e))
                return

        self._respond("quit")
        if os.path.exists(self._killFileName):
            os.remove(self._killFileName)

    def pickNewEngine(self):
        """
        Choose a different engine and reconnect. If the engine fails to start,
        this throws an exception
        """

        if self._currentEngineIndex == -1:
            self._currentEngineIndex = 0
        elif len(self._engineConfigs) == 1:
            return
        else:
            self._currentEngineGamesLeft -= 1

            if self._currentEngineGamesLeft > 0:
                return

            self._currentEngineIndex = (self._currentEngineIndex + 1) % len(
                self._engineConfigs
            )

        if self._engine is not None:
            self._engine.shutdown()

        newEngineConfig = self._engineConfigs[self._currentEngineIndex]
        self._currentEngineGamesLeft = int(newEngineConfig.getValue("NumberOfGames"))

        self.logger.info(
            "Chose engine "
            + str(self._currentEngineIndex + 1)
            + ' ("'
            + newEngineConfig.getValue("Name")
            + '") as next player. Switching and re-connecting.'
        )

        try:
            newEngine = EngineConnector(
                newEngineConfig.getValue("CommandLine"),
                newEngineConfig.getValue("Name"),
                logger="EngineConnector" + str(self._currentEngineIndex),
                logfile=newEngineConfig.getValueOpt("LogFile")
            )
            newEngine.connect()
        except Exception as e:
            self.logger.error("Switch failed. Engine failed to start: " + str(e))
            raise

        self._engine = newEngine

        if newEngineConfig.hasValue("SGFDirectory"):
            self._sgfDirectory = newEngineConfig.getValue("SGFDirectory")
        else:
            self._sgfDirectory = None

        self._server = newEngineConfig.getValue("ServerHost")
        self._port = int(newEngineConfig.getValue("ServerPort"))
        self._username = newEngineConfig.getValue("ServerUser")
        self._password = newEngineConfig.getValue("ServerPassword")

        self._engineSwitching = True

    def setObserver(self, engine):
        self._observer = engine

    def setSGFDirectory(self, dir):
        self._sgfDirectory = dir
        self.logger.info("SGF files will be saved in: " + dir)

    def shutdown(self):
        self.logger.info("Shutting down CGOS connection")

        if self._socketfile is not None:
            self._socketfile.close()
            self._socket.close()

        if self._engine is not None:
            self._engine.shutdown()


def main(argv):
    print("Python CGOS client. " + CGOSClient.CLIENT_ID + " (c)2009 Christian Nentwich")
    if len(argv) != 1:
        print("Usage: python cgosclient.py config.cfg")
        return 1

    # Here we go. Grab the configuration file
    config = ConfigFile()
    config.load(argv[0])

    engineConfigs = config.getEngineSections()
    client = CGOSClient(engineConfigs,
                        config.getCommonSection().getValue("KillFile"),
                        config.getCommonSection().getValueOpt("LogFile"))

    # Launch observer (e.g. GoGUI) if any
    observerConfig = config.getObserverSection()
    observerEngine = None

    if observerConfig is not None:
        observerEngine = EngineConnector(
            observerConfig.getValue("CommandLine"),
            "Observer",
            logger="ObserverLogger",
            logfile=observerConfig.getValueOpt("LogFile")
        )
        observerEngine.connect(EngineConnector.MANDATORY_OBSERVE_COMMANDS)
        client.setObserver(observerEngine)

    # And play until done
    try:
        client.pickNewEngine()
        client.mainloop()
    finally:
        client.shutdown()
        if observerEngine is not None:
            observerEngine.shutdown()


if __name__ == "__main__":
    try:
        main(sys.argv[1:])
    except Exception as e:
        traceback.print_exc(file=sys.stderr)
