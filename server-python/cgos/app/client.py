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

import asyncio
import traceback
from typing import Optional

from util.logutils import getLogger


# Setup logger
logger = getLogger("cgos_server.client")

ENCODING = "utf-8"

MAX_QUEUE_SIZE = 10


class Client:
    def __init__(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter, id: str
    ) -> None:
        self._reader = reader
        self._writer = writer
        self._readQueue: asyncio.Queue[str] = asyncio.Queue(MAX_QUEUE_SIZE)
        self._writeQueue: asyncio.Queue[str] = asyncio.Queue(MAX_QUEUE_SIZE)
        self.id = id or "<unknown>"
        self.user_name: Optional[str] = None
        self.alive = True

    def close(self) -> None:
        self.alive = False

    def send(self, *messages: str) -> bool:
        try:
            logger.debug(f"S -> {self.id}: '{list(messages)}'")
            if self._writer.is_closing():
                logger.info(f"writer is closing user: {self.id}")
                self.alive = False
                return False
            message = "\n".join(messages) + "\n"
            self._writeQueue.put_nowait(message)
            return True
        except:
            logger.error(f"alert: Client crash for user: {self.id}")
            logger.error(traceback.format_exc())
            logger.error(traceback.format_stack())
            self.alive = False
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
        try:
            self._writer.close()
        except:
            pass
        logger.info(f"writer ended {self.id}")

    async def readTask(self) -> None:
        # Old python client doesn't send new line
        first = True
        pythonClient = True
        while self.alive:
            try:
                if pythonClient:
                    line = await self._reader.read(10000)
                    if first:
                        first = False
                        pythonClient = str(line, ENCODING).find("\n") < 0
                        logger.info(
                            f"Client {self.id} old-python-client:{pythonClient} {len(line)}"
                        )
                else:
                    line = await self._reader.readline()
                if len(line) == 0:
                    self.alive = False
                    break
                logger.debug(f"S <== {self.id}: '{str(line, ENCODING)}'")
                await self._readQueue.put(str(line, encoding=ENCODING))
            except Exception as e:
                logger.info(f"reader exception {self.id} {str(e)}")
                self.alive = False
        try:
            # put empty string to run writer queue
            self._writeQueue.put_nowait("")
        except:
            pass
        logger.info(f"reader ended {self.id}")
