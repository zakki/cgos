import { WGo } from "./wgo";

import { BasicPlayer } from "./basicplayer";
import { Component } from "./basicplayer.component";
import { Control, MenuItem, Button, Group } from "./basicplayer.control";

// Utility

function parseCoord(size, str) {
	str = str.toLowerCase();
	const LEGAL_COORDINATES = "abcdefghjklmnopqrstuvwxyz";
	const x = LEGAL_COORDINATES.indexOf(str[0]);
	if (x < 0) return null;
	const y = parseInt(str.substr(1));
	if (Number.isNaN(y)) return null;
	return [x, size - y];
}

// board mousemove callback for cgos move - adds highlighting
const cgos_board_mouse_move = function (x, y) {
	if (this._lastX == x && this._lastY == y) return;

	this._lastX = x;
	this._lastY = y;

	if (this._last_mark) {
		this.board.removeObject(this._last_mark);
	}

	if (
		!this.player.kifuReader ||
		!this.player.kifuReader.game ||
		!this.infoList
	)
		return;
	const game = this.player.kifuReader.game;
	if (x != -1 && y != -1) {
		for (let i = 0; i < this.infoList.length; i++) {
			const o = this.infoList[i];
			if (o.move[0] != x || o.move[1] != y) continue;
			this._last_mark = o.pv.flatMap(function (m, i) {
				const turn = i % 2 == 0 ? -game.turn : game.turn;
				return [
					{
						type: "MONO",
						x: m[0],
						y: m[1],
						c: turn
					},
					{
						type: "LB",
						text: "" + (i + 1),
						x: m[0],
						y: m[1],
						c: turn == WGo.B ? "white" : "black"
					}
				];
			});
			this.board.addObject(this._last_mark);
		}
	} else {
		delete this._last_mark;
	}
};

// board mouseout callback for cgos move
const cgos_board_mouse_out = function () {
	if (this._last_mark) {
		this.board.removeObject(this._last_mark);
		delete this._last_mark;
		delete this._lastX;
		delete this._lastY;
	}
};

const theme_variable = function (key, board) {
	return typeof board.theme[key] == "function"
		? board.theme[key](board)
		: board.theme[key];
};

const moveStatDrawer = {
	stone: {
		draw: function (args, board) {
			const xr = board.getX(args.x),
				yr = board.getY(args.y),
				sr = board.stoneRadius * 0.8,
				font = args.font || theme_variable("font", board) || "";

			this.fillStyle = "#333333";

			{
				let text = args.label;
				if (args.winrate !== null)
					text = (args.winrate * 100).toFixed(1);

				if (text != null) {
					if (text.length == 1)
						this.font = Math.round(sr * 1.5) + "px " + font;
					else if (text.length == 2)
						this.font = Math.round(sr * 1.2) + "px " + font;
					else this.font = Math.round(sr) + "px " + font;

					this.beginPath();
					this.textBaseline = "middle";
					this.textAlign = "center";
					this.strokeStyle = "#ffffff";
					this.strokeText(text, xr, yr - sr * 0.5, 2 * sr);
					this.strokeStyle = null;
					this.fillText(text, xr, yr - sr * 0.5, 2 * sr);
				}
			}

			if (args.score != null) {
				const text = args.score.toFixed(1);
				if (text.length == 1)
					this.font = Math.round(sr * 1.5) + "px " + font;
				else if (text.length == 2)
					this.font = Math.round(sr * 1.2) + "px " + font;
				else this.font = Math.round(sr) + "px " + font;

				this.beginPath();
				this.textBaseline = "middle";
				this.textAlign = "center";
				this.strokeStyle = "#ffffff";
				this.strokeText(text, xr, yr + sr * 0.5, 2 * sr);
				this.strokeStyle = null;
				this.fillText(text, xr, yr + sr * 0.5, 2 * sr);
			}
		}
	}
};

const OwnershipLayer = WGo.extendClass(WGo.Board.CanvasLayer, function () {
	this.super.call(this);
});

OwnershipLayer.prototype.draw = function (board) {
	if (!board._cgosMode) return;
	if (board._cgosOwnership) {
		const CHARS =
			"ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";
		const COLORS = [WGo.B, WGo.W];
		for (let i = 0; i < 2; i++) {
			const c = COLORS[i];
			if (c === WGo.B) this.context.fillStyle = "rgba(0, 0, 0, 0.5)";
			else this.context.fillStyle = "rgba(255, 255, 255, 0.5)";

			for (let j = 0; j < board._cgosOwnership.length; j++) {
				let m = CHARS.indexOf(board._cgosOwnership[j]);
				if (m < 0) break;
				m = (m / 62) * 2 - 1.0;
				if (this._cgosColor == WGo.W) m = -m;
				if (board._cgosColor == WGo.W) m *= -1;
				const x = j % board.size;
				const y = (j / board.size) | 0;
				const xo = board.getX(x);
				const yo = board.getY(y);
				const sr = board.stoneRadius * Math.abs(m) * 0.8;
				if (c == WGo.B) {
					if (m < 0) continue;
				} else {
					if (m > 0) continue;
				}
				this.context.fillRect(xo - sr, yo - sr, 2 * sr, 2 * sr);
			}
		}
	}
};

/**
 * Toggle cgos mode.
 */

export const CgosAnalysisContext = function (player, board) {
	this.player = player;
	this.board = board;
	this.cgosMode = false;

	this.showStats = true;
	this.showOwnership = true;
	this.showBlackWinrate = true;
	this.showBlackScore = true;
	this.showWhiteWinrate = true;
	this.showWhiteScore = true;

	this.ownershipLayer = new OwnershipLayer();
	this.board.addLayer(this.ownershipLayer, 400);
};

CgosAnalysisContext.prototype.set = function (set) {
	if (!this.cgosMode && set) {
		// register cgos listeners
		this._ev_move = this._ev_move || cgos_board_mouse_move.bind(this);
		this._ev_out = this._ev_out || cgos_board_mouse_out.bind(this);

		this.board.addEventListener("mousemove", this._ev_move);
		this.board.addEventListener("mouseout", this._ev_out);

		this.cgosMode = true;
	} else if (this.cgosMode && !set) {
		this.player.update(true);

		// remove cgos listeners
		this.board.removeEventListener("mousemove", this._ev_move);
		this.board.removeEventListener("mouseout", this._ev_out);

		this.cgosMode = false;
	}
};

const prepare_cgos_contol_dom = function (player) {
	this.iconBar = document.createElement("div");
	this.iconBar.className = "wgo-cgos-control-wrapper";
	this.element.appendChild(this.iconBar);

	let widget;

	for (const w in CgosControl.widgets) {
		widget = new CgosControl.widgets[w].constructor(
			player,
			CgosControl.widgets[w].args
		);
		widget.appendTo(this.iconBar);
		this.widgets.push(widget);
	}
};

export const CgosControl = WGo.extendClass(Component, function (player) {
	this.super(player);

	this.widgets = [];
	this.element.className = "wgo-player-cgos-control";

	prepare_cgos_contol_dom.call(this, player);
});
BasicPlayer.component.CgosControl = CgosControl;

CgosControl.prototype.updateDimensions = function () {
	if (this.element.clientWidth < 340)
		this.element.className = "wgo-player-control wgo-340";
	else if (this.element.clientWidth < 440)
		this.element.className = "wgo-player-control wgo-440";
	else this.element.className = "wgo-player-control";
};

CgosControl.widgets = [];

{
	/*
	Control.menu.push({
		constructor: MenuItem,
		args: {
			name: "cgos",
			togglable: true,
			click: function (player) {
				player._cgos.set(!player._cgos.cgosMode);
				return player._cgos.cgosMode;
			},
			init: function (player) {
				const _this = this;
				player._cgos =
					player._cgos ||
					new CgosAnalysisContext(player, player.board);
				player.addEventListener("frozen", function (e) {
					_this._disabled = _this.disabled;
					if (!_this.disabled) _this.disable();
				});
				player.addEventListener("unfrozen", function (e) {
					if (!_this._disabled) _this.enable();
					delete _this._disabled;
				});
				if (player._cgos.cgosMode) this.select();
				//player.addEventListener("update", update_board.bind(this));
			}
		}
	});
	*/

	const toggleHandler = function (prop) {
		return function (player) {
			player._cgos[prop] = !player._cgos[prop];
			player.update(true);
			return player._cgos[prop];
		};
	};

	const initHandler = function (prop) {
		return function (player) {
			player._cgos =
				player._cgos || new CgosAnalysisContext(player, player.board);
			if (player._cgos[prop]) this.select();
		};
	};

	const menuItems = [
		["cgos-stats", "showStats"],
		["cgos-ownership", "showOwnership"],
		["cgos-bwinrate", "showBlackWinrate"],
		["cgos-bscore", "showBlackScore"],
		["cgos-wwinrate", "showWhiteWinrate"],
		["cgos-wscore", "showWhiteScore"]
	];

	const widgets = [];
	for (const [name, prop] of menuItems) {
		widgets.push({
			constructor: Button,
			args: {
				name: name,
				togglable: true,
				click: toggleHandler(prop),
				init: initHandler(prop)
			}
		});
	}

	CgosControl.widgets.push({
		constructor: Group,
		args: { name: "cgos", widgets: widgets }
	});

	const bp_layouts = BasicPlayer.layouts;
	bp_layouts["right_top"].bottom.push("CgosControl");
	bp_layouts["right"].right.push("CgosControl");
	bp_layouts["one_column"].bottom.push("CgosControl");
	// bp_layouts["no_comment"].bottom.push("CgosControl");
	// bp_layouts["minimal"].bottom.push("CgosControl");
}

WGo.i18n.en["cgos"] = "CGOS mode";
WGo.i18n.en["cgos-stats"] = "Move stats overlay";
WGo.i18n.en["cgos-ownership"] = "Ownership overlay";
WGo.i18n.en["cgos-bwinrate"] = "Black winrate graph";
WGo.i18n.en["cgos-bscore"] = "Black score graph";
WGo.i18n.en["cgos-wwinrate"] = "White winrate graph";
WGo.i18n.en["cgos-wscore"] = "White score graph";

// CGOS variation overlay component.
// Displays CGOS analysis information on the board.

// basic updating function - handles board changes
const update_board = function (e) {
	// init array for new objects
	const add = [];

	// remove old markers from the board
	if (this._cgos && this._cgos.temp_marks) {
		this._cgos.board.removeObject(this._cgos.temp_marks);
		this._cgos.temp_marks = null;
	}
	this._cgos.board._cgosMode = false;
	if (!this._cgos || !this._cgos.cgosMode) {
		this._cgos.board.redraw();
		return;
	}
	this._cgos.board._cgosMode = true;
	this._cgos.board._cgosColor = 0;
	this._cgos.board._cgosOwnership = null;

	// genmove_analyze style comment
	if (e.node.CC && e.node.CC.length > 0) {
		const tokens = JSON.parse(e.node.CC);
		this._cgos.board._cgosColor = e.node.move.c;
		this._cgos.infoList = [];
		this._cgos.board._cgosOwnership = this._cgos.showOwnership
			? tokens.ownership
			: null;

		if (this._cgos.showStats && tokens.moves) {
			for (let j = 0; j < tokens.moves.length; j++) {
				const info = tokens.moves[j];
				let move = null;
				let winrate = null;
				let score = null;
				const pv = [];
				if (info.move) {
					move = parseCoord(this._cgos.board.size, info.move);
				}
				if (info.winrate) {
					winrate = info.winrate;
				}
				if (info.score) {
					score = info.score;
				}
				if (info.pv) {
					const moves = info.pv.split(" ");
					if (info.move && moves[0] != info.move) {
						moves.unshift(info.move);
					}
					for (let k = 0; k < moves.length; k++) {
						const m = parseCoord(this._cgos.board.size, moves[k]);
						if (m == null) break;
						pv.push(m);
					}
				}

				if (!move) continue;
				const o = {
					move: move,
					label: "[" + (this._cgos.infoList.length + 1) + "]",
					winrate: winrate,
					score: score,
					pv: pv
				};
				this._cgos.infoList.push(o);

				add.push({
					type: moveStatDrawer,
					winrate: o.winrate,
					score: o.score,
					x: o.move[0],
					y: o.move[1],
					c:
						this._cgos.board.theme.variationColor ||
						"rgba(0,32,128,0.8)"
				});
			}
		}
	}

	// add new markers on the board
	this._cgos.temp_marks = add;
	this._cgos.board.addObject(add);
	// XXX Redraw the entire board as garbage remains
	this._cgos.board.redraw();
};

const VariationOverlay = WGo.extendClass(Component, function (player) {
	this.super(player);

	player._cgos = this._cgos =
		player._cgos || new CgosAnalysisContext(player, player.board);
	const disabled =
		player.currentLayout.className.indexOf("wgo-small") >= 0 ||
		player.currentLayout.className.indexOf("wgo-xsmall") >= 0;
	player._cgos.set(!disabled);

	player.addEventListener("update", update_board.bind(this));
});

const bp_layouts = BasicPlayer.layouts;
bp_layouts["right_top"].bottom.push("VariationOverlay");
bp_layouts["right"].right.push("VariationOverlay");
bp_layouts["one_column"].top.push("VariationOverlay");
bp_layouts["no_comment"].top.push("VariationOverlay");

BasicPlayer.component.VariationOverlay = VariationOverlay;

// EvaluationGraphBox
//

const prepare_dom = function (player) {
	prepare_dom_box.call(this, "winrate", player);
	this.element.appendChild(this.winrate.box);
};

const WIDTH = 400;
const HEIGHT = 100;

function prepare_dom_box(type, player) {
	this[type] = {};
	const self = this;
	const t = this[type];

	const SVG = "http://www.w3.org/2000/svg";
	t.box = document.createElement("div");
	t.box.className = "wgo-box-wrapper wgo-player-wrapper wgo-" + type;

	t.graph = document.createElementNS(SVG, "svg");
	t.graph.setAttribute("viewBox", "-5 -5 410 110");
	t.graph.setAttribute("style", "background-color:#f0f0f0;");
	t.box.appendChild(t.graph);
	const pt = t.graph.createSVGPoint();
	t.graph.onclick = function (e) {
		pt.x = e.clientX;
		pt.y = e.clientY;
		const cursor = pt.matrixTransform(t.graph.getScreenCTM().inverse());
		const turn = (cursor.x / self.xScale) | 0;
		player.goTo(turn);
	};

	{
		const line = document.createElementNS(SVG, "line");
		line.setAttribute("x1", 0);
		line.setAttribute("y1", 50);
		line.setAttribute("x2", WIDTH);
		line.setAttribute("y2", 50);
		line.setAttribute("stroke", "#666666");
		line.setAttribute("stroke-width", 2);
		t.graph.appendChild(line);
	}

	for (let i = -30; i <= 30; i += 5) {
		const r = (-i / 40 + 0.5) * 100;
		const label = createLabel(
			(i == 0 ? "" : i > 0 ? "+" : "-") + Math.abs(i),
			WIDTH + 10,
			r,
			10,
			"#999999"
		);
		label.setAttribute("alignment-baseline", "middle");
		label.setAttribute("text-anchor", "end");
		t.graph.appendChild(label);
		if (i == 0) continue;
		const line = document.createElementNS(SVG, "line");
		line.setAttribute("x1", 0);
		line.setAttribute("y1", r);
		line.setAttribute("x2", WIDTH);
		line.setAttribute("y2", r);
		line.setAttribute("stroke", "#cccccc");
		line.setAttribute("stroke-width", 1);
		t.graph.appendChild(line);
	}

	const blackScore = document.createElementNS(SVG, "polyline");
	blackScore.setAttribute("points", "0,0 0,0");
	blackScore.setAttribute("stroke", "#ff6666");
	blackScore.setAttribute("stroke-width", 1);
	blackScore.setAttribute("fill", "none");
	t.blackScore = blackScore;
	t.graph.appendChild(blackScore);

	const whiteScore = document.createElementNS(SVG, "polyline");
	whiteScore.setAttribute("points", "0,0 0,0");
	whiteScore.setAttribute("stroke", "#66ff66");
	whiteScore.setAttribute("stroke-width", 1);
	whiteScore.setAttribute("fill", "none");
	t.whiteScore = whiteScore;
	t.graph.appendChild(whiteScore);

	const blackWinrate = document.createElementNS(SVG, "polyline");
	blackWinrate.setAttribute("points", "0,0 0,0");
	blackWinrate.setAttribute("stroke", "#ff0000");
	blackWinrate.setAttribute("stroke-width", 3);
	blackWinrate.setAttribute("fill", "none");
	t.blackWinrate = blackWinrate;
	t.graph.appendChild(blackWinrate);

	const whiteWinrate = document.createElementNS(SVG, "polyline");
	whiteWinrate.setAttribute("points", "0,0 0,0");
	whiteWinrate.setAttribute("stroke", "#006600");
	whiteWinrate.setAttribute("stroke-width", 3);
	whiteWinrate.setAttribute("fill", "none");
	t.whiteWinrate = whiteWinrate;
	t.graph.appendChild(whiteWinrate);

	const cursor = document.createElementNS(SVG, "rect");
	cursor.setAttribute("x", 0);
	cursor.setAttribute("y", 0);
	cursor.setAttribute("width", 1);
	cursor.setAttribute("height", 100);
	cursor.setAttribute("stroke", "#3333ff");
	cursor.setAttribute("fill", "none");
	t.cursor = cursor;
	t.graph.appendChild(cursor);

	function createLabel(str, x, y, fontSize, color, id) {
		const text = document.createElementNS(SVG, "text");
		text.setAttribute("x", x);
		text.setAttribute("y", y);
		text.setAttribute("font-size", fontSize ? fontSize : 10);
		// text.setAttribute('font-family', 'monospace');
		text.setAttribute("font-family", "Calibri, Tahoma, Arial");
		text.setAttribute("font-weight", "bold");
		if (color) {
			text.setAttribute("stroke", "none");
			text.setAttribute("fill", color);
		}
		if (id) {
			text.setAttribute("id", id);
		}
		text.textContent = str;
		return text;
	}

	// legends
	{
		const box = document.createElementNS(SVG, "rect");
		box.setAttribute("x", -10);
		box.setAttribute("y", -10);
		box.setAttribute("width", 150);
		box.setAttribute("height", 35);
		box.setAttribute("fill-opacity", "0.5");
		box.setAttribute("fill", "#ffffff");
		t.graph.appendChild(box);
	}

	{
		const box = document.createElementNS(SVG, "rect");
		box.setAttribute("x", -10);
		box.setAttribute("y", 75);
		box.setAttribute("width", 150);
		box.setAttribute("height", 110);
		box.setAttribute("fill-opacity", "0.5");
		box.setAttribute("fill", "#ffffff");
		t.graph.appendChild(box);
	}

	t.blackName = createLabel("B:", 0, 7, 15, "#cc0000", "legend-player-b");
	t.graph.appendChild(t.blackName);

	{
		t.graph.appendChild(createLabel("Score", 0, 20, 10, "#cc0000"));
		const blackScore = document.createElementNS(SVG, "polygon");
		blackScore.setAttribute("points", "30,20 60,20, 60,15 30,15");
		blackScore.setAttribute("stroke", "#ff6666");
		blackScore.setAttribute("stroke-width", 1);
		blackScore.setAttribute("fill", "none");
		t.graph.appendChild(blackScore);

		t.graph.appendChild(createLabel("Winrate", 70, 20, 10, "#cc0000"));
		const blackWinrate = document.createElementNS(SVG, "polyline");
		blackWinrate.setAttribute("points", "110,18 130,18");
		blackWinrate.setAttribute("stroke", "#ff0000");
		blackWinrate.setAttribute("stroke-width", 3);
		blackWinrate.setAttribute("fill", "none");
		t.graph.appendChild(blackWinrate);

		t.whiteName = createLabel(
			"W:",
			0,
			100,
			15,
			"#00cc00",
			"legend-player-w"
		);
		t.graph.appendChild(t.whiteName);

		t.graph.appendChild(createLabel("Score", 0, 85, 10, "#00cc00"));
		const whiteScore = document.createElementNS(SVG, "polygon");
		whiteScore.setAttribute("points", "30,85 60,85 60,80 30,80");
		whiteScore.setAttribute("stroke", "#66ff66");
		whiteScore.setAttribute("stroke-width", 1);
		whiteScore.setAttribute("fill", "none");
		t.graph.appendChild(whiteScore);

		t.graph.appendChild(createLabel("Winrate", 70, 85, 10, "#00cc00"));
		const whiteWinrate = document.createElementNS(SVG, "polyline");
		whiteWinrate.setAttribute("points", "110,83 130,83");
		whiteWinrate.setAttribute("stroke", "#006600");
		whiteWinrate.setAttribute("stroke-width", 3);
		whiteWinrate.setAttribute("fill", "none");
		t.graph.appendChild(whiteWinrate);
	}
}

function winrate(analysis) {
	if (analysis.winrate != undefined) return analysis.winrate * 100;
	if (
		analysis.moves != undefined &&
		analysis.moves.length > 0 &&
		analysis.moves[0].winrate
	)
		return analysis.moves[0].winrate * 100;
	return null;
}

function score(analysis) {
	let score;
	if (analysis.score != undefined) {
		score = analysis.score;
	} else if (
		analysis.moves != undefined &&
		analysis.moves.length > 0 &&
		analysis.moves[0].score
	) {
		score = analysis.moves[0].score;
	} else {
		return null;
	}
	let r = score / 40 + 0.5;
	if (r < 0) r = 0;
	if (r > 1) r = 1;
	return r * 100;
}

const kifu_loaded = function (e) {
	this.black = [];
	this.white = [];
	this.blackScore = [];
	this.whiteScore = [];

	for (let i = 0; i < e.kifu.nodeCount; i++) {
		this.black.push("");
		this.blackScore.push("");
		this.blackScore.push("");
		this.blackScore.push("");
		this.blackScore.push("");
		this.white.push("");
		this.whiteScore.push("");
		this.whiteScore.push("");
		this.whiteScore.push("");
		this.whiteScore.push("");
	}

	this.xScale = WIDTH / Math.max(100, e.kifu.nodeCount + 10);
	this.winrate.blackName.textContent = "B:  " + e.kifu.info.black.name;
	this.winrate.whiteName.textContent = "W:  " + e.kifu.info.white.name;
};

const update = function (e) {
	if (!e.node || !e.path || !e.path.m) return;
	let node = e.node;
	let turn = e.path.m;
	this.winrate.cursor.setAttribute("x", (turn - 1) * this.xScale);
	this.winrate.cursor.setAttribute("width", 3 * this.xScale);
	while (node) {
		if (!node.move || !node.CC) {
			node = node.parent;
			turn--;
			continue;
		}
		let winrateList, scoreList;
		if (node.move.c == WGo.B) {
			winrateList = this.black;
			scoreList = this.blackScore;
		} else {
			winrateList = this.white;
			scoreList = this.whiteScore;
		}

		const info = JSON.parse(node.CC);
		let rate = winrate(info);
		if (rate != null) {
			if (node.move.c == WGo.B) rate = 100 - rate;
			winrateList[turn] = turn * this.xScale + "," + rate;
		}
		let sc = score(info);
		if (sc != null) {
			if (node.move.c == WGo.B) sc = 100 - sc;
			scoreList[turn * 4] = turn * this.xScale + "," + 50;
			scoreList[turn * 4 + 1] = turn * this.xScale + "," + sc;
			scoreList[turn * 4 + 2] = (turn + 0.4) * this.xScale + "," + sc;
			scoreList[turn * 4 + 3] = (turn + 0.4) * this.xScale + "," + 50;
		}

		node = node.parent;
		turn--;
	}

	this.winrate.blackWinrate.setAttribute("points", this.black.join(" "));
	this.winrate.blackScore.setAttribute("points", this.blackScore.join(" "));
	this.winrate.whiteWinrate.setAttribute("points", this.white.join(" "));
	this.winrate.whiteScore.setAttribute("points", this.whiteScore.join(" "));

	if (this.player && this.player._cgos) {
		const f = this.player._cgos;
		this.winrate.blackWinrate.style.display = f.showBlackWinrate
			? ""
			: "none";
		this.winrate.blackScore.style.display = f.showBlackScore ? "" : "none";
		this.winrate.whiteWinrate.style.display = f.showWhiteWinrate
			? ""
			: "none";
		this.winrate.whiteScore.style.display = f.showWhiteScore ? "" : "none";
	}
};

const EvaluationGraphBox = WGo.extendClass(Component, function (player) {
	this.super(player);
	this.player = player;
	this.element.className = "wgo-analyzebox";

	prepare_dom.call(this, player);

	player.addEventListener("kifuLoaded", kifu_loaded.bind(this));
	player.addEventListener("update", update.bind(this));
});

bp_layouts["right_top"].bottom.push("EvaluationGraphBox");
//bp_layouts["right"].right.push("EvaluationGraphBox");
bp_layouts["one_column"].bottom.push("EvaluationGraphBox");
bp_layouts["no_comment"].bottom.push("EvaluationGraphBox");

BasicPlayer.component.EvaluationGraphBox = EvaluationGraphBox;
