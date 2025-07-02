# CGOS GTP Extension for Move Analysis

## 1. Intent

The primary goal of this extension is to enable Go engines to provide detailed analysis (including win rate, score, principal variations, and territory ownership) for each move during a game. This information can then be stored by the CGOS server and visualized in a web-based game viewer, offering a richer experience for spectators of AI tournaments.

![image](https://user-images.githubusercontent.com/162515/213919556-12102f4b-63b9-42e2-977c-a72f767e7895.png)

## 2. System Architecture and Data Flow

The analysis data flows through four main components:

1.  **Go Engine**: The AI that analyzes the position and generates moves (e.g., KataGo, Leela Zero).
2.  **Client Bridge (`gtpengine.py`)**: A script that communicates with the Go Engine via GTP. It is responsible for translating the engine's analysis into the standard JSON format required by the CGOS server.
3.  **CGOS Server (`cgos.py`)**: The central server that manages games. It receives moves and the associated analysis JSON from the Client Bridge.
4.  **Web Viewer (`player.cgos.js`)**: The frontend application that displays the game board, moves, and the analysis data provided by the engine.

The data flow is as follows:

1.  The **CGOS Server** sends a `genmove` command to the **Client Bridge**.
2.  The **Client Bridge** sends an analysis command (e.g., `kata-genmove_analyze`) to the **Go Engine**.
3.  The **Go Engine** performs its search and returns the analysis results in its native format.
4.  The **Client Bridge** parses the engine's output and constructs a **single-line JSON string** containing the standardized analysis data.
5.  The **Client Bridge** sends the chosen move followed by the JSON string to the **CGOS Server** (e.g., `O15 {"winrate":0.13,...}`).
6.  The **CGOS Server** receives the move and the JSON payload. It saves the move to the SGF record and stores the entire JSON payload in the **SGF Comment property (`C[]`)** for that move.
7.  The **Web Viewer** loads the SGF file, reads the comment for the current move, parses the JSON, and uses the data to display graphs, territory maps, and principal variations.

## 3. GTP Command: `cgos-genmove_analyze`

This is the standardized GTP command that a Client Bridge can use to request analysis from a Go Engine. While a client can adapt the output from other commands (like `kata-genmove_analyze`), engines can also implement this command natively for direct compatibility.

**Command:** `cgos-genmove_analyze <color>`

**Response:**
The engine should output the analysis information as a **single-line JSON string** on one line, followed by the chosen move in the format `play <coordinate>` on the next line.

**GTP Exchange Example:**

```
(client bridge -> engine)
cgos-genmove_analyze w

(engine -> client bridge)
=
{"winrate":0.13,"score":-11.5,"visits":258,"moves":[...],"ownership":"..."}
play O15

```

The Client Bridge then parses this response to send `O15 {"winrate":0.13,...}` to the CGOS server.

## 4. Analysis JSON Format

The JSON payload contains the root analysis and a list of candidate moves.

**Root Fields:**

| Key | Type | Description |
| :--- | :--- | :--- |
| `winrate` | float | The overall win rate for the current player, from their perspective. A value of `1.0` is a certain win, `0.0` is a certain loss. |
| `score` | float | The expected score difference (e.g., Black's score - White's score), including komi. A positive value favors the current player. |
| `visits` | integer | The total number of search visits (playouts) performed from the root position. |
| `moves` | array | An array of JSON objects, each describing a candidate move (see below). |
| `ownership`| string | A 361-character string representing the predicted territory ownership for a 19x19 board. See section 5 for the encoding scheme. |
| `comment` | string | An optional, UTF-8 encoded comment from the engine. |

**`moves` Object Fields:**

| Key | Type | Description |
| :--- | :--- | :--- |
| `move` | string | The move in GTP coordinates (e.g., "O15", "pass"). |
| `visits` | integer | The number of search visits for this specific move. |
| `winrate` | float | The win rate after this move is played. |
| `score` | float | The expected score after this move is played. |
| `prior` | float | The prior probability of this move from the policy network. |
| `pv` | string | A space-separated string of the principal variation (best line of play) *following* this move. |

### JSON Example

*Note: The JSON must be sent as a single line without extra whitespace. The formatting here is for readability.*

```json
{
  "winrate": 0.13,
  "score": -11.5,
  "visits": 258,
  "moves": [
    {
      "move": "O15",
      "visits": 189,
      "winrate": 0.1355,
      "score": -11.2142,
      "prior": 0.831028,
      "pv": "P17 O18 N17 O8 P6 N7 Q7 O6 P5"
    },
    {
      "move": "M16",
      "visits": 69,
      "winrate": 0.111084,
      "score": -12.2514,
      "prior": 0.123766,
      "pv": "N17 O15 L16 O18"
    }
  ],
  "ownership": "y356789...kQDCC",
  "comment": "A UTF-8 comment from the engine."
}
```

## 5. Ownership String Encoding

The `ownership` string is a compact way to represent the predicted owner of each point on the board.

- The string has 361 characters for a 19x19 board, starting from the top-left (A19) and ending at the bottom-right (T1), proceeding row by row.
- Each character corresponds to a point on the board and encodes a float value between -1.0 (100% opponent's territory) and +1.0 (100% player's territory). A value of 0.0 is neutral.
- The float is mapped to one of 63 characters (`A-Z`, `a-z`, `0-9`, `+`, `/`).

Here is the reference Python implementation for encoding the ownership array:

```python
def encodeOwnership(ownership: List[float]) -> str:
    """
    Encodes a list of ownership values (-1.0 to 1.0) into a compact string.
    """
    CHARS = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/"

    def encode(r: float) -> str:
        # Normalize the value from [-1.0, 1.0] to [0.0, 1.0]
        i = max(0, min((r + 1) / 2, 1))
        # Scale to an index in the CHARS string
        return CHARS[round(i * 62)]

    return "".join([encode(f) for f in ownership])
```

## 6. Interoperability with Other Engines

The provided **Client Bridge (`gtpengine.py`)** is designed to be a versatile adapter. It is not limited to engines that have natively implemented the `cgos-genmove_analyze` command. The bridge includes parsers for the analysis output of popular engines like **KataGo** and **Leela Zero**.

This means you can use engines that support `kata-genmove_analyze` or `lz-genmove_analyze` without any modification to the engine itself. The Client Bridge will automatically:

1.  Detect the appropriate analysis command (`kata-genmove_analyze`, `lz-genmove_analyze`, or `cgos-genmove_analyze`) supported by the engine.
2.  Call that command.
3.  Parse the engine's native output format.
4.  Convert the parsed data into the standardized CGOS JSON format before sending it to the CGOS server.

This approach ensures broad compatibility and allows various engines to be used within the CGOS ecosystem.
