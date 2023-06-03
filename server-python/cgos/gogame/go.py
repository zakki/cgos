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

from __future__ import annotations

from enum import Enum
import re
from typing import List, Dict


RE_MOVE = re.compile(r"^[a-z]\d+")


class KoRule(Enum):
    SIMPLE = 0
    POSITIONAL = 1


class Rule:
    koRule: KoRule

    def __init__(self, koRule: KoRule) -> None:
        self.koRule = koRule


class GoGame:

    __LEGAL_COORDINATES = "abcdefghjklmnopqrstuvwxyz"

    ctm: int  # where in the game we are
    bd: List[int]
    size: int
    size1: int
    his: Dict[int, List[int]]  # a list of board copies
    moves: List[str]  # a list of moves
    dir: List[int]  # the 4 possible directions
    rule: Rule

    def __init__(self, size: int, rule: Rule) -> None:
        self.bd = []
        self.ctm = 0
        self.size = size
        self.size1 = size + 1
        self.dir = [-1, 1, self.size1, -1 * self.size1]
        self.moves = []
        self.his = dict()
        self.rule = rule

        for y in range(self.size + 2):
            for x in range(self.size1):
                if y < 1 or y > self.size or x == 0:
                    self.bd.append(3)
                else:
                    self.bd.append(0)
        self.his[self.ctm] = self.bd.copy()

    def mvToIndex(self, mv: str) -> int:
        m = mv.lower()

        if m[0:2] == "pa":
            return 0

        match = re.search(RE_MOVE, m)
        if match is not None:
            y = self.size1 - int(m[1:])  # [string range $m 1 2]]
            if y > self.size or y <= 0:
                return -4
            try:
                x = self.__LEGAL_COORDINATES.index(m[0:1]) + 1
                if x > self.size:
                    return -4
            except ValueError:
                return -4
        else:
            # puts "Sorry"
            return -4

        return y * self.size1 + x  # index of point on board

    # return a list of captured stones
    # --------------------------------
    def capture_group(self, target: int) -> List[int]:
        tbd = self.bd.copy()  # copy of board for restoration if needed
        lst = [target]
        est = self.bd[target]  # enemy (color of group to be captured)
        ret = [target]  # list of stones to return
        # flag($target) = 1
        flag = {target: 1}

        while True:
            nlst = []  # build a new list
            for ix in lst:
                for d in self.dir:
                    p = d + ix

                    if self.bd[p] == 0:
                        self.bd = tbd
                        return []  # nothing captured nothing gained

                    if self.bd[p] == est:
                        if p not in flag:
                            nlst.append(p)
                            ret.append(p)  # list of stones to be captured
                            flag[p] = 1

            if len(nlst) == 0:
                for ix in ret:
                    # set bd [lreplace $bd $ix $ix 0]
                    self.bd[ix] = 0
                return ret
            else:
                lst = nlst

    def colorToMove(self) -> int:
        return self.ctm

    # return a "board" with correct status
    # ------------------------------------
    def score_board(self, dead_list: List[str]) -> List[int]:
        b = self.bd.copy()  # work from a copy

        # kill the dead stones
        # --------------------------------
        for s in dead_list:
            imv = self.mvToIndex(s)
            b[imv] = 0

        for x in range(1, self.size1):
            for y in range(1, self.size1):
                i = y * self.size1 + x

                if b[i] == 0:  # empty square and hasn't been covered yet
                    lst = [i]
                    cc = 0  # color of surrounding stones
                    flag = {i: 1}

                    while True:
                        nlst = []
                        # build a new list
                        for ix in lst:
                            for d in self.dir:
                                p = d + ix

                                if b[p] == 0 and p not in flag:
                                    nlst.append(p)
                                    flag[p] = 1
                                elif b[p] == 1:
                                    cc = cc | 1
                                elif b[p] == 2:
                                    cc = cc | 2

                        if len(nlst) == 0:
                            if cc == 1 or cc == 2:
                                for ix in flag.keys():
                                    b[ix] = cc
                            del flag
                            break
                        else:
                            lst = nlst
        return b

    #  make -
    #
    #   Return: -4  if str_move formatted wrong
    #   Return: -3  move to occupied square
    #   Return: -2  Positional super KO move
    #   Return: -1  suicide
    #   Return   0  non capture move
    #   Return  >0  number of stones captured
    #   --------------------------------------
    def make(self, mov: str) -> int:

        mv = mov.upper()
        fst = 2 - (self.ctm & 1)  # friendly stone color
        est = fst ^ 3  # enemy stone color

        if mv[0:2] == "PA":
            self.moves.append("PASS")
            self.ctm += 1
            self.his[self.ctm] = self.bd.copy()
            return 0

        ix = self.mvToIndex(mv)

        # set ix [expr $y * $n1 + $x]   ;# index of point on board
        if ix < 0:
            return ix

        if self.bd[ix] != 0:
            return -3  # move to occupied square

        self.bd[ix] = fst

        # determine if a capture was made in one or more directions
        # ---------------------------------------------------------
        clist = []
        for d in self.dir:
            p = d + ix
            if self.bd[p] == est:
                clist.extend(self.capture_group(p))

        # is the move suicidal?
        # ---------------------
        if len(clist) == 0:  # move was not a capture!
            if len(self.capture_group(ix)) > 0:
                self.bd = self.his[self.ctm].copy()
                return -1

        # test for KO
        # ------------
        if self.rule.koRule == KoRule.POSITIONAL:
            for i in range(self.ctm):
                if self.his[i] == self.bd:
                    self.bd = self.his[self.ctm].copy()
                    return -2  # KO move
        if self.rule.koRule == KoRule.SIMPLE:
            if self.ctm > 0:
                if self.his[self.ctm - 1] == self.bd:
                    self.bd = self.his[self.ctm].copy()
                    return -2  # KO move

        # ok, the move was apparently valid!  accept it.
        # ----------------------------------------------
        self.moves.append(mv)
        self.ctm += 1
        self.his[self.ctm] = self.bd.copy()
        return len(clist)

    def unmake(self) -> bool:
        if self.ctm > 0:
            self.ctm -= 1
            self.bd = self.his[self.ctm].copy()
            return True
        else:
            return False

    def twopass(self) -> bool:
        if self.ctm > 1:
            if (
                self.moves[self.ctm - 1] == "PASS"
                and self.moves[self.ctm - 2] == "PASS"
            ):
                return True
            else:
                return False
        else:
            return False

    def list_moves(self) -> List[str]:
        all = []

        for ix in range(self.ctm):
            all.append(self.moves[ix])

        return all

    def displayAll(self) -> None:
        for y in range(self.size + 2):
            print()
            for x in range(self.size1):
                ix = y * self.size1 + x
                print("%3d" % (self.bd[ix]), end="")
        print()

    def display(self, pretty=True) -> None:
        print(self.to_string(pretty))

    def to_string(self, pretty=True) -> str:
        out = ""
        for y in range(1, self.size + 1):
            for x in range(1, self.size + 1):
                ix = y * self.size1 + x
                p = self.bd[ix]
                if pretty:
                    if p == 0:
                        out += "."
                    elif p == 1:
                        out += "O"
                    elif p == 2:
                        out += "X"
                    elif p == 3:
                        out += "#"
                else:
                    out += "%3d" % (self.bd[ix])
            out += "\n"
        return out

    @staticmethod
    def from_string(board: str, rule: Rule) -> GoGame:
        lines = board.upper().splitlines()
        sy = len(lines)
        sx = len(lines[0])
        if sx != sy:
            raise ValueError(f"non rectangle board {sx}x{sy}")
        if any([sx != len(line) for line in lines]):
            raise ValueError("unique size")

        game = GoGame(sx, rule)
        for y, line in enumerate(lines, start=1):
            for x, p in enumerate(line, start=1):
                ix = y * game.size1 + x
                v = None
                if p == ".":
                    v = 0
                elif p == "O":
                    v = 1
                elif p == "X":
                    v = 2
                else:
                    raise ValueError(f"unexpected character {p} at {x} {y}")
                game.bd[ix] = v

        game.his[game.ctm] = game.bd.copy()

        return game

    # return a copy of the current board as a tcl list
    # ------------------------------------------------
    def getboard(self) -> List[int]:
        board = []
        for y in range(1, self.size + 1):
            for x in range(1, self.size + 1):
                ix = y * self.size1 + x
                board.append(self.bd[ix])
        return board

    # return a copy of the current board as a tcl list
    # ------------------------------------------------
    def getFinalBoard(self, dead: List[str]) -> List[int]:
        b = self.score_board(dead)
        board = []
        for y in range(1, self.size + 1):
            for x in range(1, self.size + 1):
                ix = y * self.size1 + x
                board.append(b[ix])
        return board

    # tromp/taylor chinese style scoring
    # ----------------------------------
    def ttScore(self) -> int:
        tbd = self.getFinalBoard([])
        score = 0
        for j in tbd:
            if j == 2:
                score += 1
            elif j == 1:
                score -= 1
        return score
