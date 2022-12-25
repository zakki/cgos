"""
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
"""

from common import Colour
import traceback
import sys


class SGFMove(object):
    def __init__(self, coord, colour, timeleft=None):
        """
        Create a move. coord is a tuple (x,y) between (1,1) and the board
        size. Colour is a constant from the common.Colour class.
        """
        self._coord = coord
        self._colour = colour
        self._timeleft = timeleft

    @staticmethod
    def getPassMove(colour, timeleft=None):
        return SGFMove((0, 0), colour, timeleft)

    def isPass(self):
        return self._coord == (0, 0)

    def x(self):
        (x, y) = self._coord
        return x

    def y(self):
        (x, y) = self._coord
        return y

    def colour(self):
        return self._colour

    def timeleft(self):
        return self._timeleft


class SGFGame(object):
    """SGF move coordinate letters for x/y axis"""

    __COORD_LETTERS = "abcdefghijklmnopqrstuvwxyz"

    def __init__(self, boardsize, komi):
        self._boardsize = int(boardsize)
        self._komi = komi
        self._moves = []
        self._white = ""
        self._black = ""
        self._whiteRank = None
        self._blackRank = None
        self._time = 0
        self._result = None

    def addMove(self, move):
        self._moves.append(move)

    def getBlack(self):
        return self._black

    def setBlack(self, black):
        self._black = black

    def setBlackRank(self, rank):
        self._blackRank = rank

    def setWhite(self, white):
        self._white = white

    def getWhite(self):
        return self._white

    def setWhiteRank(self, rank):
        self._whiteRank = rank

    def setMainTimeLimit(self, timeSeconds):
        self._time = timeSeconds

    def setScore(self, winColour, score):
        """
        Set a numeric score. winColour must be a constant from the Colour class.
        score must be a floating point number or integer.
        """
        self._result = self._sgfColour(winColour) + "+" + str(score)

    def setScoreResign(self, winColour):
        """
        Set a resignation score. winColour is the player who win, a constant
        from the Colour class.
        """
        self._result = self._sgfColour(winColour) + "+Resign"

    def setScoreForfeit(self, winColour):
        """
        Set a forfeit score. winColour is a constant from the Colour class.
        """
        self._result = self._sgfColour(winColour) + "+Forfeit"

    def setScoreTimeWin(self, winColour):
        """
        Set a win by time. winColour is a constant from the Colour class.
        """
        self._result = self._sgfColour(winColour) + "+Time"

    def _sgfColour(self, colour):
        """Convert a colour constant to an SGF colour"""
        return {Colour.WHITE: "W", Colour.BLACK: "B"}[colour]

    def save(self, fileName):
        file = open(fileName, "w")

        file.write("(\n")
        file.write(";GM[1]FF[3]AP[cgos-python]\n")
        file.write(
            "RU[NZ]SZ[" + str(self._boardsize) + "]HA[0]KM[" + str(self._komi) + "]\n"
        )
        file.write("PW[" + self._white + "]\n")
        file.write("PB[" + self._black + "]\n")
        file.write("TM[" + str(self._time) + "]\n")

        if self._blackRank is not None and self._whiteRank is not None:
            file.write(
                "GN["
                + self._black
                + " ("
                + self._blackRank
                + ") vs. "
                + self._white
                + " ("
                + self._whiteRank
                + ")]\n"
            )

        if self._result is not None:
            file.write("RE[" + self._result + "]\n")

        if len(self._moves) > 0:
            file.write("(\n")

            for move in self._moves:
                sgfColour = self._sgfColour(move.colour())

                if move.isPass():
                    file.write(";" + sgfColour + "[]")
                else:
                    sgfCoord = (
                        SGFGame.__COORD_LETTERS[move.x() - 1]
                        + SGFGame.__COORD_LETTERS[self._boardsize - move.y()]
                    )
                    file.write(";" + sgfColour + "[" + sgfCoord + "]")

                if move.timeleft() is not None:
                    file.write(sgfColour + "L[" + str(move.timeleft()) + "]")

            file.write(")\n")

        file.write(")\n")

        file.flush()
        file.close()


def main():
    game = SGFGame(19, 6.5)
    game.setBlack("foo")
    game.setBlackRank("1800?")
    game.setWhite("bar")
    game.setWhiteRank("1400?")
    game.setMainTimeLimit(500)
    game.addMove(SGFMove((5, 5), Colour.BLACK, 300))
    game.addMove(SGFMove.getPassMove(Colour.WHITE, 200))
    game.setScoreTimeWin(Colour.BLACK)
    game.save("test.sgf")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        traceback.print_exc(file=sys.stderr)
