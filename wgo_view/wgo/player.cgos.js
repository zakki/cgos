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

        if (args.score !== null) {
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

    // modifies grid layer too
    grid: {
      draw: function (args, board) {
        if (args.ownership && args.ownership.length > 0 && !args._nodraw) {
          for (var i = 0; i < board.size * board.size; i++) {
            var xo = board.getX(i % board.size);
            var yo = board.getY(Math.floor(i / board.size));
            sr = board.stoneRadius * Math.abs(args.ownership[i]);

            if (args.ownership[i] > 0) this.fillStyle = "rgba(0, 0, 0, 0.5)";
            else this.fillStyle = "rgba(255, 255, 255, 0.5)";
            this.fillRect(xo - sr, yo - sr, 2 * sr, 2 * sr);
          }
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
    if (e.node.comment && e.node.comment.length > 0) {
      var tokens = e.node.comment.split(" ");
      infoList = [];
      for (var i = 0; i < tokens.length; i++) {
        var token = tokens[i];
        if (token == "info") {
          infoList.push([]);
        }
        infoList[infoList.length - 1].push(token);
      }
      this._cgos.infoList = [];
      for (var j = 0; j < infoList.length; j++) {
        var info = infoList[j];
        var move = null;
        var winrate = null;
        var i = 0;
        var score = null;
        var pv = [];
        var ownership = [];
        while (i < info.length) {
          if (i >= info.length) break;
          var key = info[i];
          i++;
          var value = info[i];
          if (key == "move") {
            move = parseCoord(this._cgos.board.size, value);
            i++;
          } else if (key == "winrate") {
            winrate = parseFloat(value);
            i++;
          } else if (key == "scoreMean") {
            score = parseFloat(value);
            i++;
          } else if (key == "pv") {
            while (i < info.length) {
              var m = parseCoord(this._cgos.board.size, info[i]);
              if (m == null) break;
              pv.push(m);
              i++;
            }
          } else if (key == "ownership") {
            while (i < info.length) {
              var m = parseFloat(info[i]);
              if (Number.isNaN(m)) break;
              if (e.node.move.c == WGo.W) m *= -1;
              ownership.push(m);
              i++;
            }
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
          ownership: ownership,
          c: this._cgos.board.theme.variationColor || "rgba(0,32,128,0.8)",
        });
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

  var prepare_dom = function () {
    prepare_dom_box.call(this, "winrate");
    this.element.appendChild(this.winrate.box);
  };

  var prepare_dom_box = function (type) {
    this[type] = {};
    var t = this[type];
    t.box = document.createElement("div");
    t.box.className = "wgo-box-wrapper wgo-player-wrapper wgo-" + type;

    t.graph = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    t.graph.setAttribute("width", "490");
    t.graph.setAttribute("height", "100");
    t.graph.setAttribute("viewbox", "-5 -5 410 110");
    t.graph.setAttribute("style", "background-color:#cccccc;");
    t.box.appendChild(t.graph);

    var line = document.createElementNS("http://www.w3.org/2000/svg", "rect");
    line.setAttribute("x", 0);
    line.setAttribute("y", 0);
    line.setAttribute("width", 490);
    line.setAttribute("height", 50);
    line.setAttribute("stroke", "#666666");
    line.setAttribute("fill", "#336633");
    t.graph.appendChild(line);

    var line = document.createElementNS("http://www.w3.org/2000/svg", "rect");
    line.setAttribute("x", 0);
    line.setAttribute("y", 50);
    line.setAttribute("width", 490);
    line.setAttribute("height", 50);
    line.setAttribute("stroke", "#666666");
    line.setAttribute("fill", "#99cc99");
    t.graph.appendChild(line);

    var line = document.createElementNS("http://www.w3.org/2000/svg", "line");
    line.setAttribute("x1", 0);
    line.setAttribute("y1", 50);
    line.setAttribute("x2", 490);
    line.setAttribute("y2", 50);
    line.setAttribute("stroke", "#666666");
    line.setAttribute("stroke-width", 2);
    t.graph.appendChild(line);

    var blackWinrate = document.createElementNS(
      "http://www.w3.org/2000/svg",
      "polyline"
    );
    blackWinrate.setAttribute("points", "0,0 0,0");
    blackWinrate.setAttribute("stroke", "#330000");
    blackWinrate.setAttribute("stroke-width", 3);
    blackWinrate.setAttribute("fill", "none");
    t.blackWinrate = blackWinrate;
    t.graph.appendChild(blackWinrate);

    var whiteWinrate = document.createElementNS(
      "http://www.w3.org/2000/svg",
      "polyline"
    );
    whiteWinrate.setAttribute("points", "0,0 0,0");
    whiteWinrate.setAttribute("stroke", "#ccccff");
    whiteWinrate.setAttribute("stroke-width", 3);
    whiteWinrate.setAttribute("fill", "none");
    t.whiteWinrate = whiteWinrate;
    t.graph.appendChild(whiteWinrate);
  };

  function winrate(str) {
    var tokens = str.split(" ");
    for (var i = 0; i < tokens.length; i++) {
      if (tokens[i] == "winrate") {
        var r = parseFloat(tokens[i + 1]);
        if (r == +r && r > 1) r /= 10000;
        return r * 100;
      }
    }
    return null;
  }

  var kifu_loaded = function (e) {
    var info = e.kifu.info || {};

    this.black = [];
    this.white = [];
  };

  var update = function (e) {
    var list, graph;
    if (!e.node || !e.node.move || !e.path || !e.node.comment) return;
    if (e.node.move.c == WGo.B) {
      list = this.black;
      graph = this.winrate.blackWinrate;
    } else {
      list = this.white;
      graph = this.winrate.whiteWinrate;
    }
    while (e.path.m >= list.length) {
      list.push("");
    }
    rate = winrate(e.node.comment);
    if (rate != null) {
      if (e.node.move.c == WGo.B) rate = 100 - rate;
      list[e.path.m] = e.path.m + "," + rate;
      graph.setAttribute("points", list.join(" "));
    }
  };

  var AnalyzeBox = WGo.extendClass(
    WGo.BasicPlayer.component.Component,
    function (player) {
      this.super(player);
      this.element.className = "wgo-analyzebox";

      prepare_dom.call(this);

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
