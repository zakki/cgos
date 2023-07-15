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
let players = new Map();

(function(){
    "use strict";

    const POLL_INTERVAL = 10_000;
    const FORCE_UPDATE_SGF = true;

    let updateCheckbox;

    function createPlayer(elmList, gameId, sgfPath, title, mode) {
        let elmGame = document.createElement("div");
        elmGame.id = gameId;
        elmGame.classList.add("game");
        elmList.prepend(elmGame);

        let elmHeader = document.createElement("div");
        elmHeader.classList.add("header");
        let elmTitle = document.createElement("a");
        elmTitle.innerText = title;
        elmTitle.href = "viewer.html?" + sgfPath;
        elmHeader.append(elmTitle)
        elmHeader.insertAdjacentHTML('beforeend', '<span class="spacer"/>');

        let elmButtons = document.createElement("div");
        elmButtons.classList.add("buttons");

        elmButtons.insertAdjacentHTML('beforeend', '<span class="material-symbols-outlined close">close</span>');
        elmHeader.append(elmButtons);

        elmGame.append(elmHeader);

        let sgfPath2 = sgfPath;
        if (FORCE_UPDATE_SGF)
            sgfPath2 += "?_=" + Date.now();

        let elmPlayer = document.createElement("iframe");
        elmPlayer.className = "player";
        elmPlayer.src = "viewer_iframe.html?" + sgfPath2;
        elmGame.append(elmPlayer)

        const obj = {
            "element": elmGame,
            "mode": mode,
            "active": true,
        }
        elmButtons.querySelector(".close").onclick = () => {
            elmGame.style.display = "none";
            obj.active = false;
        }
        players.set(gameId, obj);
    }

    function addWgo(lines) {
        const elmNum = document.querySelector("#num-games");
        const numGames = Number.parseInt(elmNum.value);
        //console.log(elmNum, numGames);
        const elmList = document.getElementById("games");
        let gameKeys = new Set(Array.from(players.keys()));
        for (let line of lines) {
            let tokens = line.split(" ");
            let gid, sgfPath, white, black, result;
            if (tokens[0] === "g") {
                gid = tokens[1];
                sgfPath = "SGF/" + tokens[6].replaceAll("-", "/") + "/" + tokens[1] + ".sgf";
                white = tokens[2];
                black = tokens[4];
                result = tokens[10];
            } else if (tokens[0] === "s") {
                gid = tokens[3];
                sgfPath = "SGF/" + tokens[1].replaceAll("-", "/") + "/" + tokens[3] + ".sgf";
                white = tokens[4];
                black = tokens[5];
                result = "*";
            } else {
                continue;
            }
            const title = gid + " " + white + " - " + black + " " + result;
            const gameId = "game-"+gid;
            let obj = players.get(gameId);
            // let elmGame = document.getElementById(gameId);
            if (obj) {
                // console.log("exists", gameId)
                if (obj.active && obj.mode === "s") {
                    // obj.player.loadSgfFromFile(sgfPath, END_MOVES);
                    obj.element.querySelector("a").innerText = title;
                }
                players.get(gameId).mode = tokens[0];
            } else {
                createPlayer(elmList, gameId, sgfPath, title, tokens[0]);
            }
            gameKeys.delete(gameId);
        }

        // Remove games
        let keys = Array.from(players.keys());
        keys.sort((a, b) => Number(b.split("-")[1]) - Number(a.split("-")[1]))
        if (numGames > 0) {
            let numVisible = 0;
            for (let i = 0; i < keys.length; i++) {
                const obj = players.get(keys[i]);
                if (obj.active) {
                    numVisible ++;
                }
                if (numVisible > numGames || !obj.active) {
                    // console.log("remove", obj);
                    obj.active = false;
                    if (obj.element)
                        elmList.removeChild(obj.element);
                    obj.player = null;
                    obj.element = null;
                }
            }
        }
        // console.log(gameKeys);
    }

    function pollWebData() {
        let xhr = new XMLHttpRequest();

        if (!xhr) {
            console.error('Fail to create XMLHttpRequest');
            return false;
        }
        xhr.onreadystatechange = () => {
            if (xhr.readyState === XMLHttpRequest.DONE) {
                let lines = xhr.responseText.split("\n");

                const elmWdata = document.getElementById("wdata");
                if (elmWdata) {
                    // console.log(lines);
                    elmWdata.innerText = xhr.responseText;
                }
                addWgo(lines);
            }
        };
        xhr.open("GET", "wdata.txt");
        xhr.setRequestHeader("Cache-Control", "no-cache, no-store, max-age=0");
        xhr.send();
    }

    let pollHandlerId = null;
    function updatePollHandler() {
        if (updateCheckbox.checked) {
            pollWebData();
            pollHandlerId = window.setInterval(pollWebData, POLL_INTERVAL)
        } else {
            window.clearInterval(pollHandlerId);
        }
    }

    window.addEventListener('load', (event) => {
        updateCheckbox = document.querySelector("#update");
        updateCheckbox.addEventListener("click", (e) => {
            updatePollHandler();
        });


        let resetButton = document.querySelector("#reset");
        resetButton.addEventListener("click", (e) => {
            players.clear();
            const elmList = document.getElementById("games");
            elmList.innerHTML = '';
            pollWebData();
        });

        updatePollHandler();
    });
})();
