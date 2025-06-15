/**
 * Base class for BasicPlayer's component. Each component should implement this interface.
 */

export const Component = function() {
	this.element = document.createElement("div");
}

Component.prototype = {
	constructor: Component,
	
	/**
	 * Append component to element.
	 */
	
	appendTo: function(target) {
		target.appendChild(this.element);
	},
	
	/**
	 * Compute and return width of component.
	 */
	 
	getWidth: function() {
		const css = window.getComputedStyle(this.element);
		return parseInt(css.width);
	},
	
	/**
	 * Compute and return height of component.
	 */
	
	getHeight: function() {
		const css = window.getComputedStyle(this.element);
		return parseInt(css.height);
	},
	
	/**
	 * Update component. Actually dimensions are defined and cannot be changed in this method, 
	 * but you can change for example font size according to new dimensions.
	 */
	
	updateDimensions: function() {
	
	}
}
