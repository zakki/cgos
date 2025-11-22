# CGOS TV Mode Specification
_Last updated: 2025-11-22_

## 1. Context
Tournament streams and venue displays need to show live CGOS games in a way that cycles through ownership overlays and reading variations automatically. Today viewers must hover or click to see CGOS analysis (ownership heat maps and variation markers), which is infeasible when the feed is projected or mixed into a broadcast. A dedicated **TV mode** must drive these visual changes without user input while keeping the presentation balanced between black and white even if their time usage differs.

## 2. Goals
- Allow `cgos_viewer/viewer.html` (single game) and `cgos_viewer/list.html` (multi game wall) to enter a TV-optimised mode where CGOS analysis overlays change over time automatically.
- Rotate ownership overlays and highlighted reading variations at predictable intervals so that unattended displays stay informative.
- Guarantee that both colours receive on-screen exposure even if one player is thinking longer than the other.
- Keep manual controls available outside TV mode and allow an operator to exit TV mode instantly.
- Make the behaviour configurable (durations, which overlays participate) without code edits.

## 3. Non-goals
- Changing how CGOS engines produce `CC` payloads or wdata content.
- Redesigning existing player controls outside what is required to enable/exit TV mode.
- Building new scoreboard widgets beyond what WGo already exposes.

## 4. Terminology & Data
- **CC payload** – JSON stored in an SGF node `CC` property containing ownership values and `moves` entries (winrate, score, PV).
- **CgosAnalysisContext** – WGo helper that handles CGOS overlays (`showOwnership`, `showStats`, etc.).
- **TV cycle** – deterministic sequence of phases that toggle overlays and highlighted moves.
- **Spotlight player** – helper (per WGo player instance) that runs the TV cycle timers.

## 5. User stories
1. _Venue staff_ puts a board on a large monitor, enables TV mode, and sees the board alternate between a clean view, an ownership heatmap, and best-move variations without touching anything.
2. _Stream operator_ mirrors `list.html` with multiple boards; each board cycles overlays on its own, and a top-bar indicator confirms TV mode is active.
3. _Commentator_ uses an external mouse during TV mode; any interaction instantly pauses the automation so they can inspect the position.

## 6. TV mode activation & configuration
- UI elements:
  - Add a `TV mode` toggle button in both `viewer.html` and `list.html` footer toolbars. It shows the current status (OFF/ON) and when ON the rest of the toolbar dims.
  - Add query params: `tv=1` to auto-enable on load, `tvCycle=` to override timings, `tvGames=` (list view) to limit which boards run TV mode.
- Persistent settings:
  - Remember last-used TV mode flag and custom cycle overrides via `localStorage` (`cgos_tv_mode`, `cgos_tv_cycle`).
- Manual interaction:
  - Any click/touch/keyboard action on the board exits TV mode but keeps the remembered settings so operators can re-enable in one tap.

## 7. Display cycle definition
Each spotlight player maintains the following repeating phases (defaults shown; configurable via `tvCycle=neutral:7000,ownership:4000,read:2x3500`). Some phases repeat per colour.

| Phase | Duration (default) | Behaviour | Notes |
| --- | --- | --- | --- |
| `neutral` | 7 s | `showOwnership=false`, `showStats=false`, board only. | Resets after move arrival. |
| `ownership:black` | 4 s | Ownership heat map sampled from the most recent node played by Black. | If missing CC data, skip. |
| `ownership:white` | 4 s | Same for White (uses nearest node played by White, typically the parent). | Ensures fairness even when one side is thinking. |
| `reading:black` | `candidates * 3.5 s` | Sequentially highlight up to `reading.maxCandidates` moves from Black's `infoList`. | Each candidate shows PV stones and text overlay. |
| `reading:white` | same | Highlights White's candidate list. |
| Loop | – | Continue alternating colours. If a new move arrives, restart from `neutral` with the mover's colour scheduled first. | Prevents one colour from hogging the screen. |

Additional rules:
- When the current player is White, the colour order becomes `[white, black]` until a Black move arrives.
- If fewer than two CC nodes are available (e.g., start of game), fall back to `neutral → ownership (whoever available) → neutral`.
- If `reading.maxCandidates` is set to 0, skip reading phases entirely.

## 8. Reading (variation) rotation
- Require a new WGo API that lets code focus a specific `infoList` entry without synthetic mouse events:
  - `CgosAnalysisContext.setHighlightedMove(index, {colorNodeId, persistMs})` shows the PV markers for the indexed candidate.
  - `setHighlightedMove(-1)` clears the highlight.
- During `reading:<color>` phases, the spotlight player rotates through indexes `[0 … reading.maxCandidates-1]`. Each candidate is visible for `reading.perCandidateMs` (default 3.5 s). If `infoList` has fewer entries, stop early.
- PV markers reuse the existing `moveStatDrawer` / `_last_mark` logic but must honour programmatic focus (i.e., `mousemove` handlers should check `this._forcedHighlight` before using cursor coordinates).
- The overlay badge also shows textual data (winrate %, score delta) in the `info` panel to aid commentators.

## 9. Ownership rotation
- Ownership overlays already depend on `showOwnership`. TV mode simply toggles this flag per phase and instructs the board to render with a `perspectiveColor` (current node's mover).
- To prevent long single-colour runs when only one player has moved recently, the spotlight player caches references to the last CC node for each colour. Even if the board state has not advanced, it alternates between those snapshots.
- Add a fade animation (CSS class `tv-ownership-active`) so transitions are smooth on broadcasts.

## 10. Interaction & fail-safes
- When TV mode is active, hide pointer tooltips and lock manual board navigation to avoid sudden jumps mid-broadcast.
- If fonts, winrate graphs, or stats components are disabled because the layout is `wgo-small`, TV mode still runs but only toggles overlays that exist (detected via feature flags on the CgosAnalysisContext snapshot).
- When data fetching stalls (no SGF updates for `tv.idleTimeout` = 5 minutes), display an overlay "Waiting for new moves" and keep ownership off to avoid burn-in.

## 11. Required changes under `wgo/`
1. **CgosAnalysisContext API**
   - Add `applyOverrides(overrides, {source})` where `overrides` may include `showOwnership`, `showStats`, `showBlackWinrate`, etc. Distinguish between _persistent_ user toggles and _transient_ overrides from TV mode. When overrides lapse, the previous manual settings are restored.
   - Fire a new event `player.dispatchEvent({ type: "cgossettings", overrides, source })` whenever overrides change so UI components (menus) can update their selected state if needed.
2. **Programmatic reading highlights**
   - Expose `setHighlightedMove(index)` and `clearHighlightedMove()` described above.
   - Update `cgos_board_mouse_move` and `_last_mark` logic to cooperate with forced highlights (e.g., skip removing `_last_mark` when `_forcedHighlight` is true, but still redraw when new data arrives).
3. **CC snapshot accessors**
   - Provide `player._cgos.getSnapshot()` returning `{ nodeId, color, infoList, ownership, winrate, score }` for the node currently rendered.
   - Provide `player._cgos.getSnapshotForNode(node)` so higher-level code (like the TV spotlight) can fetch cached CC info for neighbouring nodes without re-parsing.
4. **Events for move arrivals**
   - Emit `player.dispatchEvent({ type: "moveplayed", color, nodeId, moveNumber })` whenever `update_board` runs on a node with `move` data. The TV spotlight uses this to restart its cycle.
5. **Optional CSS hook**
   - Add classes such as `wgo-tv-mode` on the board container when overrides are active to drive fade animations via CSS.

## 12. Implementation outline inside `cgos_viewer`
### 12.1 Shared TV utilities (`cgos_viewer/tv_mode.js`)
- Create a shared module exporting `createTvSpotlight(player, options)` returning `{ start(), stop(), isActive(), setCycleConfig() }`.
- Options include:
  - `cycleTimings` – parsed from defaults or query params.
  - `maxCandidates`, `ownershipFadeMs`, `idleTimeout`.
  - `colorOrderStrategy` – `"current-first"` vs `"strict-alternate"`.
- Internally use `requestAnimationFrame` or `setTimeout` chain to drive phases; rely on the new WGo APIs to toggle overlays and highlight moves.

### 12.2 `viewer.html`
- Add a toggle control next to existing checkboxes plus a floating badge in the top-right of the board when TV mode is active.
- When enabled:
  - Instantiate one spotlight tied to the single `WGoPlayer` (player reference available inside viewer.js).
  - Automatically enable CGOS analysis (`player.player._cgos.set(true)`).
  - Suppress manual controls: disable `touchmode`, `stone-style`, and `update` checkboxes until TV mode is off.
  - Hook to `mousemove`, `touchstart`, and keyboard events on `document` to auto-exit TV mode when the operator interacts.

### 12.3 `list.html`
- Extend footer with a `TV mode` checkbox that starts the spotlight on every active board (respecting `num-games` limit).
- Allow "spotlight subsets": if `tvGames` query param lists game IDs, only those boards switch overlays.
- Stagger cycle offsets per board (e.g., add `boardIndex * 750 ms`) so not all boards change overlays simultaneously on screen.
- When a board is closed/removed, dispose the spotlight to avoid timers on detached DOM.
- Ensure `analysis-mode` is forced on while TV mode is active; when TV mode stops, revert to user-selected `analysis-mode` state.

## 13. Testing strategy
- Unit test the new WGo APIs (transient overrides, highlight control) via Jest/Playwright harness that already exists under `dist-*` builds.
- Browser-level tests (Playwright) verifying that enabling TV mode toggles classes, rotates overlays, and pauses when user input occurs.
- Manual soak tests on low-power devices to ensure CPU usage stays acceptable (target < 20% on a Pi 4 for a single board).

## 14. Open questions / follow-ups
1. Should list view optionally zoom a single board to fullscreen in TV mode ("spotlight" carousel)? Currently scoped out but easy to add later.
2. Do we need per-game custom timings (e.g., faster rotation for blitz games)? Query param could include a per-game map if required.
3. Should the new `moveplayed` event include byo-yomi/time-left data if CGOS logs it? Need to inspect SGF metadata first.
4. For broadcasts, do we want an overlay that shows "Next update in Xs"? Not scoped for v1.

## 15. Roll-out plan
1. Implement WGo API extensions with automated tests.
2. Build shared `tv_mode.js` module and wire into viewer/list with feature flag hidden behind query param.
3. Collect feedback from a mock broadcast, tweak default timings/durations.
4. Make UI toggle visible by default once stable.
