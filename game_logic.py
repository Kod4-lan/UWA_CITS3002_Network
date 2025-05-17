from battleship import Board, parse_coordinate, SHIPS
import threading

def run_two_player_game(p1, p2):
    # Notify both players the game is starting
    p1['wfile'].write("Both players connected! Game will start soon...\n")
    p2['wfile'].write("Both players connected! Game will start soon...\n")
    p1['wfile'].flush()
    p2['wfile'].flush()

    # Ship placement
    setup_player_board(p1)
    setup_player_board(p2)

    # Send boards
    send_own_board(p1['wfile'], p1['board'])
    send_own_board(p2['wfile'], p2['board'])

    # Game intro
    p1['wfile'].write("Game started! You are Player 1.\n")
    p2['wfile'].write("Game started! You are Player 2.\n")
    p1['wfile'].write("You go first.\n")
    p2['wfile'].write("Waiting for Player 1 to make their move...\n")
    p1['wfile'].flush()
    p2['wfile'].flush()

    players = [p1, p2]
    turn = 0

    while True:
        current = players[turn]
        opponent = players[1 - turn]

        # Show opponent board
        send_board(current['wfile'], opponent['board'])
        current['wfile'].write("Your turn! Enter command (e.g. FIRE B5):\n")
        current['wfile'].flush()

        try:
            line = current['rfile'].readline()
            if not line:
                # Graceful disconnect
                opponent['wfile'].write("MESSAGE Opponent disconnected\n")
                opponent['wfile'].write("RESULT WIN\n")
                opponent['wfile'].flush()
                break
        except Exception:
            # Force disconnect / socket closed
            opponent['wfile'].write("MESSAGE Opponent disconnected unexpectedly\n")
            opponent['wfile'].write("RESULT WIN\n")
            opponent['wfile'].flush()
            break

        line = line.strip()

        if line.lower() == 'quit':
            # Player voluntarily quits
            current['wfile'].write("RESULT FORFEIT\n")
            opponent['wfile'].write("MESSAGE Opponent quit\n")
            opponent['wfile'].write("RESULT WIN\n")
            current['wfile'].flush()
            opponent['wfile'].flush()
            break

        parts = line.split()
        if len(parts) != 2 or parts[0].upper() != "FIRE":
            current['wfile'].write("RESULT INVALID INPUT (e.g. FIRE B2)\n")
            current['wfile'].flush()
            continue

        try:
            row, col = parse_coordinate(parts[1])
            result, sunk = opponent['board'].fire_at(row, col)

            if result == 'hit':
                if opponent['board'].all_ships_sunk():
                    if sunk:
                        current['wfile'].write(f"RESULT HIT {sunk.upper()}\n")
                    else:
                        current['wfile'].write("RESULT HIT\n")
                    current['wfile'].write("RESULT WIN\n")
                    opponent['wfile'].write("RESULT LOSE\n")
                    current['wfile'].flush()
                    opponent['wfile'].flush()
                    break
                else:
                    if sunk:
                        current['wfile'].write(f"RESULT HIT {sunk.upper()}\n")
                    else:
                        current['wfile'].write("RESULT HIT\n")
            elif result == 'miss':
                current['wfile'].write("RESULT MISS\n")
            elif result == 'already_shot':
                current['wfile'].write("RESULT ALREADY\n")
            current['wfile'].flush()

            send_board(current['wfile'], opponent['board'])
            turn = 1 - turn

        except Exception as e:
            current['wfile'].write("RESULT INVALID\n")
            current['wfile'].flush()
            continue

    # Close both sockets after game ends
    p1['conn'].close()
    p2['conn'].close()


def send_board(wfile, board):
    # Send the opponent's board view to the player (only hits and misses are visible)
    wfile.write("GRID\n")
    wfile.write("  " + " ".join(str(i + 1).rjust(2) for i in range(board.size)) + '\n')
    for r in range(board.size):
        row_label = chr(ord('A') + r)
        row_str = " ".join(board.display_grid[r][c] for c in range(board.size))
        wfile.write(f"{row_label:2} {row_str}\n")
    wfile.write('\n')
    wfile.flush()

def send_own_board(wfile, board):
    # Send the player's full board including ship positions
    wfile.write("GRID_SELF\n")
    wfile.write("  " + " ".join(str(i + 1).rjust(2) for i in range(board.size)) + '\n')
    for r in range(board.size):
        row_label = chr(ord('A') + r)
        row_str = " ".join(board.hidden_grid[r][c] for c in range(board.size))
        wfile.write(f"{row_label:2} {row_str}\n")
    wfile.write('\n')
    wfile.flush()

def setup_player_board(player):
    # Ask the player whether to place ships manually or randomly
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
