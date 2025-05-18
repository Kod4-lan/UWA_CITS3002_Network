import socket
import threading
from collections import deque
from game_logic import run_two_player_session
import time

HOST = '127.0.0.1'
PORT = 5000

waiting_clients = deque()
ready_queue = deque()
spectators = []

active_game_lock = threading.Lock()

def queue_notifier():
    while True:
        temp = []
        time.sleep(3)
        size = len(ready_queue)
        for idx in range(size):
            try:
                conn, rfile, wfile = ready_queue.popleft()
                wfile.write(f"MESSAGE Waiting in queue... you are #{idx + 1}\n")
                wfile.flush()
                temp.append((conn, rfile, wfile))
            except Exception as e:
                print(f"[WARN] Failed to notify waiting client: {e}")
        for item in reversed(temp):
            ready_queue.appendleft(item)

def client_listener(server_sock):
    while True:
        conn, addr = server_sock.accept()
        print(f"[INFO] New client from {addr}")
        rfile = conn.makefile('r')
        wfile = conn.makefile('w')

        try:
            # ✅ 判断必须在 acquire lock 之前做！
            if len(ready_queue) < 2 and not active_game_lock.locked():
                # 是 active player：允许进入 ready queue
                try:
                    wfile.write("MESSAGE Connected to BEER server. Waiting for a match...\n")
                    wfile.flush()
                    ready_queue.append((conn, rfile, wfile))
                except Exception as e:
                    print(f"[ERROR] Failed to connect player: {e}")
                    conn.close()
            else:
                # spectator
                try:
                    wfile.write("MESSAGE Connected as spectator. You will observe the current match.\n")
                    wfile.flush()
                    spectators.append((conn, rfile, wfile))
                except Exception as e:
                    print(f"[ERROR] Failed to connect spectator: {e}")
                    conn.close()
        except Exception as e:
            print(f"[ERROR] Unexpected error during client handling: {e}")
            conn.close()


def game_matchmaker():
    while True:
        if len(ready_queue) >= 2:
            if active_game_lock.locked():
                time.sleep(1)
                continue
            try:
                p1 = ready_queue.popleft()
                p2 = ready_queue.popleft()

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
                ready_queue.appendleft((survivor['conn'], survivor['rfile'], survivor['wfile']))
                print("[INFO] Survivor returned to ready queue.")
            except Exception as e:
                print(f"[WARN] Failed to requeue survivor: {e}")

def main():
    print(f"[INFO] Server listening on {HOST}:{PORT}")
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server_sock:
        server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server_sock.bind((HOST, PORT))
        server_sock.listen()

        threading.Thread(target=client_listener, args=(server_sock,), daemon=True).start()
        threading.Thread(target=queue_notifier, daemon=True).start()
        game_matchmaker()

if __name__ == "__main__":
    main()
