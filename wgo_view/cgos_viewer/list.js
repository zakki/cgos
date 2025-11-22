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
(function (cgos) {
	"use strict";

	const players = new Map();
	cgos.players = players;
	const tvControllers = new Map();

	const rawSearch = window.location.search.substring(1);
	const urlParams = new URLSearchParams(rawSearch);
	const tvGameFilter = new Set();
	const tvGamesParam = urlParams.get("tvGames");
	if (tvGamesParam) {
		for (const token of tvGamesParam.split(/[,;]/)) {
			const trimmed = token.trim();
			if (trimmed) tvGameFilter.add(trimmed);
		}
	}

	const tvStorageKey = "cgos_tv_mode";
	const tvCycleStorageKey = "cgos_tv_cycle";
	let storedTvPref = false;
	let storedCycleSpec = "";
	try {
		storedTvPref = localStorage.getItem(tvStorageKey) === "true";
		storedCycleSpec = localStorage.getItem(tvCycleStorageKey) || "";
	} catch (e) {
		// ignore storage errors
	}
	const tvParam = urlParams.get("tv");
	if (tvParam != null) {
		storedTvPref = tvParam !== "0" && tvParam.toLowerCase() !== "false";
	}
	const tvCycleParam = urlParams.get("tvCycle");
	if (tvCycleParam) {
		storedCycleSpec = tvCycleParam;
		try {
			localStorage.setItem(tvCycleStorageKey, tvCycleParam);
		} catch (e) {
			// ignore
		}
	}
	const parseCycleConfig =
		typeof cgos.parseTvCycleConfig === "function"
			? cgos.parseTvCycleConfig
			: () => ({
					neutralMs: undefined,
					ownershipMs: undefined,
					readingPerCandidateMs: undefined,
					readingMaxCandidates: undefined
				});
	const tvCycleConfig = parseCycleConfig(storedCycleSpec);
	let tvModeEnabled = false;

	const POLL_INTERVAL = 10_000;
	const FORCE_UPDATE_SGF = false;

	let currentAnalysisMode = false;
	let currentTouchMode = false;
	let currentStoneStyle = "SHELL";
	let tvCheckbox = null;
	let analysisCheckbox = null;
	let touchCheckbox = null;
	let stoneStyleSelect = null;
	let prevAnalysisChecked = false;
	let prevUpdateChecked = true;

	function createPlayer(elmList, gameId, sgfPath, title, mode) {
		const elmGame = document.createElement("div");
		elmGame.id = gameId;
		elmGame.classList.add("game");
		elmList.prepend(elmGame);

		const elmHeader = document.createElement("div");
		elmHeader.classList.add("header");
		const elmTitle = document.createElement("a");
		elmTitle.innerText = title;
		elmTitle.title = title;
		elmTitle.href = "viewer.html?" + sgfPath;
		elmHeader.append(elmTitle);
		elmHeader.insertAdjacentHTML("beforeend", '<span class="spacer"/>');

		const elmButtons = document.createElement("div");
		elmButtons.classList.add("buttons");

		elmButtons.insertAdjacentHTML(
			"beforeend",
			'<span class="material-symbols-outlined close">close</span>'
		);
		elmHeader.append(elmButtons);

		elmGame.append(elmHeader);

		let sgfPath2 = sgfPath;
		if (FORCE_UPDATE_SGF) sgfPath2 += "?_=" + Date.now();

		const elmPlayer = document.createElement("div");
		elmPlayer.className = "player";
		// elmPlayer.src = "viewer_iframe.html?" + sgfPath2;
		elmGame.append(elmPlayer);
		const player = new cgos.WGoPlayer(elmPlayer, sgfPath2, null, {
			touchMode: currentTouchMode,
			touchSwipe: true,
			layout: cgos.LAYOUT_LIST
		});
		player.player._cgos.set(currentAnalysisMode);

		const obj = {
			element: elmGame,
			mode: mode,
			active: true,
			player: player
		};
		elmButtons.querySelector(".close").onclick = () => {
			elmGame.style.display = "none";
			obj.active = false;
			player.stop();
		};
		players.set(gameId, obj);
		if (tvModeEnabled) {
			startTvForGame(gameId, obj, tvControllers.size * 750);
		}
	}

	function applyStoneStyle(style) {
		for (const obj of players.values()) {
			if (obj.player) {
				obj.player.setStoneStyle(style);
			}
		}
	}

	function applyTouchMode(touchMode) {
		for (const obj of players.values()) {
			if (obj.player) {
				obj.player.setTouchMode(touchMode);
			}
		}
	}

	function applyAnalysisMode(enabled) {
		currentAnalysisMode = enabled;
		if (analysisCheckbox) analysisCheckbox.checked = enabled;
		for (const obj of players.values()) {
			if (obj.player && obj.player.player && obj.player.player._cgos) {
				obj.player.player._cgos.set(enabled);
				obj.player.player.update();
			}
		}
	}

	function shouldUseTv(gameId) {
		if (!tvGameFilter.size) return true;
		const gid = gameId.replace("game-", "");
		return tvGameFilter.has(gid);
	}

	function ensureTvController(gameId, obj, offsetMs = 0) {
		if (!obj || !obj.player) return null;
		let ctrl = tvControllers.get(gameId);
		const options = Object.assign(
			{ staggerOffsetMs: offsetMs },
			tvCycleConfig
		);
		if (!ctrl) {
			if (typeof cgos.createTvSpotlight !== "function") return null;
			try {
				ctrl = cgos.createTvSpotlight(obj.player, options);
				tvControllers.set(gameId, ctrl);
			} catch (err) {
				console.error("Failed to create TV controller", err);
				return null;
			}
		} else {
			ctrl.setCycleConfig(options);
		}
		return ctrl;
	}

	function stopTvController(gameId, destroy) {
		const ctrl = tvControllers.get(gameId);
		if (!ctrl) return;
		ctrl.stop();
		if (destroy && typeof ctrl.destroy === "function") ctrl.destroy();
		if (destroy) tvControllers.delete(gameId);
	}

	function startTvForGame(gameId, obj, offsetMs = 0) {
		if (!tvModeEnabled) return;
		if (!shouldUseTv(gameId)) return;
		const ctrl = ensureTvController(gameId, obj, offsetMs);
		if (ctrl) ctrl.start();
	}

	function startTvForAllGames() {
		let index = 0;
		for (const [gameId, obj] of players.entries()) {
			if (!obj.active || !obj.player) continue;
			if (!shouldUseTv(gameId)) continue;
			const offset = index * 750;
			const ctrl = ensureTvController(gameId, obj, offset);
			if (ctrl) ctrl.start();
			index++;
		}
	}

	function stopAllTvControllers(destroy) {
		for (const [gameId, ctrl] of tvControllers.entries()) {
			ctrl.stop();
			if (destroy && typeof ctrl.destroy === "function") ctrl.destroy();
			if (destroy) tvControllers.delete(gameId);
		}
		if (destroy) tvControllers.clear();
	}

	function persistTvPreference(enabled) {
		try {
			localStorage.setItem(tvStorageKey, enabled ? "true" : "false");
		} catch (e) {
			// ignore
		}
	}

	function enableTvMode() {
		if (tvModeEnabled) return;
		if (typeof cgos.createTvSpotlight !== "function") return;
		tvModeEnabled = true;
		if (tvCheckbox) tvCheckbox.checked = true;
		if (analysisCheckbox) {
			prevAnalysisChecked = analysisCheckbox.checked;
			analysisCheckbox.disabled = true;
		}
		applyAnalysisMode(true);
		if (updateCheckbox) {
			prevUpdateChecked = updateCheckbox.checked;
			updateCheckbox.checked = true;
			updateCheckbox.disabled = true;
			updatePollHandler();
		}
		if (touchCheckbox) touchCheckbox.disabled = true;
		if (stoneStyleSelect) stoneStyleSelect.disabled = true;
		startTvForAllGames();
		persistTvPreference(true);
	}

	function disableTvMode() {
		if (!tvModeEnabled) return;
		tvModeEnabled = false;
		if (tvCheckbox) tvCheckbox.checked = false;
		stopAllTvControllers(false);
		if (analysisCheckbox) {
			analysisCheckbox.disabled = false;
		}
		applyAnalysisMode(prevAnalysisChecked);
		if (updateCheckbox) {
			updateCheckbox.disabled = false;
			updateCheckbox.checked = prevUpdateChecked;
			updatePollHandler();
		}
		if (touchCheckbox) touchCheckbox.disabled = false;
		if (stoneStyleSelect) stoneStyleSelect.disabled = false;
		persistTvPreference(false);
	}

	function addWgo(lines) {
		const elmNum = document.querySelector("#num-games");
		const numGames = Number.parseInt(elmNum.value);
		//console.log(elmNum, numGames);
		const elmList = document.getElementById("games");
		if (elmList == null) throw Error("no games element");
		const gameKeys = new Set(Array.from(players.keys()));
		for (const line of lines) {
			const tokens = line.split(" ");
			let gid, sgfPath, white, black, result;
			let hasError = false;
			let message = "";
			let lastMoveTime = 0;
			if (tokens[0] === "g") {
				gid = tokens[1];
				sgfPath =
					"SGF/" +
					tokens[6].replaceAll("-", "/") +
					"/" +
					tokens[1] +
					".sgf";
				white = tokens[2];
				black = tokens[4];
				result = tokens[10];
			} else if (tokens[0] === "s") {
				gid = tokens[3];
				sgfPath =
					"SGF/" +
					tokens[1].replaceAll("-", "/") +
					"/" +
					tokens[3] +
					".sgf";
				white = tokens[4];
				black = tokens[5];
				result = "*";
				if (tokens.length > 13) {
					const wcon = Number.parseInt(tokens[11]);
					const bcon = Number.parseInt(tokens[12]);
					lastMoveTime = (Number.parseInt(tokens[13]) / 1000) | 0;
					if (wcon == 0) {
						message += "[W ERROR]";
						hasError = true;
					}
					if (bcon == 0) {
						message += "[B ERROR]";
						hasError = true;
					}
					if (lastMoveTime > 30) {
						message += lastMoveTime + "sec ";
					}
				}
			} else {
				continue;
			}
			const title =
				message + gid + " " + white + " - " + black + " " + result;
			const gameId = "game-" + gid;
			const obj = players.get(gameId);
			// let elmGame = document.getElementById(gameId);
			if (obj) {
				obj.mode = tokens[0];
				if (obj.element) {
					// console.log("exists", gameId)
					if (obj.active) {
						// obj.player.loadSgfFromFile(sgfPath, END_MOVES);
						obj.element.querySelector("a").innerText = title;
					}
					// warn slow games
					if (hasError || lastMoveTime > 60) {
						obj.element.style["border-color"] = "red";
					} else if (lastMoveTime > 30) {
						obj.element.style["border-color"] = "yellow";
					} else {
						obj.element.style["border-color"] = null;
					}
				}
			} else {
				createPlayer(elmList, gameId, sgfPath, title, tokens[0]);
			}
			gameKeys.delete(gameId);
		}

		applyStoneStyle(currentStoneStyle);

		// Remove games
		const keys = Array.from(players.keys());
		keys.sort((a, b) => Number(b.split("-")[1]) - Number(a.split("-")[1]));
		if (numGames > 0) {
			let numVisible = 0;
			for (let i = 0; i < keys.length; i++) {
				const obj = players.get(keys[i]);
				if (obj.active) {
					numVisible++;
				}
				if (numVisible > numGames || !obj.active) {
					// console.log("remove", obj);
					obj.active = false;
					if (obj.element) elmList.removeChild(obj.element);
					obj.player = null;
					obj.element = null;
					stopTvController(keys[i], true);
				}
			}
		}
		// console.log(gameKeys);
	}

	function pollWebData() {
		const xhr = new XMLHttpRequest();

		if (!xhr) {
			console.error("Fail to create XMLHttpRequest");
			return false;
		}
		xhr.onreadystatechange = () => {
			if (xhr.readyState === XMLHttpRequest.DONE) {
				const lines = xhr.responseText.split("\n");

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

	let updateCheckbox;
	let pollHandlerId = null;
	function updatePollHandler() {
		if (updateCheckbox.checked) {
			pollWebData();
			pollHandlerId = window.setInterval(pollWebData, POLL_INTERVAL);
		} else {
			window.clearInterval(pollHandlerId);
		}
	}

	window.addEventListener("load", (event) => {
		updateCheckbox = document.querySelector("#update");
		if (updateCheckbox) {
			updateCheckbox.addEventListener("click", (e) => {
				if (tvModeEnabled) {
					updateCheckbox.checked = true;
					return;
				}
				updatePollHandler();
			});
		}

		analysisCheckbox = document.querySelector("#analysis-mode");
		if (analysisCheckbox) {
			analysisCheckbox.addEventListener("change", () => {
				if (tvModeEnabled) {
					analysisCheckbox.checked = true;
					return;
				}
				applyAnalysisMode(analysisCheckbox.checked);
			});
			analysisCheckbox.checked = currentAnalysisMode;
			prevAnalysisChecked = analysisCheckbox.checked;
		}

		tvCheckbox = document.querySelector("#tv-mode");
		if (tvCheckbox) {
			tvCheckbox.addEventListener("change", (e) => {
				if (e.target.checked) enableTvMode();
				else disableTvMode();
			});
		}

		touchCheckbox = document.querySelector("#touchmode");
		const touchStorageKey = "cgos_touch_mode";
		try {
			currentTouchMode = localStorage.getItem(touchStorageKey) === "true";
		} catch (e) {
			// do nothing
		}
		if (touchCheckbox) {
			touchCheckbox.checked = currentTouchMode;

			touchCheckbox.addEventListener("click", (e) => {
				currentTouchMode = e.target.checked;
				try {
					localStorage.setItem(touchStorageKey, currentTouchMode);
				} catch (err) {
					// do nothing
				}
				applyTouchMode(currentTouchMode);
			});
		}

		stoneStyleSelect = document.querySelector("#stone-style");
		const stoneStyleStorageKey = "cgos_stone_style";
		try {
			currentStoneStyle =
				localStorage.getItem(stoneStyleStorageKey) || "SHELL";
		} catch (e) {
			// do nothing
		}
		applyStoneStyle(currentStoneStyle);
		if (stoneStyleSelect) {
			stoneStyleSelect.value = currentStoneStyle;

			stoneStyleSelect.addEventListener("change", (e) => {
				const style = e.target.value;
				try {
					localStorage.setItem(stoneStyleStorageKey, style);
				} catch (err) {
					// do nothing
				}
				applyStoneStyle(style);
			});
		}

		const resetButton = document.querySelector("#reset");
		if (resetButton) {
			resetButton.addEventListener("click", (e) => {
				players.clear();
				stopAllTvControllers(true);
				const elmList = document.getElementById("games");
				if (elmList == null) throw Error("no games element");
				elmList.innerHTML = "";
				pollWebData();
			});
		}

		if (storedTvPref) {
			enableTvMode();
		} else if (tvCheckbox) {
			tvCheckbox.checked = false;
		}

		updatePollHandler();
	});
})((window.cgos = window.cgos || {}));
