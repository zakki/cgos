/**
 * Automatic CGOS analysis rotation for unattended displays.
 *
 * This file deliberately has no dependency on the viewer implementation.  It
 * accepts either cgos.WGoPlayer or a WGo.BasicPlayer and only uses the public
 * CgosAnalysisContext API.
 */
/* global cgos, WGo */
(function (cgos) {
	"use strict";

	const DEFAULTS = Object.freeze({
		neutralMs: 7000,
		ownershipMs: 4000,
		readingPerCandidateMs: 3500,
		readingMaxCandidates: 2,
		ownershipFadeMs: 350,
		idleTimeout: 5 * 60 * 1000,
		staggerOffsetMs: 0,
		colorOrderStrategy: "current-first"
	});
	const TV_OVERRIDE_SOURCE = "tv-mode";

	function positiveNumber(value, fallback, allowZero) {
		const number = Number(value);
		if (!Number.isFinite(number)) return fallback;
		if (allowZero ? number < 0 : number <= 0) return fallback;
		return number;
	}

	function normalizeConfig(options) {
		const timings =
			options && typeof options.cycleTimings === "object"
				? options.cycleTimings
				: {};
		const reading =
			options && typeof options.reading === "object"
				? options.reading
				: {};
		const source = Object.assign({}, timings, options || {});
		return {
			neutralMs: positiveNumber(
				source.neutralMs,
				DEFAULTS.neutralMs,
				false
			),
			ownershipMs: positiveNumber(
				source.ownershipMs,
				DEFAULTS.ownershipMs,
				false
			),
			readingPerCandidateMs: positiveNumber(
				source.readingPerCandidateMs ??
					reading.perCandidateMs ??
					source.perCandidateMs,
				DEFAULTS.readingPerCandidateMs,
				false
			),
			readingMaxCandidates: Math.floor(
				positiveNumber(
					source.readingMaxCandidates ??
						source.maxCandidates ??
						reading.maxCandidates,
					DEFAULTS.readingMaxCandidates,
					true
				)
			),
			ownershipFadeMs: positiveNumber(
				source.ownershipFadeMs,
				DEFAULTS.ownershipFadeMs,
				true
			),
			idleTimeout: positiveNumber(
				source.idleTimeout,
				DEFAULTS.idleTimeout,
				false
			),
			staggerOffsetMs: positiveNumber(
				source.staggerOffsetMs,
				DEFAULTS.staggerOffsetMs,
				true
			),
			colorOrderStrategy:
				source.colorOrderStrategy === "strict-alternate"
					? "strict-alternate"
					: "current-first"
		};
	}

	/**
	 * Parse `neutral:7000,ownership:4000,read:2x3500`.
	 * Invalid entries are ignored so a typo cannot prevent the viewer loading.
	 */
	function parseTvCycleConfig(spec) {
		const parsed = {};
		if (typeof spec !== "string") return parsed;
		for (const entry of spec.split(",")) {
			const separator = entry.indexOf(":");
			if (separator < 0) continue;
			const name = entry.slice(0, separator).trim().toLowerCase();
			const value = entry
				.slice(separator + 1)
				.trim()
				.toLowerCase();
			if (name === "neutral") {
				parsed.neutralMs = positiveNumber(value, undefined, false);
			} else if (name === "ownership") {
				parsed.ownershipMs = positiveNumber(value, undefined, false);
			} else if (name === "read" || name === "reading") {
				const match = value.match(/^(\d+)\s*x\s*(\d+(?:\.\d+)?)$/);
				if (match) {
					parsed.readingMaxCandidates = Number(match[1]);
					parsed.readingPerCandidateMs = Number(match[2]);
				} else {
					parsed.readingPerCandidateMs = positiveNumber(
						value,
						undefined,
						false
					);
				}
			}
		}
		return parsed;
	}

	function resolvePlayer(player) {
		if (player && player.player && player.player._cgos) {
			return {
				basic: player.player,
				context: player.player._cgos,
				element: player.elmPlayer || player.player.element
			};
		}
		if (player && player._cgos) {
			return {
				basic: player,
				context: player._cgos,
				element: player.element
			};
		}
		throw new Error("TV mode requires a player with CGOS analysis");
	}

	function createWaitingOverlay(element) {
		if (!element || !element.appendChild) return null;
		const overlay = document.createElement("div");
		overlay.className = "cgos-tv-waiting";
		overlay.textContent = "Waiting for new moves";
		overlay.hidden = true;
		overlay.setAttribute("role", "status");
		overlay.style.cssText =
			"position:absolute;inset:0;z-index:1000;display:flex;" +
			"align-items:center;justify-content:center;background:rgba(0,0,0,.55);" +
			"color:white;font:600 1.2em sans-serif;pointer-events:none";
		if (getComputedStyle(element).position === "static") {
			element.style.position = "relative";
		}
		element.appendChild(overlay);
		return overlay;
	}

	function createTvSpotlight(player, options = {}) {
		const resolved = resolvePlayer(player);
		const basic = resolved.basic;
		const analysis = resolved.context;
		const element = resolved.element;
		let config = normalizeConfig(options);
		let active = false;
		let destroyed = false;
		let timer = null;
		let idleTimer = null;
		let lastMoveAt = Date.now();
		let firstColor = null;
		let strictFirstColor = null;
		let waitingOverlay = null;
		let sequence = [];
		let sequenceIndex = 0;

		function colorValues() {
			const black = typeof WGo !== "undefined" ? WGo.B : 1;
			const white = typeof WGo !== "undefined" ? WGo.W : -1;
			return { black, white };
		}

		function snapshotFor(color) {
			if (typeof analysis.getLastColorSnapshot === "function") {
				return analysis.getLastColorSnapshot(color);
			}
			const current =
				typeof analysis.getSnapshot === "function"
					? analysis.getSnapshot()
					: null;
			return current && current.color === color ? current : null;
		}

		function clearTimer() {
			if (timer != null) {
				clearTimeout(timer);
				timer = null;
			}
		}

		function clearIdleTimer() {
			if (idleTimer != null) {
				clearTimeout(idleTimer);
				idleTimer = null;
			}
		}

		function hideWaiting() {
			if (waitingOverlay) waitingOverlay.hidden = true;
			if (element) element.classList.remove("tv-idle");
		}

		function showWaiting() {
			if (!active) return;
			clearTimer();
			neutral();
			if (!waitingOverlay) waitingOverlay = createWaitingOverlay(element);
			if (waitingOverlay) waitingOverlay.hidden = false;
			if (element) element.classList.add("tv-idle");
		}

		function armIdleTimer() {
			clearIdleTimer();
			const remaining = config.idleTimeout - (Date.now() - lastMoveAt);
			if (remaining <= 0) {
				showWaiting();
				return;
			}
			idleTimer = setTimeout(showWaiting, remaining);
		}

		function apply(overrides) {
			analysis.applyOverrides(overrides, {
				source: TV_OVERRIDE_SOURCE
			});
		}

		function clearHighlight() {
			if (typeof analysis.clearHighlightedMove === "function") {
				analysis.clearHighlightedMove();
			} else if (typeof analysis.setHighlightedMove === "function") {
				analysis.setHighlightedMove(-1);
			}
		}

		function clearSnapshot() {
			if (typeof analysis.clearSnapshotOverride === "function") {
				analysis.clearSnapshotOverride();
			}
		}

		function neutral() {
			clearHighlight();
			clearSnapshot();
			apply({ showOwnership: false, showStats: false });
			if (element) element.classList.remove("tv-ownership-active");
		}

		function schedule(callback, duration) {
			clearTimer();
			if (!active) return;
			timer = setTimeout(callback, Math.max(0, duration));
		}

		function buildSequence() {
			const colors = colorValues();
			const current =
				typeof analysis.getSnapshot === "function"
					? analysis.getSnapshot()
					: null;
			let preferred = firstColor || (current && current.color);
			if (preferred !== colors.black && preferred !== colors.white) {
				preferred = colors.black;
			}
			if (config.colorOrderStrategy === "strict-alternate") {
				strictFirstColor =
					strictFirstColor == null
						? preferred
						: strictFirstColor === colors.black
							? colors.white
							: colors.black;
				preferred = strictFirstColor;
			}
			const other =
				preferred === colors.black ? colors.white : colors.black;
			const available = [preferred, other].filter((color) =>
				Boolean(snapshotFor(color))
			);

			// With only one analysed colour, avoid repeatedly showing reading
			// from one side: neutral -> ownership -> neutral.
			if (available.length < 2) {
				return available.length
					? [
							{ type: "ownership", color: available[0] },
							{ type: "neutral" }
						]
					: [{ type: "neutral" }];
			}
			const phases = [];
			for (const color of available) {
				phases.push({ type: "ownership", color });
			}
			if (config.readingMaxCandidates > 0) {
				for (const color of available) {
					const snapshot = snapshotFor(color);
					const count = Math.min(
						config.readingMaxCandidates,
						snapshot && snapshot.infoList
							? snapshot.infoList.length
							: 0
					);
					for (let index = 0; index < count; index++) {
						phases.push({ type: "reading", color, index });
					}
				}
			}
			return phases.length ? phases : [{ type: "neutral" }];
		}

		function runNextPhase() {
			if (!active) return;
			if (Date.now() - lastMoveAt >= config.idleTimeout) {
				showWaiting();
				return;
			}
			if (sequenceIndex >= sequence.length) {
				neutral();
				sequence = buildSequence();
				sequenceIndex = 0;
				schedule(runNextPhase, config.neutralMs);
				return;
			}
			const phase = sequence[sequenceIndex++];
			if (phase.type === "neutral") {
				neutral();
				schedule(runNextPhase, config.neutralMs);
				return;
			}
			const snapshot = snapshotFor(phase.color);
			if (!snapshot) {
				schedule(runNextPhase, 0);
				return;
			}
			if (typeof analysis.showSnapshot === "function") {
				analysis.showSnapshot(snapshot);
			}
			if (phase.type === "ownership") {
				clearHighlight();
				apply({ showOwnership: true, showStats: false });
				if (element) element.classList.add("tv-ownership-active");
				schedule(runNextPhase, config.ownershipMs);
			} else {
				if (element) element.classList.remove("tv-ownership-active");
				apply({ showOwnership: false, showStats: true });
				analysis.setHighlightedMove(phase.index, {
					colorNodeId: snapshot.nodeId,
					persistMs: config.readingPerCandidateMs
				});
				schedule(runNextPhase, config.readingPerCandidateMs);
			}
		}

		function restart(color) {
			if (!active) return;
			firstColor = color;
			lastMoveAt = Date.now();
			hideWaiting();
			armIdleTimer();
			neutral();
			sequence = buildSequence();
			sequenceIndex = 0;
			schedule(runNextPhase, config.neutralMs);
		}

		function onMovePlayed(event) {
			restart(event && event.color);
		}

		function start() {
			if (destroyed) {
				throw new Error("Cannot restart a destroyed TV spotlight");
			}
			if (active) return;
			active = true;
			lastMoveAt = Date.now();
			const current =
				typeof analysis.getSnapshot === "function"
					? analysis.getSnapshot()
					: null;
			firstColor = current ? current.color : null;
			if (typeof analysis.set === "function") analysis.set(true);
			if (element) element.classList.add("wgo-tv-mode");
			basic.addEventListener("moveplayed", onMovePlayed);
			neutral();
			sequence = buildSequence();
			sequenceIndex = 0;
			armIdleTimer();
			schedule(runNextPhase, config.neutralMs + config.staggerOffsetMs);
		}

		function stop() {
			if (!active) return;
			active = false;
			clearTimer();
			clearIdleTimer();
			basic.removeEventListener("moveplayed", onMovePlayed);
			hideWaiting();
			clearHighlight();
			clearSnapshot();
			analysis.clearOverrides(TV_OVERRIDE_SOURCE);
			if (element) {
				element.classList.remove("wgo-tv-mode", "tv-ownership-active");
			}
		}

		function destroy() {
			stop();
			destroyed = true;
			if (waitingOverlay && waitingOverlay.parentNode) {
				waitingOverlay.parentNode.removeChild(waitingOverlay);
			}
			waitingOverlay = null;
		}

		function setCycleConfig(nextOptions) {
			config = normalizeConfig(
				Object.assign({}, config, nextOptions || {})
			);
			if (active) restart(firstColor);
		}

		return {
			start,
			stop,
			destroy,
			isActive: () => active,
			setCycleConfig
		};
	}

	cgos.parseTvCycleConfig = parseTvCycleConfig;
	cgos.createTvSpotlight = createTvSpotlight;
})(cgos);
