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
import queue
from game_logic import run_two_player_session

HOST = '127.0.0.1'
PORT = 5000

# Queue to hold waiting clients
waiting_clients = queue.Queue()

def client_listener(server_sock):
    # background thread, accept new clients and put them in the queue
    while True:
        conn, addr = server_sock.accept()
        print(f"[INFO] New client from {addr}")
        rfile = conn.makefile('r')
        wfile = conn.makefile('w')
        wfile.write("MESSAGE Connected to BEER server. Waiting for a match...\n")
        wfile.flush()
        waiting_clients.put((conn, rfile, wfile))

def game_matchmaker():
    # background thread, match clients from the queue
    while True:
        if waiting_clients.qsize() >= 2:
            p1 = waiting_clients.get()
            p2 = waiting_clients.get()
            print("[INFO] Starting a new game...")
            t = threading.Thread(
                target=start_game_session,
                args=(p1, p2),
                daemon=True
            )
            t.start()

def start_game_session(p1_raw, p2_raw):
    conn1, rfile1, wfile1 = p1_raw
    conn2, rfile2, wfile2 = p2_raw
    p1 = {"conn": conn1, "rfile": rfile1, "wfile": wfile1}
    p2 = {"conn": conn2, "rfile": rfile2, "wfile": wfile2}

    try:
        survivor = run_two_player_session(p1, p2)
    except Exception as e:
        print(f"[ERROR] Game session crashed: {e}")
        survivor = None
    finally:
        print("[INFO] Game session cleaned up.")
        if survivor:
            try:
                waiting_clients.put((survivor['conn'], survivor['rfile'], survivor['wfile']))
                print("[INFO] Survivor returned to waiting queue.")
            except Exception as e:
                print(f"[WARN] Failed to requeue survivor: {e}")

def main():
    print(f"[INFO] Server listening on {HOST}:{PORT}")
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server_sock:
        server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server_sock.bind((HOST, PORT))
        server_sock.listen()

        # Launch a thread to listen for new clients
        threading.Thread(target=client_listener, args=(server_sock,), daemon=True).start()
        # Launch a thread to match clients
        game_matchmaker()

if __name__ == "__main__":
    main()
