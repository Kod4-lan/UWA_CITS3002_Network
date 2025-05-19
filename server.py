import socket
import threading
from collections import deque
from game_logic import run_two_player_session
import time
import traceback
from utils import encode_packet, decode_packet, send_packet_message
'''
PACKET_TYPE_MESSAGE = 1
PACKET_TYPE_COMMAND = 2
PACKET_TYPE_RESULT = 3
PACKET_TYPE_CONTROL = 4
'''

HOST = '127.0.0.1'
PORT = 5000

waiting_clients = deque()
ready_queue = deque()
spectators = []

active_game_lock = threading.Lock()

player_session = {}

def queue_notifier():
    while True:
        temp = []
        time.sleep(3)
        size = len(ready_queue)
        for idx in range(size):
            try:
                conn, rfile, wfile, _ = ready_queue.popleft()
                send_packet_message(wfile, 1, f"MESSAGE Waiting in queue... you are #{idx + 1}")
                temp.append((conn, rfile, wfile, _))
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

        id_line = rfile.readline()
        if not id_line or not id_line.startswith("ID "):
            print("[WARN] Invalid or missing ID line.")
            conn.close()
            continue

        player_id = id_line.strip().split(" ", 1)[1]
        print(f"[INFO] Received player ID: {player_id}")

        try:
            # Reconnect logic
            if player_id in player_session and player_session[player_id]['status'] == 'disconnected':
                player_session[player_id]['conn'] = conn
                player_session[player_id]['rfile'] = rfile
                player_session[player_id]['wfile'] = wfile
                player_session[player_id]['status'] = 'reconnected'
                player_session[player_id]['last_seen'] = time.time()
                print(f"[INFO] Player {player_id} reconnected.")
                
                # After reconect,go back directly to the game
                continue

            # If timeout or new session
            player_session[player_id] = {
                'conn': conn,
                'rfile': rfile,
                'wfile': wfile,
                'status': 'connected',
                'last_seen': time.time()
            }

            if len(ready_queue) < 2 and not active_game_lock.locked():
                try:
                    send_packet_message(wfile, 1, "MESSAGE Connected as player. Waiting for a match...")
                    ready_queue.append((conn, rfile, wfile, player_id))
                except Exception as e:
                    print(f"[ERROR] Failed to connect player: {e}")
                    conn.close()
            else:
                try:
                    send_packet_message(wfile, 1, "MESSAGE Spectator mode. Waiting for a match...")
                    spectators.append((conn, rfile, wfile))
                except Exception as e:
                    print(f"[ERROR] Failed to connect spectator: {e}")
                    conn.close()

        except Exception as e:
            print(f"[ERROR] Unexpected error during client handling: {e}")
            conn.close()



def game_matchmaker():
    while True:
        if len(ready_queue) >= 2 and not active_game_lock.locked():
            p1 = ready_queue.popleft()
            p2 = ready_queue.popleft()

            conn1, rfile1, wfile1, player1_id = p1
            conn2, rfile2, wfile2, player2_id = p2

            print("[INFO] Starting a new game...")
            print(f"[DEBUG] p1: {p1}")
            print(f"[DEBUG] p2: {p2}")

            def start():
                with active_game_lock:
                    survivor = run_two_player_session(
                        {"conn": conn1, "rfile": rfile1, "wfile": wfile1, "player_id": player1_id},
                        {"conn": conn2, "rfile": rfile2, "wfile": wfile2, "player_id": player2_id},
                        spectators,
                        player_session
                    )

                    if survivor:
                        try:
                            send_packet_message(survivor['wfile'], 1, "Waiting for a new opponent...")
                        except Exception:
                            print("[WARN] Could not notify survivor.")
                        ready_queue.append((
                            survivor['conn'],
                            survivor['rfile'],
                            survivor['wfile'],
                            survivor['player_id']
                        ))

                    # ✅ check if there are spectators waiting
                    while len(ready_queue) < 2 and spectators:
                        new_conn, new_rfile, new_wfile = spectators.pop(0)
                        try:
                            #check if the connection is still alive
                            send_packet_message(new_wfile, 4, "PING")
                        except Exception as e:
                            print(f"[SKIP] Spectator connection dead, skipping: {e}")
                            continue  

                        try:
                            send_packet_message(new_wfile, 1, "You are being promoted to a player. Send your ID again.")
                            send_packet_message(new_wfile, 2, "SEND-ID")
                            id_line = new_rfile.readline()
                            if id_line.startswith("ID "):
                                new_id = id_line.strip().split(" ", 1)[1]
                                print(f"[INFO] Promoted spectator with ID: {new_id}")
                                player_session[new_id] = {
                                    'conn': new_conn,
                                    'rfile': new_rfile,
                                    'wfile': new_wfile,
                                    'status': 'connected',
                                    'last_seen': time.time()
                                }
                                ready_queue.append((new_conn, new_rfile, new_wfile, new_id))
                            else:
                                print("[WARN] Spectator failed to send ID.")
                        except Exception as e:
                            print(f"[ERROR] Failed to promote spectator: {e}")

                    print("[INFO] Game session cleaned up.")
                    print("[INFO] Game finished. Lock released.")

            threading.Thread(target=start, daemon=True).start()

        time.sleep(1)



def start_game_session_with_unlock(p1_raw, p2_raw, spectators):
    try:
        start_game_session(p1_raw, p2_raw, spectators)
    finally:
        active_game_lock.release()
        print("[INFO] Game finished. Lock released.")

def start_game_session(p1_raw, p2_raw, spectators):
    conn1, rfile1, wfile1, player_id1 = p1_raw
    conn2, rfile2, wfile2, player_id2 = p2_raw
    p1 = {"conn": conn1, "rfile": rfile1, "wfile": wfile1, "player_id": player_id1}
    p2 = {"conn": conn2, "rfile": rfile2, "wfile": wfile2, "player_id": player_id2}


    try:
        survivor = run_two_player_session(p1, p2, spectators, player_session)
    except Exception as e:
        print(f"[ERROR] Game session crashed: {e}")
        traceback.print_exc()
        survivor = None
    finally:
        print("[INFO] Game session cleaned up.")
        if survivor:
            try:
                ready_queue.appendleft((survivor['conn'], survivor['rfile'], survivor['wfile'], survivor['player_id']))
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
        threading.Thread(target=game_matchmaker, daemon=True).start()

        while True:
            time.sleep(1)

if __name__ == "__main__":
    main()
