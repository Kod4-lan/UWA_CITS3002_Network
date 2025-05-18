"""
client.py

Connects to a Battleship server which runs the single-player game.
Simply pipes user input to the server, and prints all server responses.

TODO: Fix the message synchronization issue using concurrency (Tier 1, item 1).
"""

import socket
import threading
import time

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

def receive_messages(rfile):
    global is_spectator
    while running:
        try:
            line = rfile.readline()
            if not line:
                print("[INFO] Server disconnected.")
                break

            line = line.strip()

            if line == "GRID":
                print("\n[Board]")
                while True:
                    board_line = rfile.readline()
                    if not board_line or board_line.strip() == "":
                        break
                    print(board_line.strip(), flush=True)

            elif line == "GRID_SELF":
                print("\n[Your Board]")
                while True:
                    board_line = rfile.readline()
                    if not board_line or board_line.strip() == "":
                        break
                    print(board_line.strip(), flush=True)

            elif line.startswith("MESSAGE Connected as spectator"):
                is_spectator = True
                print(line, flush=True)
                print(">> Spectator mode. No input required.", flush=True)

            elif line.startswith(("RESULT", "MESSAGE")):
                print(line, flush=True)

            else:
                # Default print for prompts or other messages
                print(line, flush=True)

        except Exception as e:
            print(f"[ERROR] Connection lost: {e}")
            break


def main():
    global running
    global is_spectator

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.connect((HOST, PORT))
        rfile = s.makefile('r')
        wfile = s.makefile('w')

        threading.Thread(target=receive_messages, args=(rfile,), daemon=True).start()

        try:
            while running:
                if is_spectator:
                    time.sleep(10)  # Spectators do not send input
                    continue

                user_input = input(">> ").strip()
                if user_input.lower() == "quit":
                    print("[INFO] Quitting game. Closing connection.")
                    running = False
                    wfile.close()
                    rfile.close()
                    s.shutdown(socket.SHUT_RDWR)
                    s.close()
                    break

                wfile.write(user_input + '\n')
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