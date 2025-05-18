from battleship import Board, parse_coordinate, SHIPS
import select

def broadcast_to_spectators(spectators, message):
    """
    Send a message to all currently connected spectators.
    Spectators are (conn, rfile, wfile) tuples.
    """
    for conn, rfile, wfile in spectators:
        try:
            wfile.write(f"MESSAGE [Spectator] {message}\n")
            wfile.flush()
        except Exception:
            continue  # ignore disconnected spectators

def run_two_player_session(p1, p2, spectators):
    while True:
        broadcast_to_spectators(spectators, "A new round is starting...")
        success = run_single_game(p1, p2, spectators)
        if not success:
            break

        p1['wfile'].write("MESSAGE Waiting for the other player to decide...\n")
        p2['wfile'].write("MESSAGE Waiting for the other player to decide...\n")
        p1['wfile'].flush()
        p2['wfile'].flush()

        again1 = ask_play_again(p1)
        if not again1:
            p2['wfile'].write("MESSAGE Opponent declined to continue. Game session ended.\n")
            p2['wfile'].write("MESSAGE Session ended.\n")
            p2['wfile'].flush()
            break

        again2 = ask_play_again(p2)
        if not again2:
            p1['wfile'].write("MESSAGE Opponent declined to continue. Game session ended.\n")
            p1['wfile'].write("MESSAGE Session ended.\n")
            p1['wfile'].flush()
            break

    p1['conn'].close()
    p2['conn'].close()

    # Determine if the players are still connected
    try:
        p1['wfile'].write("PING\n")
        p1['wfile'].flush()
        return p1
    except:
        pass
    try:
        p2['wfile'].write("PING\n")
        p2['wfile'].flush()
        return p2
    except:
        pass
    return None



def safe_readline_with_timeout(rfile, timeout_seconds):
    try:
        ready, _, _ = select.select([rfile], [], [], timeout_seconds)
        if ready:
            line = rfile.readline()
            if line == '':
                return "closed", None  # socket closed
            return "ok", line
        return "timeout", None
    except Exception:
        return "closed", None

def check_alive(p, opponent):
    try:
        p['wfile'].write("PING\n")
        p['wfile'].flush()
        return True
    except:
        opponent['wfile'].write("MESSAGE Opponent disconnected unexpectedly\n")
        opponent['wfile'].write("RESULT WIN\n")
        opponent['wfile'].flush()
        return False

def run_single_game(p1, p2, spectators):
    players = [p1, p2]
    turn = 0

    p1['wfile'].write("MESSAGE Both players connected! Now set up your ships.\n")
    p2['wfile'].write("MESSAGE Both players connected! Now waiting p1 place ships.\n")
    p1['wfile'].flush()
    p2['wfile'].flush()

    if not setup_player_board(p1, p2):
        p1['conn'].close()
        p2['conn'].close()
        return False

    if not setup_player_board(p2, p1):
        p1['conn'].close()
        p2['conn'].close()
        return False

    send_own_board(p1['wfile'], p1['board'])
    send_own_board(p2['wfile'], p2['board'])

    broadcast_to_spectators(spectators, "A new game has started between two players.")
    p1['wfile'].write("MESSAGE Both players have placed their ships. Game starting...\n")
    p2['wfile'].write("MESSAGE Both players have placed their ships. Game starting...\n")
    p1['wfile'].write("Game started! You are Player 1.\n")
    p2['wfile'].write("Game started! You are Player 2.\n")
    p1['wfile'].write("You go first.\n")
    p2['wfile'].write("Waiting for Player 1 to make their move...\n")
    p1['wfile'].flush()
    p2['wfile'].flush()

    def check_alive(p, opponent):
        try:
            p['wfile'].write("PING\n")
            p['wfile'].flush()
            return True
        except:
            opponent['wfile'].write("MESSAGE Opponent disconnected unexpectedly\n")
            opponent['wfile'].write("RESULT WIN\n")
            opponent['wfile'].flush()
            return False

    while True:
        # Check both players are alive before each turn
        if not check_alive(players[0], players[1]) or not check_alive(players[1], players[0]):
            return False

        current = players[turn]
        opponent = players[1 - turn]

        send_board(current['wfile'], opponent['board'])
        current['wfile'].write("Your turn! Enter command (e.g. FIRE B5):\n")
        current['wfile'].flush()

        try:
            status, line = safe_readline_with_timeout(current['rfile'], 30)

            if status == "closed":
                opponent['wfile'].write("MESSAGE Opponent disconnected unexpectedly\n")
                opponent['wfile'].write("RESULT WIN\n")
                opponent['wfile'].flush()
                return False

            elif status == "timeout":
                current['wfile'].write("MESSAGE Timeout occurred. Your turn was skipped.\n")
                current['wfile'].flush()
                opponent['wfile'].write("MESSAGE Opponent timed out. Their turn was skipped.\n")
                opponent['wfile'].flush()
                turn = 1 - turn
                continue

            line = line.strip()

            if line.lower() == 'quit':
                current['wfile'].write("RESULT FORFEIT\n")
                opponent['wfile'].write("MESSAGE Opponent quit\n")
                opponent['wfile'].write("RESULT WIN\n")
                current['wfile'].flush()
                opponent['wfile'].flush()
                return False

            if line.upper().startswith("FIRE"):
                broadcast_to_spectators(spectators, f"Player {turn + 1} fired at {line.split()[1]}")

            parts = line.split()
            if len(parts) != 2 or parts[0].upper() != "FIRE":
                current['wfile'].write("RESULT INVALID INPUT (e.g. FIRE B2)\n")
                current['wfile'].flush()
                continue

            try:
                row, col = parse_coordinate(parts[1])
            except Exception:
                current['wfile'].write("RESULT INVALID\n")
                current['wfile'].write("MESSAGE Invalid coordinate format. Use A1–J10.\n")
                current['wfile'].flush()
                continue

            if not (0 <= row < 10 and 0 <= col < 10):
                current['wfile'].write("RESULT INVALID\n")
                current['wfile'].write("MESSAGE Coordinate out of bounds. Use A1–J10.\n")
                current['wfile'].flush()
                continue

            result, sunk = opponent['board'].fire_at(row, col)

            if result == 'hit':
                broadcast_to_spectators(spectators, "It was a HIT!")
            elif result == 'miss':
                broadcast_to_spectators(spectators, "It was a MISS!")
            elif result == 'already_shot':
                broadcast_to_spectators(spectators, "They fired at an already hit position.")


            if result == 'hit':
                if opponent['board'].all_ships_sunk():
                    if sunk:
                        current['wfile'].write(f"RESULT HIT {sunk.upper()}\n")
                        broadcast_to_spectators(spectators, f"They sank a {sunk.upper()}!")
                    else:
                        current['wfile'].write("RESULT HIT\n")
                    current['wfile'].write("RESULT WIN\n")
                    opponent['wfile'].write("RESULT LOSE\n")
                    broadcast_to_spectators(spectators, f"Player {turn + 1} won the game!")
                    current['wfile'].flush()
                    opponent['wfile'].flush()
                    return True
                else:
                    if sunk:
                        current['wfile'].write(f"RESULT HIT {sunk.upper()}\n")
                        broadcast_to_spectators(spectators, f"They sank a {sunk.upper()}!")
                    else:
                        current['wfile'].write("RESULT HIT\n")
            elif result == 'miss':
                current['wfile'].write("RESULT MISS\n")
            elif result == 'already_shot':
                current['wfile'].write("RESULT ALREADY\n")
            current['wfile'].flush()

            send_board(current['wfile'], opponent['board'])
            turn = 1 - turn

        except Exception:
            opponent['wfile'].write("MESSAGE Opponent disconnected unexpectedly\n")
            opponent['wfile'].write("RESULT WIN\n")
            opponent['wfile'].flush()
            return False


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

def setup_player_board(player, opponent):
    try:
        wfile = player['wfile']
        rfile = player['rfile']

        # Check if player is alive before prompt
        if not check_alive(player, opponent):
            return False

        wfile.write("Place ships manually (M) or randomly (R)? [M/R]  (timeout in 15s):\n")
        wfile.flush()

        status, choice_line = safe_readline_with_timeout(rfile, 15)
        if status != "ok":
            opponent['wfile'].write("MESSAGE Opponent disconnected during setup (timeout or quit)\n")
            opponent['wfile'].write("RESULT WIN\n")
            opponent['wfile'].flush()
            return False

        board = Board()
        choice = choice_line.strip().upper()
        if choice == 'M':
            for ship_name, ship_size in SHIPS:
                while True:
                    if not check_alive(player, opponent):
                        return False
                    wfile.write(f"Placing {ship_name} (size {ship_size})\n")
                    wfile.write("Enter starting coordinate (e.g. A1):\n")
                    wfile.flush()

                    status, coord_line = safe_readline_with_timeout(rfile, 30)
                    if status != "ok":
                        opponent['wfile'].write("MESSAGE Opponent disconnected during setup\n")
                        opponent['wfile'].write("RESULT WIN\n")
                        opponent['wfile'].flush()
                        return False

                    coord_str = coord_line.strip()
                    wfile.write("Orientation? Enter 'H' or 'V':\n")
                    wfile.flush()

                    status, orient_line = safe_readline_with_timeout(rfile, 30)
                    if status != "ok":
                        opponent['wfile'].write("MESSAGE Opponent disconnected during setup\n")
                        opponent['wfile'].write("RESULT WIN\n")
                        opponent['wfile'].flush()
                        return False

                    orientation_str = orient_line.strip().upper()
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
        return True

    except Exception:
        opponent['wfile'].write("MESSAGE Opponent disconnected during setup\n")
        opponent['wfile'].write("RESULT WIN\n")
        opponent['wfile'].flush()
        return False

def ask_play_again(player):
    wfile = player['wfile']
    rfile = player['rfile']

    for _ in range(3):
        wfile.write("MESSAGE Play again? (Y/N)\n")
        wfile.flush()

        status, response = safe_readline_with_timeout(rfile, 15)
        if status != "ok":
            return False

        response = response.strip().upper()
        if response == 'Y':
            return True
        elif response == 'N':
            return False
        else:
            wfile.write("MESSAGE Invalid response. Please enter Y or N.\n")
            wfile.flush()

    return False
