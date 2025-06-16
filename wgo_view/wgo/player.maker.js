/**
 * Originally created by larry https://github.com/larryclean/wgo.js/tree/marker
 * Created by larry on 2016/12/30.
 * display marks move in board
 */
import { WGo } from "./wgo";

import { Player } from "./player";
import { BasicPlayer } from "./basicplayer";
import { Component } from "./basicplayer.component";
import { Control, MenuItem, Button, Group } from "./basicplayer.control";

/*
 *  add solid triangle for show
 */
WGo.Board.drawHandlers["TRS"] = {
	stone: {
		draw: function (args, board) {
			const xr = board.getX(args.x),
				yr = board.getY(args.y),
				sr = board.stoneRadius;

			//this.strokeStyle ="red";// args.c || get_markup_color(board, args.x, args.y);
			//this.lineWidth = args.lineWidth || board.lineWidth || 1;
			this.fillStyle = "#FF0000";
			this.beginPath();
			this.moveTo(xr - 0.5, yr - 0.5 - Math.round(sr / 2));
			this.lineTo(
				Math.round(xr - sr / 2) - 0.5,
				Math.round(yr + sr / 3) + 0.5
			);
			this.lineTo(
				Math.round(xr + sr / 2) + 0.5,
				Math.round(yr + sr / 3) + 0.5
			);
			this.closePath();
			this.fill();
			//this.stroke();
		}
	}
};

const defConfig = {
	markerStyle: "TRS", //display style
	markerNum: 1, // Set to specify how many items should be displayed at once. from back to front
	lastMoveColor: "red"
};

export const Marker = function (player, board, config) {
	this.player = player;
	this.board = board;
	this.config = config || {};
	for (const key in defConfig)
		if (this.config[key] === undefined && defConfig[key] !== undefined)
			this.config[key] = defConfig[key];
	this.init();
};

Marker.prototype = {
	init: function () {
		this._bindEvent();
	},
	clearDefaultSytle: function () {
		const node = this.player.kifuReader.node;
		if (node.move) {
			this.board.removeObject({
				x: node.move.x,
				y: node.move.y,
				type: "CR"
			});
		}
	},
	_bindEvent: function () {
		const self = this;
		this.player.addEventListener("update", function (e) {
			self.showMarker(e);
		});
	},
	clearMarker: function () {
		if (!this.lbs) return;
		for (let i = 0; i < this.lbs.length; i++) {
			this.board.removeObject(this.lbs[i]);
		}
	},
	switchMaker: function (config) {
		this.clearMarker();
		for (const key in config) this.config[key] = config[key];
		this.showMarker({
			position: this.player.kifuReader.game.getPosition()
		});
	},
	showMarker: function (e) {
		this.clearMarker();
		this.lbs = [];
		const poss = new WGo.Position(this.player.kifu.size);
		const clonePos = e.position.clone();
		let num = this.player.kifuReader.path.m;
		let node = this.player.kifuReader.node;
		let step = 0;
		while (
			node.move &&
			(step < this.config.markerNum || this.config.markerNum == 0)
		) {
			const x = node.move.x;
			const y = node.move.y;
			if (clonePos.get(x, y) && poss.get(x, y) == 0) {
				poss.set(x, y, num);
				if (step == 0) {
					this.lbs.push({
						x: x,
						y: y,
						text: num,
						c: this.config.lastMoveColor,
						type: this.config.markerStyle
					});
				} else {
					this.lbs.push({
						x: x,
						y: y,
						text: num,
						type: this.config.markerStyle
					});
				}
			}
			num--;
			step++;
			node = node.parent;
		}
		for (let i = 0; i < this.lbs.length; i++) {
			this.board.addObject(this.lbs[i]);
		}
	}
};

Player.Marker = Marker;
if (Control) {
	Control.menu.push({
		constructor: MenuItem,
		args: {
			name: "switchmarker",
			togglable: true,
			click: function (player) {
				this._marker = this._marker || new Marker(player, player.board);
				if (!this._isFirst) {
					player.config.markLastMove = false;
					this._marker.clearDefaultSytle();
					this._marker.switchMaker();
					this._isFirst = true;
				} else if (
					this._marker.config.markerStyle == "LB" &&
					this._marker.config.markerNum != 0
				) {
					this._marker.switchMaker({
						markerNum: 0
					});
				} else if (
					this._marker.config.markerStyle == "LB" &&
					this._marker.config.markerNum == 0
				) {
					this._marker.switchMaker({
						markerStyle: "TRS",
						markerNum: 1
					});
				} else {
					this._marker.switchMaker({
						markerStyle: "LB",
						markerNum: 5
					});
				}
			}
		}
	});
}

WGo.i18n.en["switchmarker"] = "Switch Marker";
