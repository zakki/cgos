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

    let sgfBuffer = null;
    let sgfSize = 0;
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

        if (sgfBuffer == null) {
            sgfSize = 0;
            sgfBuffer = new Uint8Array(1024);
        }
        let startPos = Math.max(0, sgfSize - 8);
        // console.log("fetch", sgfSize, startPos);
        let init = {
            cache: "no-store"
        };
        if (startPos > 0) {
            init["headers"] = {
                    'range': 'bytes=' + startPos + "-" + (startPos+10_000_000),
            };
        }
        fetch(path, init)
        .then(r => {
            if (r.ok) {
                return r.arrayBuffer();
            } else {
                if (r.status == 404) {
                    return Promise.reject("404");
                }
                useRangeFetch = false;
                return Promise.reject("error");
            }
        })
        .then(buf => {
            let size = startPos + buf.byteLength;
            if (size >= sgfBuffer.byteLength) {
                let newBuffer = new Uint8Array(size * 2);
                // console.log("resize", sgfBuffer.byteLength, size);
                newBuffer.set(sgfBuffer);
                sgfBuffer = newBuffer;
            }

            sgfBuffer.set(new Uint8Array(buf), startPos);
            sgfSize = size;
            let sgf = new TextDecoder().decode(sgfBuffer.slice(0, sgfSize));
            // console.log(sgf);
            if (!sgf.trim().endsWith(")")) {
                pollSgf();
                return;
            }
            player.loadSgf(sgf, END_MOVES);
            player.updateDimensions();
            if (sgf.indexOf('CZ[]') > 0) {
                useRangeFetch = true;
            } else {
                useRangeFetch = false;
            }
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
