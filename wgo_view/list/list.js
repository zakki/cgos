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
    const END_MOVES = 100000;
    const FORCE_UPDATE_SGF = true;

    function createPlayer(elmList, gameId, sgfPath, title, mode) {
        let elmGame = document.createElement("div");
        elmGame.id = gameId;
        //elmGame.setAttribute("data-go", sgfPath);
        elmList.prepend(elmGame);

        let elmTitle = document.createElement("a");
        elmTitle.innerText = title;
        elmTitle.href = "viewer.html?" + sgfPath;
        elmGame.append(elmTitle);

        let elmPlayer = document.createElement("div");
        elmPlayer.className = "player";
        elmGame.append(elmPlayer)
        let player = new WGo.BasicPlayer(elmPlayer, {
            sgfFile: sgfPath,
            move: END_MOVES,
            markLastMove: true,
        });
        players[gameId] = [elmGame, player, mode];
    }

    function addWgo(lines) {
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
                if (FORCE_UPDATE_SGF)
                    sgfPath += "?_=" + Date.now();
                white = tokens[4];
                black = tokens[5];
                result = "*";
            } else {
                continue;
            }
            const title = gid + " " + white + " - " + black + " " + result;
            //<div data-wgo="19x19/SGF/2023/01/07/895.sgf" style="width: 700px" ></div>
            const gameId = "game-"+gid;
            let elmGame = document.getElementById(gameId);
            if (elmGame) {
                console.log("exists", gameId)
                if (players[gameId][2] === "s") {
                    players[gameId][1].loadSgfFromFile(sgfPath, END_MOVES)
                    elmGame.querySelector("a").innerText = title;
                }
                players[gameId][2] = tokens[0];
            } else {
                createPlayer(elmList, gameId, sgfPath, title, tokens[0]);
            }
            gameKeys.delete(gameId);
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
                    console.log(lines);
                    elmWdata.innerText = xhr.responseText;
                }
                addWgo(lines);
            }
        };
        xhr.open("GET", "wdata.txt");
        xhr.setRequestHeader("Cache-Control", "no-cache, no-store, max-age=0");
        xhr.send();
    }

    window.addEventListener('load', (event) => {
        pollWebData();
        window.setInterval(pollWebData, POLL_INTERVAL)
    });
})();
