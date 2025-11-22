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
/* global cgos */
(function (cgos) {
	"use strict";

	window.addEventListener("load", (event) => {
		const rawSearch = window.location.search.substring(1);
		const parts = rawSearch.split("&");
		const path = parts.shift() || "";
		const extraQuery = parts.join("&");
		const extraParams = new URLSearchParams(extraQuery);
		const elmPlayer = document.querySelector("#cgoswgo");
		const updateCheckbox = document.querySelector("#update");
		const touchCheckbox = document.querySelector("#touchmode");
		const stoneStyleSelect = document.querySelector("#stone-style");
		const tvCheckbox = document.querySelector("#tv-mode");
		if (!elmPlayer) return;
		// Instantiate the WGoPlayer class (defined in viewer_inner.js)
		// Persist touch mode setting across reloads
		const touchStorageKey = "cgos_touch_mode";
		let initialTouchMode = false;
		if (touchCheckbox) {
			try {
				initialTouchMode =
					localStorage.getItem(touchStorageKey) === "true";
			} catch (e) {
				// do nothing
			}
			touchCheckbox.checked = initialTouchMode;
		}

		// Persist stone style setting across reloads
		const stoneStyleStorageKey = "cgos_stone_style";
		let initialStoneStyle = "SHELL";
		if (stoneStyleSelect) {
			try {
				initialStoneStyle =
					localStorage.getItem(stoneStyleStorageKey) || "SHELL";
			} catch (e) {
				// do nothing
			}
			stoneStyleSelect.value = initialStoneStyle;
		}

		const player = new cgos.WGoPlayer(elmPlayer, path, updateCheckbox, {
			touchMode: initialTouchMode,
			touchSwipe: true,
			stoneStyle: initialStoneStyle
		});
		// Bind touch mode toggle
		if (touchCheckbox) {
			touchCheckbox.addEventListener("click", (e) => {
				const enabled = e.target.checked;
				try {
					localStorage.setItem(touchStorageKey, enabled);
				} catch (err) {
					// do nothing
				}
				player.setTouchMode(enabled);
			});
		}

		// Bind stone style selector
		if (stoneStyleSelect) {
			stoneStyleSelect.addEventListener("change", (e) => {
				const style = e.target.value;
				try {
					localStorage.setItem(stoneStyleStorageKey, style);
				} catch (err) {
					// do nothing
				}
				player.setStoneStyle(style);
			});
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
		const tvParam = extraParams.get("tv");
		let desiredTvMode = storedTvPref;
		if (tvParam != null) {
			desiredTvMode =
				tvParam !== "0" && tvParam.toLowerCase() !== "false";
		}
		const tvCycleParam = extraParams.get("tvCycle");
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
		let tvSpotlight = null;
		let tvModeEnabled = false;
		let prevUpdateChecked = updateCheckbox ? updateCheckbox.checked : true;
		const interactionListeners = [];

		function persistTvPreference(enabled) {
			try {
				localStorage.setItem(tvStorageKey, enabled ? "true" : "false");
			} catch (e) {
				// ignore
			}
		}

		function ensureTvSpotlight() {
			if (tvSpotlight) {
				tvSpotlight.setCycleConfig(tvCycleConfig);
				return tvSpotlight;
			}
			if (typeof cgos.createTvSpotlight !== "function") return null;
			try {
				tvSpotlight = cgos.createTvSpotlight(player, tvCycleConfig);
			} catch (err) {
				console.error("Failed to initialize TV mode", err);
				return null;
			}
			return tvSpotlight;
		}

		function detachInteractionGuards() {
			while (interactionListeners.length) {
				const [target, type, handler] = interactionListeners.pop();
				target.removeEventListener(type, handler);
			}
		}

		function attachInteractionGuards() {
			detachInteractionGuards();
			const handler = () => disableTvMode("interaction");
			const boardElm = player.elmPlayer;
			if (boardElm) {
				boardElm.addEventListener("pointerdown", handler);
				interactionListeners.push([boardElm, "pointerdown", handler]);
				boardElm.addEventListener("touchstart", handler);
				interactionListeners.push([boardElm, "touchstart", handler]);
			}
			window.addEventListener("keydown", handler);
			interactionListeners.push([window, "keydown", handler]);
		}

		function enableTvMode(source) {
			const spotlight = ensureTvSpotlight();
			if (!spotlight) return;
			tvModeEnabled = true;
			if (tvCheckbox) {
				tvCheckbox.checked = true;
			}
			if (updateCheckbox) {
				prevUpdateChecked = updateCheckbox.checked;
				updateCheckbox.checked = true;
				updateCheckbox.disabled = true;
				player.updatePollHandler();
			}
			if (touchCheckbox) touchCheckbox.disabled = true;
			if (stoneStyleSelect) stoneStyleSelect.disabled = true;
			player.elmPlayer.classList.add("wgo-tv-mode");
			attachInteractionGuards();
			spotlight.start();
			persistTvPreference(true);
		}

		function disableTvMode(reason) {
			if (!tvModeEnabled) return;
			tvModeEnabled = false;
			detachInteractionGuards();
			if (tvCheckbox) {
				tvCheckbox.checked = false;
			}
			if (tvSpotlight) {
				tvSpotlight.stop();
			}
			player.elmPlayer.classList.remove("wgo-tv-mode");
			if (updateCheckbox) {
				updateCheckbox.disabled = false;
				updateCheckbox.checked = prevUpdateChecked;
				player.updatePollHandler();
			}
			if (touchCheckbox) touchCheckbox.disabled = false;
			if (stoneStyleSelect) stoneStyleSelect.disabled = false;
			persistTvPreference(false);
		}

		if (tvCheckbox) {
			tvCheckbox.addEventListener("change", (e) => {
				if (e.target.checked) enableTvMode("manual");
				else disableTvMode("manual");
			});
		}

		if (desiredTvMode) {
			enableTvMode("init");
		} else if (tvCheckbox) {
			tvCheckbox.checked = false;
		}
	});
})(cgos);
