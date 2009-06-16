'''
Copyright (C) 2009 Christian Nentwich

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
'''

import logging
import logging.handlers
import subprocess
import traceback, sys, time
from common import Colour

class EngineConnectorError(Exception):
    def __init__(self, msg):
        self._msg = msg
    def __str__(self):
        return repr(self._msg)


class GTPTools(object):
    '''
    Static utilities for converting GTP colours and coordinates to canonical representations.
    '''
    
    __LEGAL_COORDINATES = "abcdefghjklmnopqrstuvwxyz";
    
    @staticmethod
    def convertConstantToColour(constant):
        ''' Convert a constant from the Colour class to a GTP colour '''
        return { Colour.WHITE : "W",
                Colour.BLACK : "B"
                }[constant]

    @staticmethod
    def convertXYToCoordinate(self, xy):
        ''' Convert an (x,y) tuple to a GTP board coordinate. '''
        (x,y) = xy
        return GTPTools.__LEGAL_COORDINATES[x-1]

    @staticmethod
    def convertColourToConstant(colourstr):
        ''' Convert a GTP coordinate to a constant from the Colour class '''
        try:
            colourstr = colourstr.lower()
            const = {
                     "w" : Colour.WHITE,
                     "white" : Colour.WHITE,
                     "b" : Colour.BLACK,
                     "black" : Colour.BLACK 
                     }[colourstr]
            return const
        except KeyError:
            raise EngineConnectorError("Invalid GTP player colour: '" + colourstr+ "'")
        
    @staticmethod
    def convertCoordinateToXY(coordstr):
        ''' Convert a GTP board coordinate to an (x,y) tuple '''
        try:
            column = GTPTools.__LEGAL_COORDINATES.index(coordstr[0].lower()) + 1
            row = int(coordstr[1:])
            return (column, row)
        except ValueError, IndexError:
            raise EngineConnectorError("Invalid coordinate: '" + coordstr + "'")
            
    
class EngineConnector(object):
    '''
    EngineConnector is the interface to a GTP engine, whether that engine is creating
    moves or just observing by receiving play commands.
    
    The "notify" methods are used to send commands to the engine and check responses.
    It is safe to give time handling commands to the engine - the connector will only
    issue them if the engine supports it. The "notifyCGOS" methods call cgos GTP extensions.
    
    Call connect() to launch the engine before using it. When done, the engine is given
    a "quit" command and if it fails to respond in time, it is killed using the OS.
    '''
    
    MANDATORY_PLAYING_COMMANDS = ["boardsize", "clear_board", "komi", "play", "genmove", "quit"]
    ''' Mandatory commands for an engine that can play a game. '''
    
    MANDATORY_OBSERVE_COMMANDS = ["boardsize", "clear_board", "komi", "play", "quit"]
    ''' Mandatory commands for an engine that can observe a game (like GoGUI). '''
    
    def __init__(self, programCommandLine, logger="EngineConnector", logfile = "engine.log"):
        self._programCommandLine = programCommandLine
        self._subprocess = None
        self._supportedCommands = []
        
        self.logger = logging.getLogger(logger)
        self.logger.setLevel(logging.DEBUG)
        
        self.handler = logging.FileHandler(logfile)
        self.handler.setLevel(logging.DEBUG)
        
        self.formatter = logging.Formatter("%(asctime)s - %(levelname)s: %(message)s")
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
        ''' 
        Launch the GTP engine as a sub-process. Will throw an EngineConnectorError if
        this fails. This will also use GTP list_commands to check the capabilities of the
        engine. 
        '''
        self.logger.info("Starting GTP engine, command line: " + self._programCommandLine)
        self._subprocess = subprocess.Popen(self._programCommandLine, stdin=subprocess.PIPE,
                                            stdout=subprocess.PIPE, shell=False)
        time.sleep(1)
        self._findSupportedCommands(mandatoryCommands)
    
    def shutdown(self):
        '''
        Shut down the GTP engine using the 'quit' command, or kill it if it does not
        support that or takes too long.
        '''
        if self._subprocess != None and self._subprocess.poll() == None:
            self.logger.info("Shutting down GTP engine, command line: " + self._programCommandLine)
            self._sendNoResponseCommand("quit")

            for i in range(5):
                time.sleep(0.5)
                if self._subprocess.poll() == None:
                    self.logger.info("Sending terminate")
                    self._subprocess.terminate()
                    break
                
            self._subprocess = None
    
    def hasTimeControl(self):
        '''
        Return true if the engine supports time management.
        '''
        return "time_left" in self._supportedCommands and "time_settings" in self._supportedCommands
    
    def notifyBoardSize(self, size):
        self._sendNoResponseCommand("boardsize " + str(size))
        
    def notifyKomi(self, komi):
        self._sendNoResponseCommand("komi " + str(komi))
        
    def notifyClearBoard(self):
        self._sendNoResponseCommand("clear_board")
        
    def notifyTimeSettings(self, totalTimeMSec):
        if self.hasTimeControl():
            self._sendNoResponseCommand("time_settings " + str(int(totalTimeMSec / 1000)) + " 0 0")
            
    def notifyTimeLeft(self, gtpColour, timemsec):
        '''
        Notify the engine using the 'time_left' command, *if* the engine supports 
        it.
        '''
        if self.hasTimeControl():
            self._sendNoResponseCommand("time_left " + gtpColour + " " + str(int(timemsec / 1000)) + " 0")
            
    def notifyPlay(self, gtpColour, gtpCoord):
        ''' 
        Notify the engine using the 'play' command. The colour is a GTP move
        colour and coord a GTP coordinate. 
        '''
        self._sendNoResponseCommand("play " + gtpColour + " " + gtpCoord)
   
    def requestGenMove(self, gtpColour):
        '''
        Request move generation from the engine for a particular colour. The colour
        is in GTP format and the result will be a GTP coordinate (including 'pass' or
        'resign')
        '''
        result = self._sendListResponseCommand("genmove " + gtpColour)
        if len(result) == 0:
            raise EngineConnectorError("Received invalid response to genmove")
        return result[0]
    
    def notifyCGOSOpponentName(self, name):
        '''
        Send cgos-opponent_name to engine.
        '''
        if "cgos-opponent_name" in self._supportedCommands:
            self._sendNoResponseCommand("cgos-opponent_name " + name)
            
    def notifyCGOSGameover(self, result):
        '''
        Sent cgos-game_over to engine. The calling function must format this
        into B+x.y, B+Resign, B+Time or B+Forfeit to make it SGF compliant.
        '''
        if "cgos-gameover" in self._supportedCommands:
            self._sendNoResponseCommand("cgos-gameover " + result)
            
    def _findSupportedCommands(self, mandatoryCommands):
        '''
        Fill the _supportedCommands list with GTP commands. All commands in
        'mandatoryCommands' must be present or an exception is thrown.
        '''
        self._supportedCommands = self._sendListResponseCommand("list_commands")
        
        for cmd in mandatoryCommands:
            if not(cmd in self._supportedCommands):
                raise EngineConnectorError("Mandatory GTP command not implemented: " + cmd) 
        
    def _sendNoResponseCommand(self, commandString):
        '''
        Send a GTP command to the engine. The command must be one that requires only a 
        success / failure response and no output.
        
        If the engine returns an error, EngineConnectorError is raised.
        '''
        self._sendRawGTPCommand(commandString)
        
    def _sendListResponseCommand(self, commandString):
        '''
        Send a GTP command to the engine. The command must be one that requires only a 
        line-separated list as a response. The lines are returned as an array, with
        whitespace stripped.
        
        If the engine returns an error, EngineConnectorError is raised.
        '''
        return self._sendRawGTPCommand(commandString)

    def _sendRawGTPCommand(self, commandString):
        '''
        Send a GTP command to the engine and return everything up to the next blank
        line as the response. If the response is malformed, EngineConnectorError is raised.
        
        Don't call this even within this class. Use the other send methods for specific 
        command types (list response, etc.)
        '''
        if self._subprocess.poll() != None:
            raise EngineConnectorError("Cannot send GTP command. Engine has terminated")

        self.logger.debug("Sending: " + commandString)
        self._subprocess.stdin.write(commandString + "\n")
        
        response = []
        error = None
        
        while True:
            line = self._subprocess.stdout.readline()
            
            if len(line.strip()) == 0:
                break
            
            if line[0] == '=':
                line = line[1:]
            elif line[0] == '?':
                error = line[1:].strip()

            line = line.strip()
            if len(line) > 0: response.append(line)
            
        self.logger.debug("Response: " + str(response))
        
        if error != None:
            raise EngineConnectorError("GTP command rejected: " + error)
        
        return response
        