"""
client.py

Connects to a Battleship server which runs the single-player game.
Simply pipes user input to the server, and prints all server responses.

TODO: Fix the message synchronization issue using concurrency (Tier 1, item 1).
"""

import socket
import threading
import time
import uuid
from utils import (
    encode_packet,
    decode_packet,
    send_packet_message,
    PACKET_TYPE_MESSAGE,
    PACKET_TYPE_COMMAND,
    PACKET_TYPE_RESULT,
    PACKET_TYPE_CONTROL
)

HOST = '127.0.0.1'
PORT = 5000
# Koda: A global variable to control the running state of the threads
running = True
is_spectator = False

# HINT: The current problem is that the client is reading from the socket,
# then waiting for user input, then reading again. This causes server
# messages to appear out of order.
#
# Consider using Python's threading module to separate the concerns:
# - One thread continuously reads from the socket and displays messages
# - The main thread handles user input and sends it to the server
#
# import threading

def receive_messages(rfile, wfile, player_id):
    global is_spectator
    while running:
        try:
            line = rfile.readline()
            if not line:
                print("[INFO] Server disconnected.")
                break

            pkt_type, checksum, payload = decode_packet(line)
            if pkt_type is None:
                payload = line.strip()
                pkt_type = 1  # fallback to message

            # special commands
            if payload == "SEND-ID":
                wfile.write(f"ID {player_id}\n")
                wfile.flush()
                continue

            # Board: opponent's perspective
            if payload == "GRID_OPPONENT":
                print("\n[Opponent's Board]")
                while True:
                    board_line = rfile.readline()
                    if not board_line.strip():
                        break 
                    pkt_type, _, board_payload = decode_packet(board_line)
                    if pkt_type is None:
                        board_payload = board_line.strip()
                    print(board_payload)
                continue

            # Board: your perspective
            if payload == "GRID_SELF":
                print("\n[Your Board]")
                while True:
                    board_line = rfile.readline()
                    if not board_line.strip():
                        break
                    pkt_type, _, board_payload = decode_packet(board_line)
                    if pkt_type is None:
                        board_payload = board_line.strip()
                    print(board_payload)
                continue

            # Spectator mode
            if "Connected as spectator" in payload:
                is_spectator = True
                print(payload, flush=True)
                print(">> Spectator mode. No input required.", flush=True)
                continue
            elif "You are being promoted to a player" in payload:
                print(payload)
                print("[INFO] Sending player ID again...")
                wfile.write(f"ID {player_id}\n")
                wfile.flush()
                is_spectator = False
                continue


            if pkt_type == 1:  # MESSAGE
                print(payload, flush=True)
            elif pkt_type == 3:  # RESULT
                print("[Result]", payload, flush=True)
            elif pkt_type == 4:  # PING
                # Heartbeat ping - no output
                pass
            else:
                print(payload, flush=True)  # fallback 

        except Exception as e:
            print(f"[ERROR] Connection lost: {e}")
            break



def main():
    global running
    global is_spectator

    player_id = str(uuid.uuid4())
    print(f"[INFO] Your player ID: {player_id}")
    
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.connect((HOST, PORT))
        rfile = s.makefile('r')
        wfile = s.makefile('w')

        wfile.write(f"ID {player_id}\n")
        wfile.flush()


        threading.Thread(target=receive_messages, args=(rfile, wfile, player_id), daemon=True).start()


        try:
            while running:
                if is_spectator:
                    time.sleep(10)  # Spectators do not send input
                    continue

                user_input = input(">> ").strip()
                if user_input.lower() == "quit":
                    pkt = encode_packet(2, "quit")  # type 2 means command
                    wfile.write(pkt + '\n')
                    wfile.flush()
                    print("[INFO] Quitting game. Closing connection.")
                    running = False
                    wfile.close()
                    rfile.close()
                    s.shutdown(socket.SHUT_RDWR)
                    s.close()
                    break

                pkt = encode_packet(2, user_input)
                wfile.write(pkt + '\n')
                wfile.flush()


        except KeyboardInterrupt:
            print("\n[INFO] Client exiting.")
            running = False

# HINT: A better approach would be something like:
#
# def receive_messages(rfile):
#     """Continuously receive and display messages from the server"""
#     while running:
#         line = rfile.readline()
#         if not line:
#             print("[INFO] Server disconnected.")
#             break
#         # Process and display the message
#
# def main():
#     # Set up connection
#     # Start a thread for receiving messages
#     # Main thread handles sending user input

if __name__ == "__main__":
    main()