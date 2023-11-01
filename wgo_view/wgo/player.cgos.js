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

  OwnershipLayer = WGo.extendClass(WGo.Board.CanvasLayer, function() {
    this.super.call(this);
  });

  OwnershipLayer.prototype.draw = function(board) {
    if (!board._cgosMode)
      return;
    if (board._cgosOwnership) {
      var CHARS = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";
      var COLORS = [WGo.B, WGo.W];
      for (var i = 0; i < 2; i++) {
        var c = COLORS[i];
        if (c === WGo.B)
          this.context.fillStyle = "rgba(0, 0, 0, 0.5)";
        else
          this.context.fillStyle = "rgba(255, 255, 255, 0.5)";

        for (var j = 0; j < board._cgosOwnership.length; j++) {
          var m = CHARS.indexOf(board._cgosOwnership[j]);
          if (m < 0) break;
          m = m / 62 * 2 - 1.0;
          if (this._cgosColor == WGo.W)
            m = -m;
          if (board._cgosColor == WGo.W) m *= -1;
          var x =  j % board.size;
          var y = (j / board.size) | 0;
          var xo = board.getX(x);
          var yo = board.getY(y);
          var sr = board.stoneRadius * 0.8;
          var sr = board.stoneRadius * Math.abs(m) * 0.8;
          if (c == WGo.B) {
            if (m < 0) continue;
          } else {
            if (m > 0) continue;
          }
          this.context.fillRect(xo - sr, yo - sr, 2 * sr, 2 * sr);
        }
      }
    }
  }

  // basic updating function - handles board changes
  var update_board = function (e) {
    // init array for new objects
    var add = [];

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
      var tokens = JSON.parse(e.node.CC);
      this._cgos.board._cgosColor = e.node.move.c;
      this._cgos.infoList = [];
      this._cgos.board._cgosOwnership = tokens.ownership;

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
    // XXX Redraw the entire board as garbage remains
    this._cgos.board.redraw();
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

    this.ownershipLayer = new OwnershipLayer();
    this.board.addLayer(this.ownershipLayer, 400);
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
          player._cgos = player._cgos || new WGo.Player.Cgos(player, player.board);
          player._cgos.set(!player._cgos.cgosMode);
          return player._cgos.cgosMode;
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
          if (player._cgos.cgosMode)
            this.select();
          //player.addEventListener("update", update_board.bind(this));
        },
      },
    });
  }

  WGo.i18n.en["cgos"] = "CGOS mode";

  var AnalyzeBoard = WGo.extendClass(
    WGo.BasicPlayer.component.Component,
    function (player) {
      this.super(player);

      player._cgos = this._cgos || new WGo.Player.Cgos(player, player.board);
      var disabled = player.currentLayout.className.indexOf("wgo-small") >= 0 ||
        player.currentLayout.className.indexOf("wgo-xsmall") >= 0;
      player._cgos.set(!disabled);

      player.addEventListener("update", update_board.bind(player));
    }
  );

  var bp_layouts = WGo.BasicPlayer.layouts;
  if (!bp_layouts["right_top"].bottom) bp_layouts["right_top"].bottom = [];
  bp_layouts["right_top"].bottom.push("AnalyzeBoard");
  bp_layouts["right"].right.push("AnalyzeBoard");
  bp_layouts["one_column"].top.push("AnalyzeBoard");
  bp_layouts["no_comment"].top.push("AnalyzeBoard");


  WGo.BasicPlayer.component.AnalyzeBoard = AnalyzeBoard;

})(WGo);

(function () {
  "use strict";

  var prepare_dom = function (player) {
    prepare_dom_box.call(this, "winrate", player);
    this.element.appendChild(this.winrate.box);
  };

  var WIDTH = 400;
  var HEIGHT = 100;

  var prepare_dom_box = function (type, player) {
    this[type] = {};
    var self = this;
    var t = this[type];

    var SVG = "http://www.w3.org/2000/svg";
    t.box = document.createElement("div");
    t.box.className = "wgo-box-wrapper wgo-player-wrapper wgo-" + type;

    t.graph = document.createElementNS(SVG, "svg");
    t.graph.setAttribute("viewBox", "-5 -5 410 110");
    t.graph.setAttribute("style", "background-color:#f0f0f0;");
    t.box.appendChild(t.graph);
    var pt = t.graph.createSVGPoint();
    t.graph.onclick = function (e) {
      pt.x = e.clientX;
      pt.y = e.clientY;
      var cursor = pt.matrixTransform(t.graph.getScreenCTM().inverse());
      var turn = (cursor.x / self.xScale) | 0;
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
    blackScore.setAttribute("stroke", "#ff6666");
    blackScore.setAttribute("stroke-width", 1);
    blackScore.setAttribute("fill", "none");
    t.blackScore = blackScore;
    t.graph.appendChild(blackScore);

    var whiteScore = document.createElementNS(SVG, "polyline");
    whiteScore.setAttribute("points", "0,0 0,0");
    whiteScore.setAttribute("stroke", "#66ff66");
    whiteScore.setAttribute("stroke-width", 1);
    whiteScore.setAttribute("fill", "none");
    t.whiteScore = whiteScore;
    t.graph.appendChild(whiteScore);

    var blackWinrate = document.createElementNS(SVG, "polyline");
    blackWinrate.setAttribute("points", "0,0 0,0");
    blackWinrate.setAttribute("stroke", "#ff0000");
    blackWinrate.setAttribute("stroke-width", 3);
    blackWinrate.setAttribute("fill", "none");
    t.blackWinrate = blackWinrate;
    t.graph.appendChild(blackWinrate);

    var whiteWinrate = document.createElementNS(SVG, "polyline");
    whiteWinrate.setAttribute("points", "0,0 0,0");
    whiteWinrate.setAttribute("stroke", "#006600");
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
      text.classList.add("legend");
      text.setAttribute('x', x);
      text.setAttribute('y', y);
      text.setAttribute('font-size', 10);
      text.setAttribute('font-family', 'monospace');
      text.textContent = name;
      return text;
    }
    // legends
    var blackScore = document.createElementNS(SVG, "polygon");
    blackScore.classList.add("legend");
    blackScore.setAttribute("points", "50,10 80,10, 80,5 50,5");
    blackScore.setAttribute("stroke", "#ff6666");
    blackScore.setAttribute("stroke-width", 1);
    blackScore.setAttribute("fill", "none");
    t.graph.appendChild(blackScore);
    t.graph.appendChild(createLabel('B Score', 0, 10));

    var whiteScore = document.createElementNS(SVG, "polygon");
    whiteScore.classList.add("legend");
    whiteScore.setAttribute("points", "50,20 80,20 80,15 50,15");
    whiteScore.setAttribute("stroke", "#66ff66");
    whiteScore.setAttribute("stroke-width", 1);
    whiteScore.setAttribute("fill", "none");
    t.graph.appendChild(whiteScore);
    t.graph.appendChild(createLabel('W Score', 0, 20));

    var blackWinrate = document.createElementNS(SVG, "polyline");
    blackWinrate.classList.add("legend");
    blackWinrate.setAttribute("points", "50,25 80,25");
    blackWinrate.setAttribute("stroke", "#ff0000");
    blackWinrate.setAttribute("stroke-width", 3);
    blackWinrate.setAttribute("fill", "none");
    t.graph.appendChild(blackWinrate);
    t.graph.appendChild(createLabel('B Winrate', 0, 30));

    var whiteWinrate = document.createElementNS(SVG, "polyline");
    whiteWinrate.classList.add("legend");
    whiteWinrate.setAttribute("points", "50,35 80,35");
    whiteWinrate.setAttribute("stroke", "#006600");
    whiteWinrate.setAttribute("stroke-width", 3);
    whiteWinrate.setAttribute("fill", "none");
    t.graph.appendChild(whiteWinrate);
    t.graph.appendChild(createLabel('W Winrate', 0, 40));

    var text;
    text = document.createElementNS(SVG, "text");
    text.classList.add("large-info");
    text.setAttribute('x', 80);
    text.setAttribute('y', 25);
    text.setAttribute('font-size', 50);
    text.setAttribute('dominant-baseline', 'middle');
    text.setAttribute('text-anchor', 'middle');
    text.textContent = "--";
    t.largeWinRateW = text;
    t.graph.appendChild(text);

    text = document.createElementNS(SVG, "text");
    text.classList.add("large-info");
    text.setAttribute('x', 80);
    text.setAttribute('y', 75);
    text.setAttribute('font-size', 50);
    text.setAttribute('dominant-baseline', 'middle');
    text.setAttribute('text-anchor', 'middle');
    text.textContent = "--";
    t.largeScoreW = text;
    t.graph.appendChild(text);

    text = document.createElementNS(SVG, "text");
    text.classList.add("large-info");
    text.setAttribute('x', 320);
    text.setAttribute('y', 25);
    text.setAttribute('font-size', 50);
    text.setAttribute('dominant-baseline', 'middle');
    text.setAttribute('text-anchor', 'middle');
    text.textContent = "--";
    t.largeWinRateB = text;
    t.graph.appendChild(text);

    text = document.createElementNS(SVG, "text");
    text.classList.add("large-info");
    text.setAttribute('x', 320);
    text.setAttribute('y', 75);
    text.setAttribute('font-size', 50);
    text.setAttribute('dominant-baseline', 'middle');
    text.setAttribute('text-anchor', 'middle');
    text.textContent = "--";
    t.largeScoreB = text;
    t.graph.appendChild(text);
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
    return score;
  }
  function scoreToY(score) {
    var r = (score / 40 + 0.5);
    if (r < 0)
      r = 0;
    if (r > 1)
      r = 1;
    return r * 100;
  }

  var kifu_loaded = function (e) {
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
    var whiteUpdated = false;
    var blackUpdated = false;
    while (node) {
      var winrateList, scoreList;
      if (!node.move || !node.CC) {
        node = node.parent;
        turn--;
        continue;
      }
      if (node.move.c == WGo.B) {
        winrateList = this.black;
        scoreList = this.blackScore;
      } else {
        winrateList = this.white;
        scoreList = this.whiteScore;
      }

      var info = JSON.parse(node.CC);
      var rate = winrate(info);
      if (rate != null) {
        if (node.move.c == WGo.B)
          rate = 100 - rate;
        winrateList[turn] = turn * this.xScale + "," + rate;
      }
      var sc = score(info);
      if (sc != null) {
        var scY = scoreToY(sc);
        if (node.move.c == WGo.B)
          scY = 100 - scY;
        scoreList[turn*4]   = turn * this.xScale + "," + 50;
        scoreList[turn*4+1] = turn * this.xScale + "," + scY;
        scoreList[turn*4+2] = (turn + 0.4) * this.xScale + "," + scY;
        scoreList[turn*4+3] = (turn + 0.4) * this.xScale + "," + 50;
      }

      if (node.move.c == WGo.B && !blackUpdated) {
        if (rate != null)
          this.winrate.largeWinRateB.textContent = (100 - rate).toFixed(2) + "%";
        if (sc != null)
          this.winrate.largeScoreB.textContent = (sc > 0 ? "B+" : "W+") + Math.abs(sc).toFixed(2);
        blackUpdated = true;
      }
      if (node.move.c == WGo.W && !whiteUpdated) {
        if (rate != null)
          this.winrate.largeWinRateW.textContent = rate.toFixed(2) + "%";
        if (sc != null)
          this.winrate.largeScoreW.textContent = (sc > 0 ? "W+" : "B+") + Math.abs(sc).toFixed(2);
        whiteUpdated = true;
      }

      node = node.parent;
      turn--;
    }

    this.winrate.blackWinrate.setAttribute("points", this.black.join(" "));
    this.winrate.blackScore.setAttribute("points", this.blackScore.join(" "));
    this.winrate.whiteWinrate.setAttribute("points", this.white.join(" "));
    this.winrate.whiteScore.setAttribute("points", this.whiteScore.join(" "));
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
  bp_layouts["one_column"].bottom.push("AnalyzeBox");
  bp_layouts["no_comment"].bottom.push("AnalyzeBox");

  WGo.BasicPlayer.component.AnalyzeBox = AnalyzeBox;
})(WGo);
