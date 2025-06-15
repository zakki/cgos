import { WGo } from "./wgo";

import { BasicPlayer } from "./basicplayer.js";
import { Component  } from "./basicplayer.component.js";

const compare_widgets = function(a,b) {
	if(a.weight < b.weight) return -1;
	else if(a.weight > b.weight) return 1;
	else return 0;
}

const prepare_dom = function(player) {

	this.iconBar = document.createElement("div");
	this.iconBar.className = "wgo-control-wrapper";
	this.element.appendChild(this.iconBar);

	let widget;
	
	for(const w in Control.widgets) {
		widget = new Control.widgets[w].constructor(player, Control.widgets[w].args);
		widget.appendTo(this.iconBar);
		this.widgets.push(widget);
	}
}

export const Control = WGo.extendClass(Component, function(player) {
	this.super(player);
	
	this.widgets = [];
	this.element.className = "wgo-player-control";

	prepare_dom.call(this, player);
});

Control.prototype.updateDimensions = function() {
	if(this.element.clientWidth < 340) this.element.className = "wgo-player-control wgo-340";
	else if(this.element.clientWidth < 440) this.element.className = "wgo-player-control wgo-440";
	else this.element.className = "wgo-player-control";
}

export const control = {};
BasicPlayer.control = control;

const butupd_first = function(e) {
	if(!e.node.parent && !this.disabled) this.disable();
	else if(e.node.parent && this.disabled) this.enable();
}

const butupd_last = function(e) {
	if(!e.node.children.length && !this.disabled) this.disable();
	else if(e.node.children.length && this.disabled) this.enable();
}

const but_frozen = function(e) {
	this._disabled = this.disabled;
	if(!this.disabled) this.disable();
}

const but_unfrozen = function(e) {
	if(!this._disabled) this.enable();
	delete this._disabled;
}

/**
 * Control.Widget base class. It is used for implementing buttons and other widgets.
 * First parameter is BasicPlayer object, second can be configuratioon object. 
 *
 * args = {
 *   name: String, // required - it is used for class name
 *	 init: Function, // other initialization code can be here
 *	 disabled: BOOLEAN, // default false
 * }
 */
 
export const Widget = function(player, args) {
	this.element = this.element || document.createElement(args.type || "div");
	this.element.className = "wgo-widget-"+args.name;
	this.init(player, args);
}
control.Widget = Widget;

Widget.prototype = {
	constructor: Widget,
	
	/**
	 * Initialization function.
	 */
	
	init: function(player, args) {
		if(!args) return;
		if(args.disabled) this.disable();
		if(args.init) args.init.call(this, player);
	},
	
	/**
	 * Append to element.
 	 */
	 
	appendTo: function(target) {
		target.appendChild(this.element);
	},
	
	/**
	 * Make button disabled - eventual click listener mustn't be working.
 	 */
	
	disable: function() {
		this.disabled = true;
		if(this.element.className.search("wgo-disabled") == -1) {
			this.element.className += " wgo-disabled";
		}
	},
	
	/**
	 * Make button working
 	 */
	
	enable: function() {
		this.disabled = false;
		this.element.className = this.element.className.replace(" wgo-disabled","");
		this.element.disabled = "";
	},
	
}

/**
 * Group of widgets
 */

export const Group = WGo.extendClass(Widget, function(player, args) {
	this.element = document.createElement("div");
	this.element.className = "wgo-ctrlgroup wgo-ctrlgroup-"+args.name;
	
	let widget;
	for(const w in args.widgets) {
		widget = new args.widgets[w].constructor(player, args.widgets[w].args);
		widget.appendTo(this.element);
	}
});
control.Group = Group;

/**
 * Clickable widget - for example button. It has click action. 
 *
 * args = {
 *   title: String, // required
 *	 init: Function, // other initialization code can be here
 *	 click: Function, // required *** onclick event
 *   togglable: BOOLEAN, // default false
 *	 selected: BOOLEAN, // default false
 *	 disabled: BOOLEAN, // default false
 *	 multiple: BOOLEAN
 * }
*/

export const Clickable = WGo.extendClass(control.Widget, function(player, args) {
	this.super(player, args);
});
control.Clickable = Clickable;

Clickable.prototype.init = function(player, args) {
	let fn;
	const _this = this;
	
	if(args.togglable) {
		fn = function() {
			if(_this.disabled) return;
			
			if(args.click.call(_this, player)) _this.select();
			else _this.unselect();
		};
	}
	else {
		fn = function() {
			if(_this.disabled) return;
			args.click.call(_this, player);
		};		
	}
	
	this.element.addEventListener("click", fn);
	this.element.addEventListener("touchstart", function(e){
		e.preventDefault();
		fn();
		if(args.multiple) {
			_this._touch_i = 0;
			_this._touch_int = window.setInterval(function(){
				if(_this._touch_i > 500) {
					fn();
				}
				_this._touch_i += 100;
			}, 100);
		}
		return false;
	});
	
	if(args.multiple) {
		this.element.addEventListener("touchend", function(e){
			window.clearInterval(_this._touch_int);
		});
	}

	if(args.disabled) this.disable();
	if(args.init) args.init.call(this, player);
};

Clickable.prototype.select = function() {
	this.selected = true;
	if(this.element.className.search("wgo-selected") == -1) this.element.className += " wgo-selected";
};

Clickable.prototype.unselect = function() {
	this.selected = false;
	this.element.className = this.element.className.replace(" wgo-selected","");
};

/**
 * Widget of button with image icon. 
 */

export const Button = WGo.extendClass(Clickable, function(player, args) {
	const elem = this.element = document.createElement("button");
	elem.className = "wgo-button wgo-button-"+args.name;
	elem.title = WGo.t(args.name);
	
	this.init(player, args);
});
control.Button = Button;

Button.prototype.disable = function() {
	Button.prototype.super.prototype.disable.call(this);
	this.element.disabled = "disabled";
}

Button.prototype.enable = function() {
	Button.prototype.super.prototype.enable.call(this);
	this.element.disabled = "";
}

/**
 * Widget used in menu
 */

export const MenuItem = WGo.extendClass(Clickable, function(player, args) {
	const elem = this.element = document.createElement("div");
	elem.className = "wgo-menu-item wgo-menu-item-"+args.name;
	elem.title = WGo.t(args.name);
	elem.innerHTML = elem.title;
	
	this.init(player, args);
});
control.MenuItem = MenuItem;

/**
 * Widget for move counter.
 */

export const MoveNumber = WGo.extendClass(control.Widget, function(player) {
	this.element = document.createElement("form");
	this.element.className = "wgo-player-mn-wrapper";
	
	const move = this.move = document.createElement("input");
	move.type = "text";
	move.value = "0";
	move.maxlength = 3;
	move.className = "wgo-player-mn-value";
	//move.disabled = "disabled";
	this.element.appendChild(move);

	this.element.onsubmit = move.onchange = function(player) {
		player.goTo(this.getValue());
		return false; 
	}.bind(this, player);
	
	player.addEventListener("update", function(e) {
		this.setValue(e.path.m);
	}.bind(this));
	
	player.addEventListener("kifuLoaded", this.enable.bind(this));
	player.addEventListener("frozen", this.disable.bind(this));
	player.addEventListener("unfrozen", this.enable.bind(this));
});
control.MoveNumber = MoveNumber;

MoveNumber.prototype.disable = function() {
	MoveNumber.prototype.super.prototype.disable.call(this);
	this.move.disabled = "disabled";
};

MoveNumber.prototype.enable = function() {
	MoveNumber.prototype.super.prototype.enable.call(this);
	this.move.disabled = "";
};

MoveNumber.prototype.setValue = function(n) {
	this.move.value = n;
};

MoveNumber.prototype.getValue = function() {
	return parseInt(this.move.value);
};

// display menu
const player_menu = function(player) {

	if(player._menu_tmp) {
		delete player._menu_tmp;
		return;
	}
	if(!player.menu) {
		player.menu = document.createElement("div");
		player.menu.className = "wgo-player-menu";
		player.menu.style.position = "absolute";
		player.menu.style.display = "none";
		
		this.element.parentElement.appendChild(player.menu);
		
		let widget;
		for(const i in Control.menu) {
			widget = new Control.menu[i].constructor(player, Control.menu[i].args, true);
			widget.appendTo(player.menu);
		}
	}

	if(player.menu.style.display != "none") {
		player.menu.style.display = "none";

		document.removeEventListener("click", player._menu_ev);
		//document.removeEventListener("touchstart", player._menu_ev);
		delete player._menu_ev;
		
		this.unselect();
		return false;
	}
	else {
		player.menu.style.display = "block";
		
		const top = this.element.offsetTop;
		const left = this.element.offsetLeft;
		
		// kinda dirty syntax, but working well
		if(this.element.parentElement.parentElement.parentElement.parentElement == player.regions.bottom.wrapper) {
			player.menu.style.left = left+"px";
			player.menu.style.top = (top-player.menu.offsetHeight+1)+"px";
		}
		else {
			player.menu.style.left = left+"px";
			player.menu.style.top = (top+this.element.offsetHeight)+"px";
		}
			
		player._menu_ev = player_menu.bind(this, player)
		player._menu_tmp = true;
		
		document.addEventListener("click", player._menu_ev);
		//document.addEventListener("touchstart", player._menu_ev);

		return true;
	}
}

/**
 * List of widgets (probably MenuItem objects) to be displayed in drop-down menu.
 */
 
Control.menu = [{
	constructor: control.MenuItem,
	args: {
		name: "switch-coo",
		togglable: true,
		click: function(player) {
			player.setCoordinates(!player.coordinates);
			return player.coordinates;
		},
		init: function(player) {
			if(player.coordinates) this.select();
		}
	}
}];

/**
 * List of widgets (probably Button objects) to be displayed.
 *
 * widget = {
 *	 constructor: Function, // construct a instance of widget
 *	 args: Object,
 * }
*/

Control.widgets = [ {
	constructor: Group,
	args: {
		name: "left",
		widgets: [{
			constructor: Button,
			args: {
				name: "menu",
				togglable: true,
				click: player_menu,
			}
		}]
	}
}, {
	constructor: Group,
	args: {
		name: "right",
		widgets: [{
			constructor: Button,
			args: {
				name: "about",
				click: function(player) {
					player.showMessage(WGo.t("about-text"));
				},
			}
		}]
	}
}, {
	constructor: Group,
	args: {
		name: "control",
		widgets: [{
			constructor: Button,
			args: {
				name: "first",
				disabled: true,
				init: function(player) {
					player.addEventListener("update", butupd_first.bind(this));
					player.addEventListener("frozen", but_frozen.bind(this));
					player.addEventListener("unfrozen", but_unfrozen.bind(this));
				},
				click: function(player) { 
					player.first();
				},
			}
		}, {
			constructor: Button,
			args: {
				name: "multiprev",
				disabled: true,
				multiple: true,
				init: function(player) {
					player.addEventListener("update", butupd_first.bind(this));
					player.addEventListener("frozen", but_frozen.bind(this));
					player.addEventListener("unfrozen", but_unfrozen.bind(this));
				},
				click: function(player) { 
					const p = WGo.clone(player.kifuReader.path);
					p.m -= 10; 
					player.goTo(p);
				},
			}
		},{
			constructor: Button,
			args: {
				name: "previous",
				disabled: true,
				multiple: true,
				init: function(player) {
					player.addEventListener("update", butupd_first.bind(this));
					player.addEventListener("frozen", but_frozen.bind(this));
					player.addEventListener("unfrozen", but_unfrozen.bind(this));
				},
				click: function(player) { 
					player.previous();
				},
			}
		}, {
			constructor: MoveNumber,
		}, {
			constructor: Button,
			args: {
				name: "next",
				disabled: true,
				multiple: true,
				init: function(player) {
					player.addEventListener("update", butupd_last.bind(this));
					player.addEventListener("frozen", but_frozen.bind(this));
					player.addEventListener("unfrozen", but_unfrozen.bind(this));
				},
				click: function(player) {
					player.next();
				},
			}
		}, {
			constructor: Button,
			args: {
				name: "multinext",
				disabled: true,
				multiple: true,
				init: function(player) {
					player.addEventListener("update", butupd_last.bind(this));
					player.addEventListener("frozen", but_frozen.bind(this));
					player.addEventListener("unfrozen", but_unfrozen.bind(this));
				},
				click: function(player) { 
					const p = WGo.clone(player.kifuReader.path);
					p.m += 10; 
					player.goTo(p);
				},
			}
		}, {
			constructor: Button,
			args: {
				name: "last",
				disabled: true,
				init: function(player) {
					player.addEventListener("update", butupd_last.bind(this));
					player.addEventListener("frozen", but_frozen.bind(this));
					player.addEventListener("unfrozen", but_unfrozen.bind(this));
				},
				click: function(player) {
					player.last()
				},
			}
		}]
	}
}];

const bp_layouts = BasicPlayer.layouts;
bp_layouts["right_top"].top.push("Control");
bp_layouts["right"].right.push("Control");
bp_layouts["one_column"].top.push("Control");
bp_layouts["no_comment"].bottom.push("Control");
bp_layouts["minimal"].bottom.push("Control");

const player_terms = {
	"about": "About",
	"first": "First",
	"multiprev": "10 moves back",
	"previous": "Previous",
	"next": "Next",
	"multinext": "10 moves forward",
	"last": "Last",
	"switch-coo": "Display coordinates",
	"menu": "Menu",
};

for(const key in player_terms) WGo.i18n.en[key] = player_terms[key];

BasicPlayer.component.Control = Control;
