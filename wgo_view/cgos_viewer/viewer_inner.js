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
/* global WGo, pako */
(function (cgos) {
	const POLL_INTERVAL = 10_000;
	const END_MOVES = 100000;
	const FORCE_UPDATE_SGF = true;
	const USE_FETCH = true;
	const VALID_SGF_PATH = "^[/a-zA-Z0-9.]*(\\?_=[0-9]*)?$";
	// Number of moves to advance when swiping full width
	const MAX_SWIPE_MOVES = 20;

	const LAYOUT_VIEWER = [
		{
			conditions: {
				minWidth: 650
			},
			layout: WGo.BasicPlayer.layouts["right_top"],
			className: "wgo-twocols wgo-large"
		},
		{
			layout: WGo.BasicPlayer.layouts["one_column"],
			className: "wgo-medium"
		}
	];
	cgos.LAYOUT_VIEWER = LAYOUT_VIEWER;
	const LAYOUT_LIST = [
		{
			layout: WGo.BasicPlayer.layouts["no_comment"],
			className: "wgo-xsmall"
		}
	];
	cgos.LAYOUT_LIST = LAYOUT_LIST;

	class WGoPlayer {
		// Touch mode event handlers and settings
		_events = {};
		touchMode = false;
		touchSwipe = true;
		_touchStartX = 0;
		_touchStartY = 0;
		_touchStartTime = 0;
		_touchStartHandler = null;
		_touchEndHandler = null;
		updateCheckbox;
		player;

		sgfBuffer = new Uint8Array(1_000_000);
		sgfSize = 0;
		lastSgfPos = 0;
		useRangeFetch = USE_FETCH;

		pollHandlerId = null;

		constructor(elmPlayer, path, updateCheckbox, options = {}) {
			this.path = path;
			this.elmPlayer = elmPlayer;
			// Initialize touch options
			const {
				touchMode = false,
				touchSwipe = true,
				layout = LAYOUT_VIEWER,
				stoneStyle = "SHELL"
			} = options;
			this.touchMode = touchMode;
			this.touchSwipe = touchSwipe;

			if (!path.match(VALID_SGF_PATH)) {
				console.error("bad sgf", path);
				return;
			}

			this.player = new WGo.BasicPlayer(elmPlayer, {
				move: END_MOVES,
				markLastMove: true,
				kifuLoaded: (e) => {
					if (
						e &&
						e.kifu &&
						e.kifu.info &&
						e.kifu.info.RE &&
						e.kifu.info.RE.trim() != "?"
					) {
						this.stop();
					}
					setTimeout(() => {
						this.player.last();
						this.player.previous();
						this.player.next();
					});
				},
				layout: layout
			});
			this.setStoneStyle(stoneStyle);

			const sgflink = document.querySelector("#sgflink");
			if (sgflink) sgflink.href = path;

			if (updateCheckbox) {
				this.updateCheckbox = updateCheckbox;
				this.updateCheckbox.addEventListener("click", (e) => {
					this.updatePollHandler();
				});
			} else {
				this.updateCheckbox = {
					checked: true
				};
			}
			this.updatePollHandler();
			// Initialize touch mode
			this.setTouchMode(this.touchMode);
		}

		setStoneStyle(style) {
			if (!this.player || !this.player.board) {
				return;
			}
			const board = this.player.board;
			if (style === "REALISTIC") {
				board.stoneHandler = WGo.Board.drawHandlers.REALISTIC;
			} else if (style === "GLOW") {
				board.stoneHandler = WGo.Board.drawHandlers.GLOW;
			} else if (style === "SHELL") {
				board.stoneHandler = WGo.Board.drawHandlers.SHELL;
			} else if (style === "PAINTED") {
				board.stoneHandler = WGo.Board.drawHandlers.PAINTED;
			} else {
				board.stoneHandler = WGo.Board.drawHandlers.MONO;
			}
			board.redraw();
		}

		pollSgf() {
			let path = this.path;
			if (!this.useRangeFetch) {
				if (FORCE_UPDATE_SGF) path += "?_=" + Date.now();
				this.player.loadSgfFromFile(path);
				this.player.updateDimensions();
				return;
			}

			const startPos = this.lastSgfPos;

			// console.log("fetch", sgfSize, startPos);
			const init = {
				cache: "no-store"
			};
			if (startPos > 0) {
				//startPos = ((startPos / CHUNK_SIZE) | 0) * CHUNK_SIZE;
				init["headers"] = {
					range: "bytes=" + startPos + "-" + (startPos + 10_000_000)
				};
			}
			const binpath = this.path.replace(".sgf", `.bin`);
			fetch(binpath, init)
				.then((r) => {
					if (r.ok) {
						return r.arrayBuffer();
					} else {
						if (r.status == 404) {
							if (
								this.player &&
								this.player.kifu &&
								this.player.kifu.nodeCount > 0
							) {
								this.useRangeFetch = false;
								return null;
							}
							return Promise.reject("404");
						}
						this.useRangeFetch = false;
						return Promise.reject("error");
					}
				})
				.then(
					(buf) => {
						if (buf == null) return;
						const size = startPos + buf.byteLength;
						if (size >= this.sgfBuffer.byteLength) {
							const newBuffer = new Uint8Array(size * 2);
							// console.log("resize", sgfBuffer.byteLength, size);
							newBuffer.set(this.sgfBuffer);
							this.sgfBuffer = newBuffer;
						}

						this.sgfBuffer.set(new Uint8Array(buf), startPos);
						this.sgfSize = size;

						const sgf = this.decode();
						// console.log(sgf);
						if (!sgf.trim().endsWith(")")) {
							console.log("ignore bad sgf", sgf);
							//pollSgf();
							return;
						}
						this.player.loadSgf(sgf);
						this.player.updateDimensions();
					},
					(err) => {
						console.error("fetch error", err);
						this.player.loadSgfFromFile(this.path);
						this.player.updateDimensions();
					}
				);
		}

		decode() {
			let sgf = "";
			const decoder = new TextDecoder();
			const view = new DataView(this.sgfBuffer.buffer);
			for (let i = 0; i < this.sgfSize; ) {
				let size = view.getInt32(i, true);
				let buf;
				if (size < 0) {
					size = -size;
					buf = pako.inflate(
						new Uint8Array(this.sgfBuffer.buffer, i + 4, size)
					);
				} else {
					buf = new Uint8Array(this.sgfBuffer.buffer, i + 4, size);
				}
				const chunk = decoder.decode(buf);
				// console.log(i, chunk);
				if (chunk.indexOf("CZ[]") > 0) {
					this.lastSgfPos = i;
				}

				sgf += chunk;

				i += 4 + size;
			}

			return sgf;
		}

		updatePollHandler() {
			if (this.updateCheckbox.checked) {
				this.pollSgf();
				this.pollHandlerId = window.setInterval(
					() => this.pollSgf(),
					POLL_INTERVAL
				);
			} else {
				window.clearInterval(this.pollHandlerId);
			}
		}

		stop() {
			this.updateCheckbox.checked = false;
			this.updatePollHandler();
		}

		/**
		 * Enable or disable touch mode.
		 */
		setTouchMode(enabled) {
			this.touchMode = enabled;
			// Toggle CSS class on root element
			if (enabled) {
				document.documentElement.classList.add("touch-mode");
			} else {
				document.documentElement.classList.remove("touch-mode");
			}
			// Bind or unbind touch events
			if (enabled) {
				this.bindTouchEvents();
			} else {
				this.unbindTouchEvents();
			}
			// Immediately update player dimensions after CSS change
			if (this.player && this.player.updateDimensions) {
				this.player.updateDimensions();
			}
		}

		/**
		 * Bind touch event handlers.
		 */
		bindTouchEvents() {
			if (this.touchSwipe) {
				// On swipe start, record position and reset accumulator
				this._touchStartHandler = (e) => {
					const t = e.touches[0];
					this._touchStartX = t.clientX;
					this._touchStartY = t.clientY;
					this._lastSwipeDx = 0;
				};
				// On swipe move, trigger moves based on horizontal distance
				this._touchMoveHandler = (e) => {
					const t = e.touches[0];
					const dx = t.clientX - this._touchStartX;
					const dy = t.clientY - this._touchStartY;
					const verticalThreshold = 30;
					if (Math.abs(dy) > verticalThreshold) return;
					const width =
						this.elmPlayer.clientWidth || window.innerWidth;
					const unit = width / MAX_SWIPE_MOVES;
					// Swipe left: forward moves
					while (dx - this._lastSwipeDx <= -unit) {
						this.player.next();
						this._lastSwipeDx -= unit;
						this._emit("swipeLeft", 1);
					}
					// Swipe right: backward moves
					while (dx - this._lastSwipeDx >= unit) {
						this.player.previous();
						this._lastSwipeDx += unit;
						this._emit("swipeRight", 1);
					}
				};
				this.elmPlayer.addEventListener(
					"touchstart",
					this._touchStartHandler
				);
				this.elmPlayer.addEventListener(
					"touchmove",
					this._touchMoveHandler
				);
			}
		}

		/**
		 * Unbind touch event handlers.
		 */
		unbindTouchEvents() {
			if (this._touchStartHandler) {
				this.elmPlayer.removeEventListener(
					"touchstart",
					this._touchStartHandler
				);
				this._touchStartHandler = null;
			}
			if (this._touchMoveHandler) {
				this.elmPlayer.removeEventListener(
					"touchmove",
					this._touchMoveHandler
				);
				this._touchMoveHandler = null;
			}
		}

		/**
		 * Register event handler.
		 */
		on(event, callback) {
			if (!this._events[event]) this._events[event] = [];
			this._events[event].push(callback);
		}

		/**
		 * Unregister event handler.
		 */
		off(event, callback) {
			if (!this._events[event]) return;
			if (callback) {
				const idx = this._events[event].indexOf(callback);
				if (idx > -1) this._events[event].splice(idx, 1);
			} else {
				delete this._events[event];
			}
		}

		/**
		 * Emit internal event.
		 */
		_emit(event, ...args) {
			const handlers = this._events[event];
			if (handlers) handlers.forEach((fn) => fn.apply(this, args));
		}
	}

	cgos.WGoPlayer = WGoPlayer;
})((window.cgos = window.cgos || {}));
