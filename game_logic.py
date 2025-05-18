from battleship import Board, parse_coordinate, SHIPS
import select
import time

import traceback

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

def run_two_player_session(p1, p2, spectators, player_session):
    while True:
        broadcast_to_spectators(spectators, "A new round is starting...")
        success = run_single_game(p1, p2, spectators, player_session)
        if not success:
            break

        p1['wfile'].write("MESSAGE Waiting for the other player to decide...\n")
        p2['wfile'].write("MESSAGE Waiting for the other player to decide...\n")
        p1['wfile'].flush()
        p2['wfile'].flush()

        again1 = ask_play_again(p1)
        again2 = ask_play_again(p2)

        if again1 and again2:
            continue  # if both want to play again, continue the loop

        # Define whcih player wants to continue
        if again1 and not again2:
            p1['wfile'].write("MESSAGE Opponent declined to continue. You will be returned to the waiting queue.\n")
            p1['wfile'].write("MESSAGE Session ended.\n")
            p1['wfile'].flush()
            return p1  # Client 1 continues to play

        elif again2 and not again1:
            p2['wfile'].write("MESSAGE Opponent declined to continue. You will be returned to the waiting queue.\n")
            p2['wfile'].write("MESSAGE Session ended.\n")
            p2['wfile'].flush()
            return p2  # Client 2 continues to play

        else:
            # Both want to quit
            p1['wfile'].write("MESSAGE Both players declined. Session ended.\n")
            p1['wfile'].flush()
            p2['wfile'].write("MESSAGE Both players declined. Session ended.\n")
            p2['wfile'].flush()
            return None


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



def safe_readline_with_timeout(player, timeout_seconds):
    print(f"[DEBUG] reading from conn = {player['conn'].fileno()}")

    try:
        ready, _, _ = select.select([player['conn']], [], [], timeout_seconds)
        if ready:
            line = player['rfile'].readline()
            if line == '':
                return "closed", None
            return "ok", line
        return "timeout", None
    except Exception as e:
        print(f"[DEBUG] select/readline error: {e}")
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

def run_single_game(p1, p2, spectators, player_session):
    try:
        print("[DEBUG] p1:", p1)
        print("[DEBUG] p2:", p2)

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

        player1_id = p1['player_id']
        player2_id = p2['player_id']
        for idx, (conn, rfile, wfile) in enumerate(spectators):
            try:
                wfile.write(f"MESSAGE [Spectator #{idx+1}] New game: {player1_id} vs {player2_id}\n")
                wfile.flush()
            except:
                continue

        p1['wfile'].write("MESSAGE Both players have placed their ships. Game starting...\n")
        p2['wfile'].write("MESSAGE Both players have placed their ships. Game starting...\n")
        p1['wfile'].write("Game started! You are Player 1.\n")
        p2['wfile'].write("Game started! You are Player 2.\n")
        p1['wfile'].write("You go first.\n")
        p2['wfile'].write("Waiting for Player 1 to make their move...\n")
        p1['wfile'].flush()
        p2['wfile'].flush()

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
                status, line = safe_readline_with_timeout(current, 15)
                print(f"[DEBUG] readline status = {status}")

                if status == "closed":
                    print("[DEBUG] Entered status == closed")
                    player_id = current.get("player_id")
                    print(f"[DEBUG] player_id = {player_id}")
                    print("[DEBUG] player_session keys:", list(player_session.keys()))
                    print(f"[DEBUG] looking for player_id: {player_id}")

                    if player_id in player_session:
                        opponent["wfile"].write("MESSAGE Opponent disconnected. Waiting for reconnection (60s)...\n")
                        opponent["wfile"].flush()

                        player_session[player_id]["status"] = "disconnected"
                        player_session[player_id]["last_seen"] = time.time()

                        for i in range(60):
                            session = player_session.get(player_id)
                            if not check_alive(opponent, current):
                                print("[INFO] Opponent also disconnected. Ending game.")
                                return False
                            if session and session.get("status") == "reconnected":
                                print(f"[INFO] Player {player_id} reconnected.")

                                current["conn"] = session["conn"]
                                current["rfile"] = session["rfile"]
                                current["wfile"] = session["wfile"]
                                current["player_id"] = player_id

                                player_session[player_id]["conn"] = session["conn"]
                                player_session[player_id]["rfile"] = session["rfile"]
                                player_session[player_id]["wfile"] = session["wfile"]
                                player_session[player_id]["status"] = "connected"

                                try:
                                    current['wfile'].write("MESSAGE You have reconnected successfully. Resuming game...\n")
                                    current['wfile'].flush()
                                except:
                                    print(f"[WARN] Failed to notify reconnected player {player_id}")

                                try:
                                    opponent['wfile'].write("MESSAGE Opponent has reconnected. Game will resume.\n")
                                    opponent['wfile'].flush()
                                except:
                                    print("[WARN] Failed to notify opponent about reconnection.")

                                print(f"[INFO] Player {player_id} reconnected within 60s.")
                                break  

                            time.sleep(0.5)
                        else:
                            
                            opponent["wfile"].write("MESSAGE Opponent did not reconnect in time.\n")
                            opponent["wfile"].write("RESULT WIN\n")
                            opponent["wfile"].flush()
                            return False
                        continue
                    else:
                        opponent["wfile"].write("MESSAGE Opponent ID missing. Ending game.\n")
                        opponent["wfile"].write("RESULT WIN\n")
                        opponent["wfile"].flush()
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
                    print(f"[INFO] Player {player_id} sent 'quit'. Treating as disconnect.")
                    raise ConnectionResetError("Player quit")  #


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
    except Exception as e:
        print("[CRITICAL] run_single_game failed:", e)
        traceback.print_exc()
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

        status, choice_line = safe_readline_with_timeout(player, 15)
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

                    status, coord_line = safe_readline_with_timeout(player, 30)
                    if status != "ok":
                        opponent['wfile'].write("MESSAGE Opponent disconnected during setup\n")
                        opponent['wfile'].write("RESULT WIN\n")
                        opponent['wfile'].flush()
                        return False

                    coord_str = coord_line.strip()
                    wfile.write("Orientation? Enter 'H' or 'V':\n")
                    wfile.flush()

                    status, orient_line = safe_readline_with_timeout(player, 30)
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

        status, response = safe_readline_with_timeout(player, 15)
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

