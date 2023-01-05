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

  WGo.Player.Cgos = {};

  /**
   * Toggle cgos mode.
   */

  WGo.Player.Cgos = function (player, board) {
    this.player = player;
    this.board = board;
    this.cgosMode = false;
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
