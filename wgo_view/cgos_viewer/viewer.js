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
    const VALID_SGF_PATH = "^[/a-zA-Z0-9.]*(\\?_=[0-9]*)?$";

    let updateCheckbox;
    let player;

    function pollSgf() {
        let path = location.search.substring(1);
        if (FORCE_UPDATE_SGF)
            path += "?_=" + Date.now();
        player.loadSgfFromFile(path, END_MOVES);
        player.updateDimensions();
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
                    if (e && e.kifu && e.kifu.info && e.kifu.info.RE != "?") {
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
