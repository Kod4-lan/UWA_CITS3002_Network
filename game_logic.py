import socket
import threading
from queue import Queue
from battleship import run_single_player_game_online, Board, parse_coordinate, SHIPS

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

    while waiting_players and len(players) < 2:
        p = waiting_players.pop(0)
        players.append(p)

    while len(players) < 2:
        conn, addr = server_sock.accept()
        print(f"[INFO] New player connected from {addr}")
        rfile = conn.makefile('r')
        wfile = conn.makefile('w')
        wfile.write(f"Welcome Player! Waiting for others to join...\n")
        wfile.flush()
        players.append({"conn": conn, "rfile": rfile, "wfile": wfile})

    return players

# Thread that continuously reads player input and pushes to queue
def start_input_listener(player, input_queue, notify_queue):
    def listen():
        try:
            while True:
                line = player['rfile'].readline()
                if not line:
                    input_queue.put(None)
                    break
                notify_queue.put((player, line.strip()))
        except:
            input_queue.put(None)
    threading.Thread(target=listen, daemon=True).start()

# Two-player game loop with correct win detection and input ownership enforcement
def run_two_player_game(p1, p2):
    p1['wfile'].write("Both players connected! Game will start soon...\n")
    p2['wfile'].write("Both players connected! Game will start soon...\n")
    p1['wfile'].flush()
    p2['wfile'].flush()

    setup_player_board(p1)
    setup_player_board(p2)

    send_own_board(p1['wfile'], p1['board'])
    send_own_board(p2['wfile'], p2['board'])

    p1['wfile'].write("Game started! You are Player 1.\n")
    p2['wfile'].write("Game started! You are Player 2.\n")
    p1['wfile'].write("You go first.\n")
    p2['wfile'].write("Waiting for Player 1 to move...\n")
    p1['wfile'].flush()
    p2['wfile'].flush()

    players = [p1, p2]
    notify_queue = Queue()
    for i in range(2):
        start_input_listener(players[i], Queue(), notify_queue)

    turn = 0

    while True:
        current = players[turn]
        opponent = players[1 - turn]

        send_board(current['wfile'], opponent['board'])
        current['wfile'].write("Your turn! Enter command (e.g. FIRE B5):\n")
        current['wfile'].flush()

        while True:
            sender, line = notify_queue.get()

            if sender != current:
                sender['wfile'].write("It's not your turn. Please wait.\n")
                sender['wfile'].flush()
                continue

            if line is None:
                opponent['wfile'].write("MESSAGE Opponent disconnected\n")
                opponent['wfile'].write("RESULT WIN\n")
                opponent['wfile'].flush()
                return

            line = line.strip()
            if line.lower() == 'quit':
                current['wfile'].write("RESULT FORFEIT\n")
                opponent['wfile'].write("MESSAGE Opponent quit\n")
                opponent['wfile'].write("RESULT WIN\n")
                current['wfile'].flush()
                opponent['wfile'].flush()
                return

            parts = line.split()
            if len(parts) != 2 or parts[0].upper() != "FIRE":
                current['wfile'].write("RESULT INVALID INPUT (Use: FIRE B5)\n")
                current['wfile'].flush()
                continue

            try:
                row, col = parse_coordinate(parts[1])
                result, sunk = opponent['board'].fire_at(row, col)

                if result == 'hit':
                    if sunk:
                        current['wfile'].write(f"RESULT HIT! {sunk.upper()}\n")
                    else:
                        current['wfile'].write("RESULT HIT\n")
                elif result == 'miss':
                    current['wfile'].write("RESULT MISS\n")
                elif result == 'already_shot':
                    current['wfile'].write("RESULT HIT ALREADY\n")
                current['wfile'].flush()

                send_board(current['wfile'], opponent['board'])

                if opponent['board'].all_ships_sunk():
                    current['wfile'].write("RESULT YOU WIN\n")
                    opponent['wfile'].write("RESULT YOU LOSE\n")
                    current['wfile'].flush()
                    opponent['wfile'].flush()
                    return

                turn = 1 - turn
                break

            except Exception as e:
                current['wfile'].write("RESULT INVALID COORD\n")
                current['wfile'].flush()
                continue

# ... (setup_player_board, send_board, send_own_board, main remain unchanged)


def setup_player_board(player):
    wfile = player['wfile']
    rfile = player['rfile']
    wfile.write("Place ships manually (M) or randomly (R)? [M/R]:\n")
    wfile.flush()
    choice = rfile.readline().strip().upper()

    board = Board()
    if choice == 'M':
        for ship_name, ship_size in SHIPS:
            while True:
                wfile.write(f"Placing {ship_name} (size {ship_size})\n")
                wfile.write("Enter starting coordinate (e.g. A1):\n")
                wfile.flush()
                coord_str = rfile.readline().strip()

                wfile.write("Orientation? Enter 'H' or 'V':\n")
                wfile.flush()
                orientation_str = rfile.readline().strip().upper()

                try:
                    row, col = parse_coordinate(coord_str)
                    orientation = 0 if orientation_str == 'H' else 1 if orientation_str == 'V' else -1
                    if orientation == -1:
                        wfile.write("Invalid orientation. Please enter H or V.\n")
                        wfile.flush()
                        continue

                    if board.can_place_ship(row, col, ship_size, orientation):
                        positions = board.do_place_ship(row, col, ship_size, orientation)
                        board.placed_ships.append({
                            'name': ship_name,
                            'positions': positions
                        })
                        break
                    else:
                        wfile.write("Invalid position. Try again.\n")
                        wfile.flush()
                except Exception as e:
                    wfile.write(f"Error: {e}\n")
                    wfile.flush()
    else:
        board.place_ships_randomly(SHIPS)
        wfile.write("Ships placed randomly.\n")
        wfile.flush()

    player['board'] = board

def send_board(wfile, board):
    wfile.write("GRID\n")
    wfile.write("  " + " ".join(str(i + 1).rjust(2) for i in range(board.size)) + '\n')
    for r in range(board.size):
        row_label = chr(ord('A') + r)
        row_str = " ".join(board.display_grid[r][c] for c in range(board.size))
        wfile.write(f"{row_label:2} {row_str}\n")
    wfile.write('\n')
    wfile.flush()

def send_own_board(wfile, board):
    wfile.write("GRID_SELF\n")
    wfile.write("  " + " ".join(str(i + 1).rjust(2) for i in range(board.size)) + '\n')
    for r in range(board.size):
        row_label = chr(ord('A') + r)
        row_str = " ".join(board.hidden_grid[r][c] for c in range(board.size))
        wfile.write(f"{row_label:2} {row_str}\n")
    wfile.write('\n')
    wfile.flush()

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

if __name__ == "__main__":
    main()
