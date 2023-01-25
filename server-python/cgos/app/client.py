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

import asyncio
import logging
import traceback
from typing import Optional


# Setup logger
logger = logging.getLogger("cgos_server")
logger.setLevel(logging.DEBUG)

if len(logger.handlers) == 0:
    logHandler = logging.StreamHandler()
    logHandler.setLevel(logging.DEBUG)
    formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    logHandler.setFormatter(formatter)
    logger.addHandler(logHandler)


ENCODING = "utf-8"


class Client:
    def __init__(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter, id: str
    ) -> None:
        self._reader = reader
        self._writer = writer
        self._readQueue: asyncio.Queue[str] = asyncio.Queue()
        self._writeQueue: asyncio.Queue[str] = asyncio.Queue()
        self.id = id or "<unknown>"
        self.alive = True

    def close(self) -> None:
        self.alive = False

    def send(self, message: str) -> bool:
        try:
            logger.debug(f"S -> {self.id}: '{message}'")
            self._writeQueue.put_nowait(message + "\n")
            return True
        except:
            logger.error(f"alert: Client crash for user: {self.id}")
            logger.error(traceback.format_exc())
            logger.error(traceback.format_stack())
            return False

    def readLine_nowait(self) -> Optional[str]:
        try:
            return self._readQueue.get_nowait()
        except asyncio.QueueEmpty:
            return None

    async def readLine(self) -> str:
        line = await self._readQueue.get()
        logger.debug(f"S <- {self.id}: '{line}'")
        return line

    async def writeTask(self) -> None:
        while self.alive:
            try:
                msg = await self._writeQueue.get()
                logger.debug(f"S ==> {self.id}: '{msg}'")
                self._writer.write(bytes(msg, encoding=ENCODING))
                await self._writer.drain()
            except Exception as e:
                logger.info(f"writer exception {self.id} {str(e)}")
                self.alive = False
            logger.debug(f"send queue {self.id}: {self._writeQueue.qsize()} {msg}")
        logger.info(f"writer ended {self.id}")

    async def readTask(self) -> None:
        while self.alive:
            try:
                line = await self._reader.readline()
                if len(line) == 0:
                    self.alive = False
                    break
                logger.debug(f"S <== {self.id}: '{str(line, ENCODING)}'")
                await self._readQueue.put(str(line, encoding=ENCODING))
            except Exception as e:
                logger.info(f"reader exception {self.id} {str(e)}")
                self.alive = False
        logger.info(f"reader ended {self.id}")
