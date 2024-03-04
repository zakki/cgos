/**
*  The MIT License
*
*  Copyright (c) 2023 Kensuke Matsuzaki
*
* Permission is hereby granted, free of charge, to any person obtaining a copy
* of this software and associated documentation files (the "Software"), to deal
* in the Software without restriction, including without limitation the rights
* to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
* copies of the Software, and to permit persons to whom the Software is
* furnished to do so, subject to the following conditions:
*
* The above copyright notice and this permission notice shall be included in
* all copies or substantial portions of the Software.
*
* THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
* IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
* FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
* AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
* LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
* OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
* THE SOFTWARE.
*/
(function(){
    "use strict";

    const POLL_INTERVAL = 10_000;
    const END_MOVES = 100000;
    const FORCE_UPDATE_SGF = true;
    const USE_FETCH = true;
    const VALID_SGF_PATH = "^[/a-zA-Z0-9.]*(\\?_=[0-9]*)?$";

    let updateCheckbox;
    let player;

    let sgfBuffer = new Uint8Array(1_000_000);
    let sgfSize = 0;
    let lastSgfPos = 0;
    let useRangeFetch = USE_FETCH;

    function pollSgf() {
        let path = location.search.substring(1);
        if (!useRangeFetch) {
            if (FORCE_UPDATE_SGF)
                path += "?_=" + Date.now();
            player.loadSgfFromFile(path, END_MOVES);
            player.updateDimensions();
            return
        }

        let startPos = lastSgfPos;

        // console.log("fetch", sgfSize, startPos);
        let init = {
            cache: "no-store"
        };
        if (startPos == 0) {
            player.loadSgfFromFile(path, END_MOVES);
            player.updateDimensions();
        } else {
            //startPos = ((startPos / CHUNK_SIZE) | 0) * CHUNK_SIZE;
            init["headers"] = {
                    'range': 'bytes=' + startPos + "-" + (startPos+10_000_000),
            };
        }
        path = path.replace(".sgf", `.bin`)
        fetch(path, init)
        .then(r => {
            if (r.ok) {
                return r.arrayBuffer();
            } else {
                if (r.status == 404) {
                    if (player && player.kifu && player.kifu.nodeCount > 0) {
                        useRangeFetch = false;
                        return null;
                    }
                    return Promise.reject("404");
                }
                useRangeFetch = false;
                return Promise.reject("error");
            }
        })
        .then(buf => {
            if (buf == null)
                return;
            let size = startPos + buf.byteLength;
            if (size >= sgfBuffer.byteLength) {
                let newBuffer = new Uint8Array(size * 2);
                // console.log("resize", sgfBuffer.byteLength, size);
                newBuffer.set(sgfBuffer);
                sgfBuffer = newBuffer;
            }

            sgfBuffer.set(new Uint8Array(buf), startPos);
            sgfSize = size;

            let sgf = "";
            const decoder = new TextDecoder();
            const view = new DataView(sgfBuffer.buffer);
            for (let i = 0; i < sgfSize;) {
                let size = view.getInt32(i, true);
                let buf;
                if (size < 0) {
                    size = -size;
                    buf = pako.inflate(new Uint8Array(sgfBuffer.buffer, i + 4, size));
                } else {
                    buf = new Uint8Array(sgfBuffer.buffer, i + 4, size);
                }
                const chunk = decoder.decode(buf);
                // console.log(i, chunk);
                if (chunk.indexOf('CZ[]') > 0) {
                    lastSgfPos = i;
                }

                sgf += chunk;

                i += 4 + size;
            }
            // console.log(sgf);
            if (!sgf.trim().endsWith(")")) {
                console.log("ignroe bad sgf", sgf)
                //pollSgf();
                return;
            }
            player.loadSgf(sgf, END_MOVES);
            player.updateDimensions();
        });
    }

    window.addEventListener('load', (event) => {
        let path = location.search.substring(1);
        if (!path.match(VALID_SGF_PATH)) {
            console.error("bad sgf", path);
            return;
        }
        if (path.length > 0) {
            let elmPlayer = document.querySelector("#cgoswgo");
            player = new WGo.BasicPlayer(elmPlayer, {
                sgfFile: path,
                move: END_MOVES,
                markLastMove: true,
                kifuLoaded: function(e) {
                    if (e && e.kifu && e.kifu.info && e.kifu.info.RE && e.kifu.info.RE.trim() != "?") {
                        updateCheckbox.checked = false;
                        updatePollHandler();
                    }
                    setTimeout(() => {
                        player.last();
                        player.previous();
                        player.next();
                    });
                },
            });
        }

        let sgflink = document.querySelector("#sgflink");
        if (sgflink)
            sgflink.href = path;

        updateCheckbox = document.querySelector("#update");
        updateCheckbox.addEventListener("click", (e) => {
            updatePollHandler();
        });

        updatePollHandler();
    });


    let pollHandlerId = null;
    function updatePollHandler() {
        if (updateCheckbox.checked) {
            pollSgf();
            pollHandlerId = window.setInterval(pollSgf, POLL_INTERVAL);
        } else {
            window.clearInterval(pollHandlerId);
        }
    }
})();
