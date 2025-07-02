### Binary SGF Data Format Documentation

This document describes the custom binary format used to store and transmit Go game data (SGF files). The format is designed for efficiency, especially for streaming ongoing games where new moves are frequently appended.

The server-side implementation can be found in `server-python/cgos/app/cgos.py` within the `saveSgf` function, and the client-side parser is in `wgo_view/cgos_viewer/viewer_inner.js` in the `decode` method.

#### 1. Overview

The binary format is not a single compressed file. Instead, it is a **sequence of data chunks**. Each chunk represents a small part of the SGF file, typically a single move or a part of the game header.

This chunk-based structure allows a client to fetch and parse game data incrementally. As a game progresses, the server appends new chunks to the binary file, and a web viewer can fetch only the new data without re-downloading the entire file.

#### 2. Chunk Structure

Each chunk in the file consists of two parts: a 4-byte header and a variable-length payload.

```
+----------------------+--------------------------------+
| Header (4 bytes)     | Payload (Variable Size)        |
+----------------------+--------------------------------+
```

*   **Header**: A signed 32-bit integer in little-endian byte order. This integer serves two purposes:
    1.  It indicates whether the following payload is compressed.
    2.  It specifies the length of the payload in bytes.

*   **Payload**: The raw or compressed SGF data segment, encoded in UTF-8.

#### 3. Compression Logic

The server uses zlib to compress each chunk. However, compression is only applied if it results in a smaller data size. The sign of the header's integer value indicates whether the payload is compressed.

*   **If the Header value is positive (+)**:
    *   The payload is **uncompressed**.
    *   The header's value is the exact size of the uncompressed payload data in bytes.

*   **If the Header value is negative (-)**:
    *   The payload is **compressed** using zlib.
    *   The absolute value of the header is the size of the compressed payload data in bytes.

This logic provides a simple and effective optimization, avoiding the overhead of compression for small data chunks where it would not be beneficial.

#### 4. File Assembly

The complete `.bin` file is formed by concatenating these chunks sequentially.

**Conceptual Layout:**

```
[Chunk 1] [Chunk 2] [Chunk 3] ... [Chunk N]
```

**Example:**

```
+-------------------+----------------------+-------------------+----------------------+
| 4-byte Length 1   | Payload 1            | 4-byte Length 2   | Payload 2            |
| (e.g., -48)       | (zlib-compressed)    | (e.g., 22)        | (uncompressed)       |
+-------------------+----------------------+-------------------+----------------------+...
```

#### 5. Decoding Process

To reconstruct the full SGF content from the binary format, a client must:

1.  Read the first 4 bytes of the file to get the signed, little-endian 32-bit integer (let's call it `chunkSize`).
2.  Check the sign of `chunkSize`:
    *   If `chunkSize` is negative, read the next `abs(chunkSize)` bytes and decompress them using a zlib library (like `pako` in the provided JavaScript code).
    *   If `chunkSize` is positive, read the next `chunkSize` bytes directly.
3.  Decode the resulting data (either decompressed or read directly) as a UTF-8 string. This string is one piece of the SGF file.
4.  Append this string to the reconstructed SGF content.
5.  Repeat from step 1, starting from the byte immediately following the payload just processed, until the end of the file is reached.
