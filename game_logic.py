from battleship import Board, parse_coordinate, SHIPS
import threading

def run_two_player_game(p1, p2):
    # Initialize player boards with M/R placement
    setup_player_board(p1)
    setup_player_board(p2)

    # Send players their own initial board
    send_own_board(p1['wfile'], p1['board'])
    send_own_board(p2['wfile'], p2['board'])

    # Notify players of game start and turn order
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

        # Show opponent board (partial view)
        send_board(current['wfile'], opponent['board'])
        current['wfile'].write("Your turn! Enter coordinate to fire at (e.g. B5):\n")
        current['wfile'].flush()

        coord_str = current['rfile'].readline()
        if not coord_str:
            break

        coord_str = coord_str.strip()

        if coord_str.lower() == 'quit':
            current['wfile'].write("You forfeited the game.\n")
            opponent['wfile'].write("Opponent forfeited. You win!\n")
            current['wfile'].flush()
            opponent['wfile'].flush()
            break

        try:
            row, col = parse_coordinate(coord_str)
            result, sunk = opponent['board'].fire_at(row, col)

            if result == 'hit':
                msg = f"HIT!{' You sank the ' + sunk + '!' if sunk else ''}\n"
            elif result == 'miss':
                msg = "MISS!\n"
            elif result == 'already_shot':
                msg = "Already shot here. Try again.\n"
                current['wfile'].write(msg)
                current['wfile'].flush()
                continue

            current['wfile'].write(msg)
            opponent['wfile'].write(f"Opponent fired at {coord_str} → {result.upper()}\n")
            current['wfile'].flush()
            opponent['wfile'].flush()

            # Send updated board
            send_board(current['wfile'], opponent['board'])

            if opponent['board'].all_ships_sunk():
                current['wfile'].write("\nYou WIN!\n")
                opponent['wfile'].write("\nYou LOSE! All your ships have been sunk.\n")
                current['wfile'].flush()
                opponent['wfile'].flush()
                break

            turn = 1 - turn

        except Exception as e:
            current['wfile'].write(f"Invalid input: {e}\n")
            current['wfile'].flush()
            continue

    p1['conn'].close()
    p2['conn'].close()

def send_board(wfile, board):
    # Send the opponent board (only known hits and misses)
    wfile.write("GRID\n")
    wfile.write("  " + " ".join(str(i + 1).rjust(2) for i in range(board.size)) + '\n')
    for r in range(board.size):
        row_label = chr(ord('A') + r)
        row_str = " ".join(board.display_grid[r][c] for c in range(board.size))
        wfile.write(f"{row_label:2} {row_str}\n")
    wfile.write('\n')
    wfile.flush()

def send_own_board(wfile, board):
    # Send the player's own full board (including ship positions)
    wfile.write("GRID_SELF\n")
    wfile.write("  " + " ".join(str(i + 1).rjust(2) for i in range(board.size)) + '\n')
    for r in range(board.size):
        row_label = chr(ord('A') + r)
        row_str = " ".join(board.hidden_grid[r][c] for c in range(board.size))
        wfile.write(f"{row_label:2} {row_str}\n")
    wfile.write('\n')
    wfile.flush()

def setup_player_board(player):
    # Prompt the player to place ships manually or randomly
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
