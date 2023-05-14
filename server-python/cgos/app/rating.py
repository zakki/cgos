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


# produce a printable rating given rating and K
# ---------------------------------------------
def strRate(elo: float, k: float) -> str:

    r = "%0.0f" % elo

    if elo < 0.0:
        r = "0"
    if k > 16.0:
        r += "?"

    return r
