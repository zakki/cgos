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
	const POLL_INTERVAL = 10_000;
	const END_MOVES = 100000;
	const FORCE_UPDATE_SGF = true;
	const USE_FETCH = true;
	const VALID_SGF_PATH = "^[/a-zA-Z0-9.]*(\\?_=[0-9]*)?$";

	class WGoPlayer {
		updateCheckbox = {
			checked: true
		};
		player;

		sgfBuffer = new Uint8Array(1_000_000);
		sgfSize = 0;
		lastSgfPos = 0;
		useRangeFetch = USE_FETCH;

		pollHandlerId = null;

		constructor(elmPlayer, path) {
			this.path = path;
			this.elmPlayer = elmPlayer;

			if (!path.match(VALID_SGF_PATH)) {
				console.error("bad sgf", path);
				return;
			}

			this.player = new WGo.BasicPlayer(elmPlayer, {
				sgfFile: path,
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
				}
			});

			// let sgflink = document.querySelector("#sgflink");
			// if (sgflink)
			//     sgflink.href = path;

			// updateCheckbox = document.querySelector("#update");
			// updateCheckbox.addEventListener("click", (e) => {
			//     updatePollHandler();
			// });

			this.updatePollHandler();
		}

		pollSgf() {
			if (!this.useRangeFetch) {
				if (FORCE_UPDATE_SGF) this.path += "?_=" + Date.now();
				this.player.loadSgfFromFile(this.path, END_MOVES);
				this.player.updateDimensions();
				return;
			}

			let startPos = this.lastSgfPos;

			// console.log("fetch", sgfSize, startPos);
			let init = {
				cache: "no-store"
			};
			if (startPos == 0) {
				this.player.loadSgfFromFile(this.path, END_MOVES);
				this.player.updateDimensions();
			} else {
				//startPos = ((startPos / CHUNK_SIZE) | 0) * CHUNK_SIZE;
				init["headers"] = {
					range: "bytes=" + startPos + "-" + (startPos + 10_000_000)
				};
			}
			let path = this.path.replace(".sgf", `.bin`);
			fetch(path, init)
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
				.then((buf) => {
					if (buf == null) return;
					let size = startPos + buf.byteLength;
					if (size >= this.sgfBuffer.byteLength) {
						let newBuffer = new Uint8Array(size * 2);
						// console.log("resize", sgfBuffer.byteLength, size);
						newBuffer.set(this.sgfBuffer);
						this.sgfBuffer = newBuffer;
					}

					this.sgfBuffer.set(new Uint8Array(buf), startPos);
					this.sgfSize = size;

					let sgf = this.decode();
					// console.log(sgf);
					if (!sgf.trim().endsWith(")")) {
						console.log("ignroe bad sgf", sgf);
						//pollSgf();
						return;
					}
					this.player.loadSgf(sgf, END_MOVES);
					this.player.updateDimensions();
				});
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
	}

	cgos.WGoPlayer = WGoPlayer;
})((window.cgos = window.cgos || {}));
