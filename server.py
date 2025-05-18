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
from collections import deque
from game_logic import run_two_player_session
import time

HOST = '127.0.0.1'
PORT = 5000

# Queue to hold waiting clients
waiting_clients = deque()
active_game_lock = threading.Lock()
# A global variable to control the running state of the threads

def queue_notifier():
    # notifies clients in the queue about their position
    # in the queue every 3 seconds
    while True:
        time.sleep(3)  # wait for 3 seconds

        temp = []
        size = len(waiting_clients)
        for idx in range(size):
            try:
                conn, rfile, wfile = waiting_clients.popleft()
                wfile.write(f"MESSAGE Waiting in queue... you are #{idx + 1}\n")
                wfile.flush()
                temp.append((conn, rfile, wfile))
            except:
                pass  # skip if client is not available

        # put clients back in the queue
        for item in temp:
            waiting_clients.appendleft(item)


def client_listener(server_sock):
    # background thread, accept new clients and put them in the queue
    while True:
        conn, addr = server_sock.accept()
        print(f"[INFO] New client from {addr}")
        rfile = conn.makefile('r')
        wfile = conn.makefile('w')
        wfile.write("MESSAGE Connected to BEER server. Waiting for a match...\n")
        wfile.flush()
        waiting_clients.append((conn, rfile, wfile))

def game_matchmaker():
    while True:
        if len(waiting_clients) >= 2:
            if active_game_lock.locked():
                time.sleep(1)
                continue  # Can only have one game at a time

            try:
                p1 = waiting_clients.popleft()
                p2 = waiting_clients.popleft()

                # Lock before starting a new game
                active_game_lock.acquire()
                print("[INFO] Starting a new game...")

                t = threading.Thread(
                    target=start_game_session_with_unlock,
                    args=(p1, p2),
                    daemon=True
                )
                t.start()
            except IndexError:
                time.sleep(1)

def start_game_session_with_unlock(p1_raw, p2_raw):
    #release the lock after the game session is done
    try:
        start_game_session(p1_raw, p2_raw)
    finally:
        active_game_lock.release()
        print("[INFO] Game finished. Lock released.")


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
                waiting_clients.appendleft((survivor['conn'], survivor['rfile'], survivor['wfile']))
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
        threading.Thread(target=queue_notifier, daemon=True).start()
        game_matchmaker()

if __name__ == "__main__":
    main()