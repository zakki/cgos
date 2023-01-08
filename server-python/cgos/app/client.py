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

import logging
import socket
import traceback
from typing import Dict, Optional


# Setup logger
logger = logging.getLogger("cgos_server")
logger.setLevel(logging.INFO)
logHandler = logging.StreamHandler()
logHandler.setLevel(logging.INFO)
formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logHandler.setFormatter(formatter)
logger.addHandler(logHandler)


ENCODING = "utf-8"


class Client:
    def __init__(self, s: socket.socket, id: str) -> None:
        self._socket = s
        self.id = id or "<unknown>"
        self._socketfile = self._socket.makefile("rw", encoding=ENCODING)
        self.fileno = s.fileno()
        clients[self.fileno] = self

    def _write(self, message: str) -> None:
        logger.debug(f"S -> {self.id}: '{message}'")
        self._socketfile.write(message + "\n")
        self._socketfile.flush()

    def _read(self) -> str:
        line = self._socketfile.readline()
        if len(line) == 0:
            raise Exception("EOF")
        logger.debug(f"S <- {self.id}: '{line}'")
        line = line.strip()
        return line

    def close(self) -> None:
        if self.fileno in clients:
            del clients[self.fileno]
        try:
            self._socketfile.close()
            self._socket.close()
        except Exception as e:
            logger.error(str(e))

    def recvLine(self) -> Optional[str]:
        try:
            return self._read()
        except:
            return None

    def send(self, msg: str) -> bool:
        try:
            self._write(msg)
            return True
        except:
            logger.error(f"alert: Client crash for user: {self.id}")
            logger.error(traceback.format_exc())
            logger.error(traceback.format_stack())
            return False


clients: Dict[int, Client] = dict()  # map raw socket to socket
