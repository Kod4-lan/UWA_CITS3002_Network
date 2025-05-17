"""
client.py

Connects to a Battleship server which runs the single-player game.
Simply pipes user input to the server, and prints all server responses.

TODO: Fix the message synchronization issue using concurrency (Tier 1, item 1).
"""

import socket
import threading

HOST = '127.0.0.1'
PORT = 5000

# Koda: A global variable to control the running state of the threads
running = True

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
    while running:
        line = rfile.readline()
        if not line:
            print("[INFO] Server disconnected.")
            break
        line = line.strip()

        # Recognized multi-line block: opponent board
        if line == "GRID":
            print("\n[Board]")
            while True:
                board_line = rfile.readline()
                if not board_line or board_line.strip() == "":
                    break
                print(board_line.strip())

        # Recognized multi-line block: self board
        elif line == "GRID_SELF":
            print("\n[Your Board]")
            while True:
                board_line = rfile.readline()
                if not board_line or board_line.strip() == "":
                    break
                print(board_line.strip())

        # All valid single-line structured messages
        else:
            # Print all non-empty lines
            if line != "":
                print(line)


def main():
    global running
    # Koda: Set up connection
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.connect((HOST, PORT))
        rfile = s.makefile('r')
        wfile = s.makefile('w')

        # Koda: Start a thread for receiving messages
        threading.Thread(target=receive_messages, args=(rfile,), daemon=True).start()

        try:
            while running:
                user_input = input(">> ")
                if user_input.lower() == "quit":
                    running = False
                wfile.write(user_input + '\n')
                wfile.flush()
        except KeyboardInterrupt:
            print("\n[INFO] Client exiting.")
            running = False

        except KeyboardInterrupt:
            print("\n[INFO] Client exiting.")

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