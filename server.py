"""
server.py

Serves a single-player Battleship session to one connected client.
Game logic is handled entirely on the server using battleship.py.
Client sends FIRE commands, and receives game feedback.

TODO: For Tier 1, item 1, you don't need to modify this file much. 
The core issue is in how the client handles incoming messages.
However, if you want to support multiple clients (i.e. progress through further Tiers), you'll need concurrency here too.
"""

import socket
import threading
from battleship import run_single_player_game_online,Board, parse_coordinate, SHIPS
from game_logic import run_single_game, run_two_player_session
# Koda: Server code for a two-player Battleship game

HOST = '127.0.0.1'
PORT = 5000

clients = []  # [(conn, addr, rfile, wfile)]

def handle_client(player_id, conn, addr, rfile, wfile, start_event):
    # Koda: Waiting for the client to send a command
    wfile.write(f"Welcome Player {player_id + 1}! Waiting for the other player to connect...\n")
    wfile.flush()
    start_event.wait()  # Koda: Block until both players are connected
    wfile.flush() 
    # Koda: Placeholder for the game logic  


def main():
    print(f"[INFO] Server listening on {HOST}:{PORT}")
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server_sock:
        server_sock.bind((HOST, PORT))
        server_sock.listen(2)

        start_event = threading.Event()

        for player_id in range(2):
            conn, addr = server_sock.accept()
            print(f"[INFO] Player {player_id + 1} connected from {addr}")
            rfile = conn.makefile('r')
            wfile = conn.makefile('w')
            clients.append((conn, addr, rfile, wfile))

            thread = threading.Thread(
                target=handle_client,
                args=(player_id, conn, addr, rfile, wfile, start_event),
                daemon=True
            )
            thread.start()
        # Koda: Wait for both players to connect
        print("[INFO] Both players connected. Game can begin.")
        start_event.set()
        p1 = {"conn": clients[0][0], "rfile": clients[0][2], "wfile": clients[0][3]}
        p2 = {"conn": clients[1][0], "rfile": clients[1][2], "wfile": clients[1][3]}
        run_two_player_session(p1, p2)

# HINT: For multiple clients, you'd need to:
# 1. Accept connections in a loop
# 2. Handle each client in a separate thread
# 3. Import threading and create a handle_client function

if __name__ == "__main__":
    main()