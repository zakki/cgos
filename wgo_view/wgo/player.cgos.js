(function (WGo) {
  // board mousemove callback for cgos move - adds highlighting
  var cgos_board_mouse_move = function (x, y) {
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
    var game = this.player.kifuReader.game;
    if (x != -1 && y != -1) {
      for (var i = 0; i < this.infoList.length; i++) {
        var o = this.infoList[i];
        if (o.move[0] != x || o.move[1] != y) continue;
        this._last_mark = o.pv.flatMap(function (m, i) {
          var turn = i % 2 == 0 ? -game.turn : game.turn;
          return [
            {
              type: "MONO",
              x: m[0],
              y: m[1],
              c: turn,
            },
            {
              type: "LB",
              text: "" + (i + 1),
              x: m[0],
              y: m[1],
              c: turn == WGo.B ? "white" : "black",
            },
          ];
        });
        this.board.addObject(this._last_mark);
      }
    } else {
      delete this._last_mark;
    }
  };

  // board mouseout callback for cgos move
  var cgos_board_mouse_out = function () {
    if (this._last_mark) {
      this.board.removeObject(this._last_mark);
      delete this._last_mark;
      delete this._lastX;
      delete this._lastY;
    }
  };

  var theme_variable = function (key, board) {
    return typeof board.theme[key] == "function"
      ? board.theme[key](board)
      : board.theme[key];
  };

  var cgosDrawer = {
    stone: {
      draw: function (args, board) {
        var xr = board.getX(args.x),
          yr = board.getY(args.y),
          sr = board.stoneRadius * 0.8,
          font = args.font || theme_variable("font", board) || "";

        this.fillStyle = "#333333";

        var text = args.label;
        if (args.winrate !== null) text = (args.winrate * 100).toFixed(1);

        if (text != null) {
          if (text.length == 1) this.font = Math.round(sr * 1.5) + "px " + font;
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

        if (args.score != null) {
          var text = args.score.toFixed(1);
          if (text.length == 1) this.font = Math.round(sr * 1.5) + "px " + font;
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
      },
    },
  }
  var cgosOwnershipDrawer = {
    // modifies grid layer too
    grid: {
      draw: function (args, board) {
        if (args.ownership != null && !args._nodraw) {
          var xo = board.getX(args.x);
          var yo = board.getY(args.y);
          var sr = board.stoneRadius * 0.8;
          var sr = board.stoneRadius * Math.abs(args.ownership) * 0.8;
          if (args.ownership > 0) this.fillStyle = "rgba(0, 0, 0, 0.5)";
          else this.fillStyle = "rgba(255, 255, 255, 0.5)";
          this.fillRect(xo - sr, yo - sr, 2 * sr, 2 * sr);
        }
      },
      clear: function (args, board) {
        args._nodraw = true;
        WGo.redraw_layer(board, "grid");
        delete args._nodraw;
      },
    },
  };

  // basic updating function - handles board changes
  var update_board = function (e) {
    // init array for new objects
    var add = [];

    // remove old markers from the board
    if (this._cgos && this._cgos.temp_marks) {
      this._cgos.board.removeObject(this._cgos.temp_marks);
      this._cgos.temp_marks = null;
    }
    if (!this._cgos || !this._cgos.cgosMode) return;

    // genmove_analyze style comment
    if (e.node.CC && e.node.CC.length > 0) {
      var tokens = JSON.parse(e.node.CC);
      this._cgos.infoList = [];

      if (tokens.ownership) {
        var CHARS = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";
        for (var j = 0; j < tokens.ownership.length; j++) {
          var m = CHARS.indexOf(tokens.ownership[j]);
          if (m < 0) break;
          m = m / 62 * 2 - 1.0;
          if (e.node.move.c == WGo.W) m *= -1;
          add.push({
            type: cgosOwnershipDrawer,
            x: j % this._cgos.board.size,
            y: (j / this._cgos.board.size) | 0,
            ownership: m,
          });
        }
      }

      if (tokens.moves) {
        for (var j = 0; j < tokens.moves.length; j++) {
          var info = tokens.moves[j];
          var move = null;
          var winrate = null;
          var score = null;
          var pv = [];
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
            var moves = info.pv.split(" ");
            if (info.move && moves[0] != info.move) {
              moves.unshift(info.move)
            }
            for (var k = 0; k < moves.length; k++) {
              var m = parseCoord(this._cgos.board.size, moves[k]);
              if (m == null) break;
              pv.push(m);
            }
          }

          if (!move) continue;
          var o = {
            move: move,
            label: "[" + (this._cgos.infoList.length + 1) + "]",
            winrate: winrate,
            score: score,
            pv: pv,
          };
          this._cgos.infoList.push(o);

          add.push({
            type: cgosDrawer,
            winrate: o.winrate,
            score: o.score,
            x: o.move[0],
            y: o.move[1],
            c: this._cgos.board.theme.variationColor || "rgba(0,32,128,0.8)",
          });
        }
      }
    }

    // add new markers on the board
    this._cgos.temp_marks = add;
    this._cgos.board.addObject(add);
  };

  function parseCoord(size, str) {
    str = str.toLowerCase();
    var LEGAL_COORDINATES = "abcdefghjklmnopqrstuvwxyz";
    var x = LEGAL_COORDINATES.indexOf(str[0]);
    if (x < 0) return null;
    var y = parseInt(str.substr(1));
    if (Number.isNaN(y)) return null;
    return [x, size - y];
  }

  var winrateGraph = {
    // draw on grid layer
    grid: {
      draw: function (args, board) {
        var ch, t, xright, xleft, ytop, ybottom;

        this.fillStyle = "rgba(0,0,0,0.7)";
        this.textBaseline = "middle";
        this.textAlign = "center";
        this.font = board.stoneRadius + "px " + (board.font || "");

        xright = board.getX(-0.75);
        xleft = board.getX(board.size - 0.25);
        ytop = board.getY(-0.75);
        ybottom = board.getY(board.size - 0.25);

        for (var i = 0; i < board.size; i++) {
          ch = i + "A".charCodeAt(0);
          if (ch >= "I".charCodeAt(0)) ch++;

          t = board.getY(i);
          this.fillText(board.size - i, xright, t);
          this.fillText(board.size - i, xleft, t);

          t = board.getX(i);
          this.fillText(String.fromCharCode(ch), t, ytop);
          this.fillText(String.fromCharCode(ch), t, ybottom);
        }

        this.fillStyle = "black";
      },
    },
  };

  WGo.Player.Cgos = {};

  /**
   * Toggle cgos mode.
   */

  WGo.Player.Cgos = function (player, board) {
    this.player = player;
    this.board = board;
    this.cgosMode = false;
  };

  WGo.Player.Cgos.prototype.setGraph = function (b) {
    if (!this.coordinates && b) {
      this.board.setSection(-0.5, -0.5, -0.5, -10.5);
      this.board.addCustomObject(winrateGraph);
    } else if (this.coordinates && !b) {
      this.board.setSection(0, 0, 0, 0);
      this.board.removeCustomObject(winrateGraph);
    }
    this.graph = b;
  };

  WGo.Player.Cgos.prototype.set = function (set) {
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
    // this.setGraph(this.cgosMode)
  };

  if (WGo.BasicPlayer && WGo.BasicPlayer.component.Control) {
    WGo.BasicPlayer.component.Control.menu.push({
      constructor: WGo.BasicPlayer.control.MenuItem,
      args: {
        name: "cgos",
        togglable: true,
        click: function (player) {
          this._cgos = this._cgos || new WGo.Player.Cgos(player, player.board);
          this._cgos.set(!this._cgos.cgosMode);
          return this._cgos.cgosMode;
        },
        init: function (player) {
          var _this = this;
          player.addEventListener("frozen", function (e) {
            _this._disabled = _this.disabled;
            if (!_this.disabled) _this.disable();
          });
          player.addEventListener("unfrozen", function (e) {
            if (!_this._disabled) _this.enable();
            delete _this._disabled;
          });
          player.addEventListener("update", update_board.bind(this));
        },
      },
    });
  }

  WGo.i18n.en["cgos"] = "CGOS mode";
})(WGo);

(function () {
  "use strict";

  var prepare_dom = function (player) {
    prepare_dom_box.call(this, "winrate", player);
    this.element.appendChild(this.winrate.box);
  };

  var WIDTH = 490;

  var prepare_dom_box = function (type, player) {
    this[type] = {};
    var self = this;
    var t = this[type];
    var SVG = "http://www.w3.org/2000/svg";
    t.box = document.createElement("div");
    t.box.className = "wgo-box-wrapper wgo-player-wrapper wgo-" + type;

    t.graph = document.createElementNS(SVG, "svg");
    t.graph.setAttribute("width", WIDTH);
    t.graph.setAttribute("height", "100");
    t.graph.setAttribute("viewbox", "-5 -5 410 110");
    t.graph.setAttribute("style", "background-color:#cccccc;");
    t.box.appendChild(t.graph);
    t.graph.onclick = function (e) {
      var turn = (e.offsetX / self.xScale) | 0;
      player.goTo(turn);
    }

    var line = document.createElementNS(SVG, "line");
    line.setAttribute("x1", 0);
    line.setAttribute("y1", 50);
    line.setAttribute("x2", WIDTH);
    line.setAttribute("y2", 50);
    line.setAttribute("stroke", "#666666");
    line.setAttribute("stroke-width", 2);
    t.graph.appendChild(line);

    var blackScore = document.createElementNS(SVG, "polyline");
    blackScore.setAttribute("points", "0,0 0,0");
    blackScore.setAttribute("stroke", "#993300");
    blackScore.setAttribute("stroke-width", 1);
    blackScore.setAttribute("fill", "none");
    t.blackScore = blackScore;
    t.graph.appendChild(blackScore);

    var whiteScore = document.createElementNS(SVG, "polyline");
    whiteScore.setAttribute("points", "0,0 0,0");
    whiteScore.setAttribute("stroke", "#009900");
    whiteScore.setAttribute("stroke-width", 1);
    whiteScore.setAttribute("fill", "none");
    t.whiteScore = whiteScore;
    t.graph.appendChild(whiteScore);

    var blackWinrate = document.createElementNS(SVG, "polyline");
    blackWinrate.setAttribute("points", "0,0 0,0");
    blackWinrate.setAttribute("stroke", "#ffaa00");
    blackWinrate.setAttribute("stroke-width", 3);
    blackWinrate.setAttribute("fill", "none");
    t.blackWinrate = blackWinrate;
    t.graph.appendChild(blackWinrate);

    var whiteWinrate = document.createElementNS(SVG, "polyline");
    whiteWinrate.setAttribute("points", "0,0 0,0");
    whiteWinrate.setAttribute("stroke", "#33ff33");
    whiteWinrate.setAttribute("stroke-width", 3);
    whiteWinrate.setAttribute("fill", "none");
    t.whiteWinrate = whiteWinrate;
    t.graph.appendChild(whiteWinrate);

    var cursor = document.createElementNS(SVG, "rect");
    cursor.setAttribute("x", 0);
    cursor.setAttribute("y", 0);
    cursor.setAttribute("width", 1);
    cursor.setAttribute("height", 100);
    cursor.setAttribute("stroke", "#3333ff");
    cursor.setAttribute("fill", "none");
    t.cursor = cursor;
    t.graph.appendChild(cursor);

    function createLabel(name, x, y) {
      var text = document.createElementNS(SVG, "text");
      text.setAttribute('x', x);
      text.setAttribute('y', y);
      text.setAttribute('font-size', 10);
      text.setAttribute('font-family', 'monospace');
      text.textContent = name;
      return text;
    }
    // legends
    var blackScore = document.createElementNS(SVG, "polygon");
    blackScore.setAttribute("points", "450,10 480,10, 480,5 450,5");
    blackScore.setAttribute("stroke", "#993300");
    blackScore.setAttribute("stroke-width", 1);
    blackScore.setAttribute("fill", "none");
    t.graph.appendChild(blackScore);
    t.graph.appendChild(createLabel('B Score', 400, 10));

    var whiteScore = document.createElementNS(SVG, "polygon");
    whiteScore.setAttribute("points", "450,20 480,20 480,15 450,15");
    whiteScore.setAttribute("stroke", "#009900");
    whiteScore.setAttribute("stroke-width", 1);
    whiteScore.setAttribute("fill", "none");
    t.graph.appendChild(whiteScore);
    t.graph.appendChild(createLabel('W Score', 400, 20));

    var blackWinrate = document.createElementNS(SVG, "polyline");
    blackWinrate.setAttribute("points", "450,25 480,25");
    blackWinrate.setAttribute("stroke", "#ffaa00");
    blackWinrate.setAttribute("stroke-width", 3);
    blackWinrate.setAttribute("fill", "none");
    t.graph.appendChild(blackWinrate);
    t.graph.appendChild(createLabel('B Winrate', 400, 30));

    var whiteWinrate = document.createElementNS(SVG, "polyline");
    whiteWinrate.setAttribute("points", "450,35 480,35");
    whiteWinrate.setAttribute("stroke", "#33ff33");
    whiteWinrate.setAttribute("stroke-width", 3);
    whiteWinrate.setAttribute("fill", "none");
    t.graph.appendChild(whiteWinrate);
    t.graph.appendChild(createLabel('W Winrate', 400, 40));
  };

  function winrate(analysis) {
    if (analysis.winrate != undefined)
      return analysis.winrate * 100;
    if (analysis.moves != undefined && analysis.moves[0].winrate)
      return analysis.moves[0].winrate * 100;
    return null;
  }

  function score(analysis) {
    var score;
    if (analysis.score != undefined) {
      score = analysis.score;
    } else if (analysis.moves != undefined && analysis.moves[0].score) {
      score = analysis.moves[0].score;
    } else {
      return null;
    }
    var r = (score / 40 + 0.5);
    if (r < 0)
      r = 0;
    if (r > 1)
      r = 1;
    return r * 100;
  }

  var kifu_loaded = function (e) {
    var info = e.kifu.info || {};

    this.black = [];
    this.white = [];
    this.blackScore = [];
    this.whiteScore = [];

    for (var i = 0; i < e.kifu.nodeCount; i++) {
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

    this.xScale = WIDTH / Math.max(100, e.kifu.nodeCount + 10)
  };

  var update = function (e) {
    if (!e.node || !e.path || !e.path.m)
      return;
    var node = e.node;
    var turn = e.path.m;
    this.winrate.cursor.setAttribute("x", (turn - 1) * this.xScale);
    this.winrate.cursor.setAttribute("width", 3 * this.xScale);
    while (node) {
      var winrateList, scoreList, winrateGraph, scoreGraph;
      if (!node.move || !node.CC) return;
      if (node.move.c == WGo.B) {
        winrateList = this.black;
        scoreList = this.blackScore;
        winrateGraph = this.winrate.blackWinrate;
        scoreGraph = this.winrate.blackScore;
      } else {
        winrateList = this.white;
        scoreList = this.whiteScore;
        winrateGraph = this.winrate.whiteWinrate;
        scoreGraph = this.winrate.whiteScore;
      }

      var info = JSON.parse(node.CC);
      var rate = winrate(info);
      if (rate != null) {
        if (node.move.c == WGo.B)
          rate = 100 - rate;
        winrateList[turn] = turn * this.xScale + "," + rate;
        winrateGraph.setAttribute("points", winrateList.join(" "));
      }
      var sc = score(info);
      if (sc != null) {
        if (node.move.c == WGo.B)
          sc = 100 - sc;
        scoreList[turn*4]   = turn * this.xScale + "," + 50;
        scoreList[turn*4+1] = turn * this.xScale + "," + sc;
        scoreList[turn*4+2] = (turn + 0.4) * this.xScale + "," + sc;
        scoreList[turn*4+3] = (turn + 0.4) * this.xScale + "," + 50;
        scoreGraph.setAttribute("points", scoreList.join(" "));
      }

      node = node.parent;
      turn--;
    }
  };

  var AnalyzeBox = WGo.extendClass(
    WGo.BasicPlayer.component.Component,
    function (player) {
      this.super(player);
      this.element.className = "wgo-analyzebox";

      prepare_dom.call(this, player);

      player.addEventListener("kifuLoaded", kifu_loaded.bind(this));
      player.addEventListener("update", update.bind(this));
    }
  );

  var bp_layouts = WGo.BasicPlayer.layouts;
  if (!bp_layouts["right_top"].bottom) bp_layouts["right_top"].bottom = [];
  bp_layouts["right_top"].bottom.push("AnalyzeBox");
  //bp_layouts["right"].right.push("AnalyzeBox");
  //bp_layouts["one_column"].top.push("AnalyzeBox");
  //bp_layouts["no_comment"].top.push("AnalyzeBox");

  WGo.BasicPlayer.component.AnalyzeBox = AnalyzeBox;
})(WGo);
