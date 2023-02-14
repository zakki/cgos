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

import configparser
import datetime
import sys
import time
import os
import sqlite3
import random
import re
import traceback
import logging
import json
import io
from typing import Any, List, Tuple, Dict, Optional

from sgfmill import sgf


class Colour(object):
    EMPTY = 0
    BLACK = 1
    WHITE = 2

class GTPTools(object):
    """
    Static utilities for converting GTP colours and coordinates to canonical representations.
    """

    __LEGAL_COORDINATES = "abcdefghjklmnopqrstuvwxyz"

    # @staticmethod
    # def convertConstantToColour(constant):
    #     """Convert a constant from the Colour class to a GTP colour"""
    #     return {Colour.WHITE: "W", Colour.BLACK: "B"}[constant]

    # @staticmethod
    # def convertXYToCoordinate(self, xy):
    #     """Convert an (x,y) tuple to a GTP board coordinate."""
    #     (x, y) = xy
    #     return GTPTools.__LEGAL_COORDINATES[x - 1]

    # @staticmethod
    # def convertColourToConstant(colourstr):
    #     """Convert a GTP coordinate to a constant from the Colour class"""
    #     try:
    #         colourstr = colourstr.lower()
    #         const = {
    #             "w": Colour.WHITE,
    #             "white": Colour.WHITE,
    #             "b": Colour.BLACK,
    #             "black": Colour.BLACK,
    #         }[colourstr]
    #         return const
    #     except KeyError:
    #         raise EngineConnectorError("Invalid GTP player colour: '" + colourstr + "'")

    @staticmethod
    def convertCoordinateToXY(coordstr):
        """Convert a GTP board coordinate to an (x,y) tuple"""
        try:
            column = GTPTools.__LEGAL_COORDINATES.index(coordstr[0].lower()) + 1
            row = int(coordstr[1:])
            return (column, row)
        except ValueError as IndexError:
            raise Exception("Invalid coordinate: '" + coordstr + "'")


def sgfToProto(path: str):

    def convert_analysis(dst: cgos_pb2.Analysis, src: Dict):
        if "winrate" in src:
            dst.winratei = int(src["winrate"] * 10000)
        if "score" in src:
            dst.scorei = int(src["score"] * 100)
        if "visits" in src:
            dst.visits = src["visits"]
        if "ownership" in src:
            dst.ownership = bytes(src["ownership"], encoding="ascii")
        if "moves" in src:
            for smove in src["moves"]:
                move = dst.moves.add()
                if "move" in smove:
                    pos = GTPTools.convertCoordinateToXY(smove["move"])
                    # move.move.x = pos[0]
                    # move.move.y = pos[1]
                    # move.move.pos = pos[0] + pos[1] * boardsize
                    move.move_pos = pos[0] + pos[1] * boardsize
                if "winrate" in smove:
                    move.winratei = int(smove["winrate"] * 10000)
                if "score" in smove:
                    move.scorei = int (smove["score"] * 100)
                if "prior" in smove:
                    move.priori = int (smove["prior"] * 10000)
                if "visits" in smove:
                    move.visits = smove["visits"]

                if "pv" in smove:
                    pv = smove["pv"].split(" ")
                    for m in pv:
                        pos = GTPTools.convertCoordinateToXY(m)
                        # p = move.pv_pos.add()
                        # p.x = pos[0]
                        # p.y = pos[1]
                        # p.pos = pos[0] + pos[1] * boardsize
                        move.pv_pos.append(pos[0] + pos[1] * boardsize)

    with open(path, "rb") as f:
        sg = sgf.Sgf_game.from_bytes(f.read())
        print(sg)
        game = cgos_pb2.Game()
        game.version = 1

        sg.get_handicap()
        root = sg.get_root()

        boardsize = sg.get_size()
        game.rule = root.get("RU")
        game.time = root.get("DT")
        game.boardsize = boardsize
        game.komi = sg.get_komi()
        game.white_name = root.get("PW")
        game.white_rate = float(root.get("WR"))
        game.black_name = root.get("PB")
        game.black_rate = float(root.get("BR"))
        game.level = int(root.get("TM"))
        game.result = root.get("RE")
        print(game)
        for i, node in enumerate(sg.get_main_sequence()):
            print(i, node, node.get_move())
            if i == 0:
                continue
            c, m = node.get_move()
            print(c, m)
            move = game.moves.add()
            if c == "b":
                move.color = cgos_pb2.BLACK
                move.time_left = int(node.get("BL"))
            elif c == "w":
                move.color = cgos_pb2.WHITE
                move.time_left = int(node.get("WL"))
            else:
                raise Exception("unknown " + c)
            # move.position.x = m[0]
            # move.position.y = m[1]
            move.pos = m[0] + m[1] * boardsize
            cc = node.get("CC")
            if cc:
                analysis = json.loads(cc)
                convert_analysis(move.analysis, analysis)

    return game

if __name__ == "__main__":
    import cgos_pb2

    if len(sys.argv) != 2:
        print("Must specify a sgf file.")
    game = sgfToProto(sys.argv[1])

    # print("game")
    print(game)
    
    with open(os.path.splitext(sys.argv[1])[0] + ".pb", "wb") as f:
        f.write(game.SerializeToString())
