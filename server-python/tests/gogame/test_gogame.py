# The MIT License
#
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

import textwrap
from unittest import TestCase

from gogame import GoGame, Rule, KoRule


class TestGoGame(TestCase):

    def test_simplegame(self):
        board = GoGame(9, Rule(KoRule.POSITIONAL))
        self.assertEqual(board.make("C3"), 0)
        self.assertEqual(board.make("d3"), 0)
        self.assertEqual(board.make("D4"), 0)
        self.assertEqual(board.make("C4"), 0)
        self.assertEqual(board.make("B4"), 0)
        self.assertEqual(board.make("B3"), 0)
        self.assertEqual(board.make("C5"), 1)
        self.assertEqual(board.make("C2"), 0)
        self.assertEqual(board.make("PASS"), 0)
        self.assertEqual(board.make("C1"), 0)
        self.assertEqual(board.make("PASS"), 0)
        self.assertEqual(board.make("A4"), 0)
        self.assertFalse(board.twopass())
        self.assertEqual(board.make("PASS"), 0)
        self.assertFalse(board.twopass())
        self.assertEqual(board.make("PASS"), 0)
        self.assertTrue(board.twopass())

    def test_move_wrongformat(self):
        board = GoGame(9, Rule(KoRule.POSITIONAL))
        self.assertEqual(board.make("2C3"), -4)
        self.assertEqual(board.make(""), -4)
        self.assertEqual(board.make("I1"), -4)

        self.assertEqual(board.make("C0"), -4)
        self.assertEqual(board.make("C1"), 0)
        self.assertEqual(board.make("C9"), 0)
        self.assertEqual(board.make("C10"), -4)
        self.assertEqual(board.make("J1"), 0)
        self.assertEqual(board.make("K1"), -4)
        self.assertEqual(board.make("M1"), -4)

    def test_move_occupied(self):
        board = GoGame(9, Rule(KoRule.POSITIONAL))
        self.assertEqual(board.make("C3"), 0)
        self.assertEqual(board.make("C3"), -3)

    def test_move_suicide(self):
        board = GoGame(9, Rule(KoRule.POSITIONAL))
        self.assertEqual(board.make("A2"), 0)
        self.assertEqual(board.make("C3"), 0)
        self.assertEqual(board.make("B1"), 0)
        self.assertEqual(board.make("A1"), -1)

    def test_print(self):
        board = GoGame(5, Rule(KoRule.POSITIONAL))
        board.make("C3")
        board.make("d3")
        board.make("D4")
        board.make("C4")
        self.assertEqual(board.to_string(),
                         textwrap.dedent("""\
                         .....
                         ..OX.
                         ..XO.
                         .....
                         .....
                         """))
        board.make("B4")
        board.make("B3")
        board.make("C5")
        board.make("C2")
        self.assertEqual(board.to_string(),
                         textwrap.dedent("""\
                         ..X..
                         .X.X.
                         .OXO.
                         ..O..
                         .....
                         """))
        board.make("A5")
        board.make("C1")
        board.make("D2")
        board.make("A4")
        board.make("D1")

        self.assertEqual(board.to_string(),
                         textwrap.dedent("""\
                         X.X..
                         OX.X.
                         .OXO.
                         ..OX.
                         ..OX.
                         """))

    def test_from_string(self):
        board = GoGame.from_string(
            textwrap.dedent("""\
                            O.O..
                            XO.O.
                            .XOX.
                            ..XO.
                            ..XO.
                            """),
            Rule(KoRule.POSITIONAL))
        self.assertEqual(board.size, 5)

        self.assertEqual(board.to_string(),
                         textwrap.dedent("""\
                         O.O..
                         XO.O.
                         .XOX.
                         ..XO.
                         ..XO.
                         """))

    def test_positional_ko(self):
        BOARD = textwrap.dedent("""\
            .o.xxo
            oxxxo.
            o.x.oo
            xx.oo.
            oooo.o
            oooooo
            """)
        board = GoGame.from_string(BOARD, Rule(KoRule.POSITIONAL))
        # print(); board.display()

        self.assertEqual(board.make("F5"), 1)
        # print(); board.display(); print("KO F6")
        self.assertEqual(board.make("F6"), -2)
        self.assertEqual(board.make("PASS"), 0)
        self.assertEqual(board.make("D4"), 0)

        # print(); board.display()

        self.assertEqual(board.make("C6"), 0)
        # print(); board.display()

        self.assertEqual(board.make("A6"), 2)

        # print(); board.display(); print("KO B6")
        self.assertEqual(board.make("B6"), -2)
        self.assertEqual(board.make("F6"), 1)
        # print(); board.display(); print("KO F5")
        self.assertEqual(board.make("F5"), -2)
        self.assertEqual(board.make("PASS"), 0)
        # print(); board.display()

        self.assertEqual(board.make("B6"), 1)
        # print(); board.display(); print("KO F5")
        self.assertEqual(board.make("F5"), -2)
        self.assertEqual(board.make("PASS"), 0)
        self.assertEqual(board.make("C6"), 0)

        # print(); board.display(); print("KO A6 F5")
        self.assertEqual(board.make("A6"), -2)
        self.assertEqual(board.make("F5"), -2)

    def test_simple_ko(self):
        BOARD = textwrap.dedent("""\
            .o.xxo
            oxxxo.
            o.x.oo
            xx.oo.
            oooo.o
            oooooo
            """)
        board = GoGame.from_string(BOARD, Rule(KoRule.SIMPLE))
        # rint(); board.display()

        self.assertEqual(board.make("F5"), 1)
        # print(); board.display(); print("KO F6")
        self.assertEqual(board.make("F6"), -2)
        self.assertEqual(board.make("PASS"), 0)
        self.assertEqual(board.make("C3"), 0)

        # print(); board.display()

        self.assertEqual(board.make("F6"), 1)
        # print(); board.display()

        # Ko move
        # print(); board.display(); print("KO F5")
        self.assertEqual(board.make("F5"), -2)
        self.assertEqual(board.make("D4"), 0)
        # print(); board.display()

        # Beginning sending two returning one cycle
        self.assertEqual(board.make("C6"), 0)
        # print(); board.display()
        self.assertEqual(board.make("A6"), 2)
        # print(); board.display(); print("KO B6")
        self.assertEqual(board.make("B6"), 1)
        # print(); board.display()
        self.assertEqual(board.make("PASS"), 0)

        self.assertEqual(board.make("C6"), 0)
        self.assertEqual(board.make("A6"), 2)
        self.assertEqual(board.make("B6"), 1)
        self.assertEqual(board.make("C6"), 0)
        self.assertEqual(board.make("PASS"), 0)
