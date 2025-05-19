# UWA_CITS3002_Network：

---

# BEER - Battleships: Engage in Explosive Rivalry

A turn-based, networked Battleship game built for the CITS3002 Computer Networks project.

## 🗂️ File Overview

| File                | Purpose |
|---------------------|---------|
| `server.py`         | Server entry point, manages game sessions, clients, matchmaking, and spectators |
| `client.py`         | Main client used by players and spectators |
| `client_fixed_ID.py`| Debug client with fixed ID for reconnect testing |
| `game_logic.py`     | Game flow, reconnection handling, turn management |
| `utils.py`          | Protocol encoding/decoding with checksum validation |
| `battleship.py`     | Core board logic: placement, hits, ship state |


## 🚀 Features Implemented

### ✅ Tier 1: Basic 2-Player Concurrency

* Two-player server with concurrent handling using threads.
* Each player can place ships and take turns firing at coordinates.
* Client supports concurrent input/output to avoid message synchronization issues.

### ✅ Tier 2: Game Flow Robustness

* Input validation: handles out-of-turn moves, bad coordinates, malformed commands.
* Supports multiple game sessions without restarting the server.
* 30-second turn timeout: a missed turn leads to forfeiting the round.
* Graceful disconnection handling: players who disconnect are treated as forfeiting.
* Extra clients are placed in a waiting queue.

### ✅ Tier 3: Spectator Support & Reconnection

* Supports >2 connections: only 2 active players, others are spectators.
* Spectators receive real-time updates of the game.
* Disconnected players may reconnect within 60 seconds using their client ID.
* Next-match queue: once a game ends, next two clients are selected automatically.
### ✅ Tier 4.1: Custom Protocol with Checksum
Introduced a custom structured protocol format:


<type>|<checksum>|<payload>
where:

type: packet type (e.g., 1 = MESSAGE, 2 = COMMAND, 4 = PING)

checksum: CRC32 of type|payload for integrity checking

payload: game or control message content

Implemented encode_packet() and decode_packet() to generate and verify CRC32 checksums using zlib.crc32.

The client and server now exchange all messages using this structured protocol to ensure data integrity.

Corrupted packets (e.g., wrong checksum) are detected and safely ignored or handled with fallbacks; malformed inputs do not crash the system.

The system is resilient to packet corruption:
if a checksum mismatch is detected during decoding, the packet is discarded or the payload is sanitized.

(Optional extension support) Statistics can be collected by counting corrupted packets during transmission (e.g., decode failure counter).