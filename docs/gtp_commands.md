# GTP Command Guide for CGOS Participants

[日本語版 (Japanese)](gtp_commands_ja.md)

## TL;DR

If you are already familiar with the GTP specification, keep the following core points in mind:

- Mandatory Commands (7 commands):  
  `list_commands`, `boardsize`, `clear_board`, `komi`, `play`, `genmove`, `quit`  
  These are verified by the Python client at startup. If any is missing, the client reports an error and the engine cannot play. Ensure that `list_commands` includes itself in its output.
- Support for `play` on the Engine's Own Color (Crucial for Game Resumption):  
  During normal play, `play` commands are only sent for the opponent's moves. However, when reconnecting after a disconnection, the client receives past moves from the server and replays all moves from move 1 via `play`. Therefore, the engine must accept `play` commands for both black and white.
- Time Management (Practically Required):  
  To avoid losing on time, implementing `time_settings` and `time_left` is practically essential. The client sends neither command unless both are supported, so they must be implemented as a pair.

---

## Scope of this Document

On CGOS, the game server does not send GTP commands directly to the Go engine:

```text
CGOS Server ──[CGOS Protocol]── Client Program (CGOS Client) ──[GTP]── Go Engine
```

The client program receives game progress messages from the CGOS server, converts them into GTP commands, and relays them to the engine.  
This guide explains the GTP command specifications and calling sequences expected from the Go engine (the CGOS communication protocol itself is outside the scope of this document).

> [!NOTE]
> Throughout this document, the current standard Python client is referred to as the Python client, and the original Tcl-based client is referred to as the Legacy Tcl client.

### Basic Principles of GTP Communication
- Response Format: Success responses must start with `=` and error responses with `?`. Furthermore, **the response must always end with an empty line (two consecutive newlines: LF LF or CRLF CRLF)**.
- Command IDs: The client sends commands without command IDs.
- Separation of stdout and stderr: Do not mix engine diagnostics or debug logs into standard output (stdout), as this corrupts GTP responses. Always output logs to standard error (stderr).

---

## 1. Commands Used by the Standard Python Client

### Mandatory Commands (Playing Engine)

| Command | Example Argument | Purpose / Description |
| :--- | :--- | :--- |
| `list_commands` | None | Returns the list of supported commands. Called unconditionally by the client immediately after startup. |
| `boardsize <size>` | `19` | Sets the board size. |
| `clear_board` | None | Clears the board to start a new game. |
| `komi <komi>` | `7.5` | Sets the komi value. |
| `play <color> <move>` | `b Q16` | Applies a move to the board. In normal play, this is used for opponent moves; during reconnection, all past moves from move 1 are sent. |
| `genmove <color>` | `w` | Generates a move for the specified color. |
| `quit` | None | Terminates the engine process. |

> [!IMPORTANT]
> The Python client checks the output of `list_commands` during startup. If any of the mandatory commands (`boardsize`, `clear_board`, `komi`, `play`, `genmove`, `quit`) is missing, the engine cannot start a game. `list_commands` must also include itself in the list.

*Note: When connected as an observer (e.g., using GoGUI to watch games), `genmove` is not required, but all other mandatory commands above must be supported.*

### Optional Commands

| Command | Example Argument | Condition and Purpose |
| :--- | :--- | :--- |
| `time_settings <main> 0 0` | `300 0 0` | Sent at game start only if both `time_settings` and `time_left` are supported (time in seconds). The trailing `0 0` indicates no byo-yomi. |
| `time_left <color> <time> 0` | `b 285 0` | Sent immediately before generating a move under the same condition (time in seconds). The trailing `0` indicates no stone count. |
| `cgos-opponent_name <name>` | `KataGo` | Sent if supported to notify the engine of the opponent's name. |
| `cgos-opponent_rating <rating>` | `3500.0` | Sent if supported to notify the engine of the opponent's rating. |
| `cgos-gameover <result>` | `B+Resign` | Sent if supported to notify the final game result (e.g., `B+Resign`, `W+3.5`, `B+Time`). |
| `cgos-genmove_analyze <color>` | `b` | Sent if supported to generate a move accompanied by analysis data (win rate, score lead, PV, etc.). |
| `kata-genmove_analyze <color> ownership true` | `b ownership true` | Used if `cgos-genmove_analyze` is not supported, but this command is. |
| `lz-genmove_analyze <color> 100000` | `b 100000` | Used if neither of the above analysis commands is supported, but this command is. |

- Priority of Analysis Commands:  
  The selection priority is `cgos-genmove_analyze` → `kata-genmove_analyze` → `lz-genmove_analyze`. If any of these commands are available, the client calls it in place of `genmove` (however, standard `genmove` must still be implemented to pass the startup check). For the JSON analysis schema, refer to [CGOS GTP Extension for Move Analysis](gtp.md).
- Time Management Condition:  
  Time settings and time updates are only sent if both `time_settings` and `time_left` are listed in `list_commands`. Implementing only one of them results in neither being used.

---

## 2. Commands Used by the Legacy Tcl Client

### Mandatory Commands

| Command | Purpose |
| :--- | :--- |
| `list_commands` | Retrieves the list of supported commands at startup. |
| `boardsize <size>` | Sets the board size. |
| `clear_board` | Clears the board. |
| `komi <komi>` | Sets the komi. |
| `play <color> <move>` | Applies a move. |
| `genmove <color>` | Generates a move. |
| `quit` | Terminates the engine on client exit, engine change, or error. |

*Note: Unlike the Python client, the legacy Tcl client does not check the command list at startup. However, because it issues all of these commands during a game or when shutting down, the engine must implement all of them.*

### Optional Commands

- `time_settings <main> 0 0`
- `time_left <color> <time> 0`

*Note: The legacy Tcl client does not support opponent notifications (`cgos-opponent_*`), game-over notifications (`cgos-gameover`), or analysis-extended move generation.*

---

## 3. GTP Flow During Normal Games

### Sequence of Commands
1. Immediately After Engine Startup: `list_commands` is sent.
2. At Game Start: Board size and komi are configured (`boardsize`, `komi`, `clear_board`, etc.). Time settings and opponent info are sent if supported.  
   *Note: No GTP command is sent to configure rules (e.g., Chinese, Japanese, or NZ rules). The engine's rules must be configured externally (via command-line arguments or configuration files) to match the CGOS server settings.*
3. On Opponent's Turn: Each time the opponent plays, `play` is sent.
4. On Engine's Turn: `time_left` is sent if time management is supported, followed by `genmove` (or an analysis move command).
5. Move Response: The engine replies with a GTP coordinate (e.g., `Q16`), `pass`, or `resign`.
   - Note: Following the standard GTP specification, **moves returned by `genmove` must be applied to the engine's internal board state immediately**. The client will not echo the move back with `play`.
6. Steps 3 through 5 repeat until the game concludes. When the game ends, `cgos-gameover` is sent if supported.

### Game Start Initialization Order (Comparison)

Depending on the client implementation, the exact order of commands at game start differs. Engines should be written to accept initial configuration commands in either order.

| Client Type | Initialization Order |
| :--- | :--- |
| Python Client (Standard) | `boardsize` → `komi` → [`time_settings`] → [`cgos-opponent_name`] → [`cgos-opponent_rating`] → `clear_board` |
| Legacy Tcl Client | `boardsize` → `clear_board` → `komi` → [`time_settings`] |

*Commands in brackets `[` `]` are only sent if supported by the engine.*

> [!IMPORTANT]
> `clear_board` must clear the board position without resetting komi or time settings. This is because the Python client sends `komi` and `time_settings` before `clear_board`, whereas the legacy Tcl client sends `komi` after `clear_board`.

### Sequence Diagram

```text
list_commands
(Game-start initialization: use the client-specific order in the table above)

Opponent Turn: play <color> <move>
Own Turn:      [time_left <color> <time> 0]
               genmove <color>
               ← = <move> (coordinate / pass / resign)

(Repeat until game ends)
[cgos-gameover <result>]
```

> [!NOTE]
> - `play` takes color `b` or `w`, and either `pass` or a GTP coordinate: on a 19×19 board, a column letter `A`–`T` (skipping `I`) followed by a row number `1`–`19`; smaller boards use a subset.
> - `resign` is returned as a response to `genmove`. The engine never receives `play <color> resign`.

---

## 4. GTP Flow for Reconnecting and Resuming a Game

If the client reconnects with the same account after a network disconnection, the CGOS server retrieves the in-progress game and sends the entire move history to the client to reconstruct the position. The client then performs the following steps with the engine:

1. Re-executes the client-specific game-start initialization shown in the table above (bracketed commands are sent only if supported). Ensure that `clear_board` does not reset komi or time settings.
2. Replays all recorded moves from move 1 in sequence, alternating between `play b ...` and `play w ...`.
3. If It Is the Engine's Turn: The client sends `time_left` with the remaining time calculated by the server, followed immediately by `genmove` (or an analysis command).
   If It Is the Opponent's Turn: The client waits for the next move from the opponent.

```text
(Game-start initialization: use the client-specific order in the table above)
play b <Move 1>
play w <Move 2>
play b <Move 3>
...
If it is the engine's turn:
  [time_left <color> <remaining seconds> 0]
  genmove <color>
If it is the opponent's turn:
  Wait for the opponent's move
```

### Key Considerations for Game Resumption
- Replaying Own Moves via `play`:  
  During normal play, `play` is only sent for opponent moves. During reconnection, however, after the board is cleared, **all moves—including moves previously generated by the engine itself—are replayed via `play`**. The engine must be able to accept `play` commands for both black and white regardless of its assigned color.
- Full Position Reconstruction:  
  Engines cannot assume internal search trees or history caches will persist. They must be able to reach a legal, identical position purely by replaying the sequence of `play` commands from an empty board.
- Elapsed Time and Remaining Time:  
  Time spent on previous moves is not replayed. Only the actual remaining time at the current moment is sent via `time_left` before the next move. Because the game clock continues running on the server during disconnection, do not rely on any locally cached pre-disconnection time.
- Automatic Reconnection Behavior:  
  The legacy Tcl client reconnects automatically after a delay while keeping the engine process running. Depending on the failure path, the Python client either reconnects with the existing engine or restarts the engine process through its outer loop. When a new engine is started, initialization begins again with `list_commands`; after reconnecting to CGOS, the position is rebuilt using the sequence described above.

---

## 5. Minimal Implementation Checklist

Before connecting your engine to CGOS, verify that it satisfies the following items:

- [ ] `list_commands` returns a complete list including itself and all mandatory commands (`boardsize`, `clear_board`, `komi`, `play`, `genmove`, `quit`)
- [ ] All GTP responses begin with `=` (or `?` on error) and end with an empty line (two consecutive newlines: LF LF or CRLF CRLF)
- [ ] Repeated calls to `boardsize`, `clear_board`, and `komi` can start new games indefinitely without restarting the process
- [ ] `clear_board` clears the board position without resetting komi or time settings
- [ ] `play` accepts both black (`b`) and white (`w`) moves, as well as `pass`
- [ ] Moves generated by `genmove` are immediately reflected on the engine's internal board (the client will not echo them back via `play`)
- [ ] The position can be accurately reconstructed when all moves are replayed consecutively via `play` after `clear_board`
- [ ] If time management is enabled, both `time_settings` and `time_left` are implemented
- [ ] Diagnostic and debug logs are written to standard error (stderr), never to standard output (stdout)
