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
		const path = location.search.substring(1);
		const elmPlayer = document.querySelector("#cgoswgo");
		const updateCheckbox = document.querySelector("#update");
		const touchCheckbox = document.querySelector("#touchmode");
		const stoneStyleSelect = document.querySelector("#stone-style");
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
	});
})(cgos);
