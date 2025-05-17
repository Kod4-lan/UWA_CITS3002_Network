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
from game_logic import run_two_player_game
# Koda: Server code for a two-player Battleship game

HOST = '127.0.0.1'
PORT = 5000

# Queue to store players who want to play again
waiting_players = []

# Ask a player if they want to play another game
def ask_play_again(player):
    try:
        player['wfile'].write("Game over. Play again? (yes/no):\n")
        player['wfile'].flush()
        response = player['rfile'].readline().strip().lower()
        return response == 'yes'
    except:
        return False

# Collect two active players, using old players first, then accepting new ones
def collect_two_players(server_sock):
    global waiting_players
    players = []

    # Use remaining players who chose to play again
    while waiting_players and len(players) < 2:
        p = waiting_players.pop(0)
        players.append(p)

    # Accept new players to complete the pair
    while len(players) < 2:
        conn, addr = server_sock.accept()
        print(f"[INFO] New player connected from {addr}")
        rfile = conn.makefile('r')
        wfile = conn.makefile('w')
        wfile.write(f"Welcome Player! Waiting for others to join...\n")
        wfile.flush()
        players.append({"conn": conn, "rfile": rfile, "wfile": wfile})

    return players

# Main server loop
def main():
    print(f"[INFO] Server listening on {HOST}:{PORT}")
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server_sock:
        server_sock.bind((HOST, PORT))
        server_sock.listen()

        while True:
            print("[INFO] Waiting for 2 players to start a new game...")
            p1, p2 = collect_two_players(server_sock)

            print("[INFO] Starting new game with 2 players.")
            run_two_player_game(p1, p2)

            # Ask players if they want to continue after the game ends
            again1 = ask_play_again(p1)
            again2 = ask_play_again(p2)

            if again1:
                waiting_players.append(p1)
            else:
                try: p1['conn'].close()
                except: pass

            if again2:
                waiting_players.append(p2)
            else:
                try: p2['conn'].close()
                except: pass

            print("[INFO] Game finished. Preparing next match...")


# HINT: For multiple clients, you'd need to:
# 1. Accept connections in a loop
# 2. Handle each client in a separate thread
# 3. Import threading and create a handle_client function

if __name__ == "__main__":
    main()