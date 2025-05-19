from battleship import Board, parse_coordinate, SHIPS
import select
import time
import traceback
from utils import (
    encode_packet,
    decode_packet,
    send_packet_message,
    PACKET_TYPE_MESSAGE, #1
    PACKET_TYPE_COMMAND, #2
    PACKET_TYPE_RESULT,  #3
    PACKET_TYPE_CONTROL  #4
)

def broadcast_to_spectators(spectators, message):
    """
    Send a message to all currently connected spectators.
    Spectators are (conn, rfile, wfile) tuples.
    """
    for conn, rfile, wfile in spectators:
        try:
            send_packet_message(wfile, PACKET_TYPE_MESSAGE, f"[Spectator] {message}")
        except Exception:
            continue  # ignore disconnected spectators

def run_two_player_session(p1, p2, spectators, player_session):
    while True:
        p1.pop("board", None)
        p2.pop("board", None)
        broadcast_to_spectators(spectators, "A new round is starting...")
        success = run_single_game(p1, p2, spectators, player_session)
        if not success:
            print("[DEBUG] run_single_game returned False. Exiting session.")
            return None
        send_packet_message(p1['wfile'], PACKET_TYPE_MESSAGE, " Game over. Waiting for the other player to decide...")
        send_packet_message(p2['wfile'], PACKET_TYPE_MESSAGE, " Game over. Waiting for the other player to decide...")
        again1 = ask_play_again(p1)
        again2 = ask_play_again(p2)

        if again1 and again2:
            continue  # if both want to play again, continue the loop

        # Define whcih player wants to continue
        if again1 and not again2:
            send_packet_message(p1['wfile'], PACKET_TYPE_MESSAGE, " Opponent declined to continue. You will be returned to the waiting queue.")
            send_packet_message(p1['wfile'], PACKET_TYPE_MESSAGE, " Session ended.")
            return p1  # Client 1 continues to play

        elif again2 and not again1:
            send_packet_message(p2['wfile'], PACKET_TYPE_MESSAGE, " Opponent declined to continue. You will be returned to the waiting queue.")
            send_packet_message(p2['wfile'], PACKET_TYPE_MESSAGE, " Session ended.")
            return p2  # Client 2 continues to play

        else:
            # Both want to quit
            send_packet_message(p1['wfile'], PACKET_TYPE_MESSAGE, " Both players declined. Session ended.")
            send_packet_message(p2['wfile'], PACKET_TYPE_MESSAGE, " Both players declined. Session ended.")
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
        send_packet_message(p['wfile'], PACKET_TYPE_CONTROL, "PING")  # heartbeat check packet send
        return True
    except:
        send_packet_message(opponent, PACKET_TYPE_MESSAGE, " Opponent disconnected unexpectedly")
        send_packet_message(opponent, PACKET_TYPE_RESULT, "WIN")
        return False

def run_single_game(p1, p2, spectators, player_session):
    try:
        p1.pop("board", None)
        p2.pop("board", None)

        print("[DEBUG] p1:", p1)
        print("[DEBUG] p2:", p2)

        players = [p1, p2]
        turn = 0
        send_packet_message(p1['wfile'], PACKET_TYPE_MESSAGE, " Waiting for opponent to connect...")
        send_packet_message(p2['wfile'], PACKET_TYPE_MESSAGE, " Waiting for opponent to connect...")
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
                send_packet_message(wfile, PACKET_TYPE_MESSAGE, f" [Spectator #{idx+1}] New game: {player1_id} vs {player2_id}")
            except:
                continue
        send_packet_message(p1['wfile'], PACKET_TYPE_MESSAGE, " Both players have placed their ships. Game starting...")
        send_packet_message(p2['wfile'], PACKET_TYPE_MESSAGE, " Both players have placed their ships. Game starting...")
        send_packet_message(p1['wfile'], PACKET_TYPE_MESSAGE, " Game started! You are Player 1.")
        send_packet_message(p2['wfile'], PACKET_TYPE_MESSAGE, " Game started! You are Player 2.")
        send_packet_message(p1['wfile'], PACKET_TYPE_MESSAGE, " You go first.")
        send_packet_message(p2['wfile'], PACKET_TYPE_MESSAGE, " Waiting for Player 1 to make their move...")
        while True:
            # Check both players are alive before each turn
            if not check_alive(players[0], players[1]) or not check_alive(players[1], players[0]):
                return False

            current = players[turn]
            opponent = players[1 - turn]

            send_board(current['wfile'], opponent['board'])
            send_packet_message(current['wfile'], PACKET_TYPE_MESSAGE, " Your turn! Enter command (e.g. FIRE B5):")

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
                        send_packet_message(opponent['wfile'], PACKET_TYPE_MESSAGE, " Opponent disconnected. Waiting for reconnection (60s)...")
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
                                    send_packet_message(current['wfile'], PACKET_TYPE_MESSAGE, " You have reconnected successfully. Resuming game...")
                                except:
                                    print(f"[WARN] Failed to notify reconnected player {player_id}")

                                try:
                                    send_packet_message(opponent['wfile'], PACKET_TYPE_MESSAGE, " Opponent has reconnected. Game will resume.")
                                except:
                                    print("[WARN] Failed to notify opponent about reconnection.")

                                print(f"[INFO] Player {player_id} reconnected within 60s.")
                                break  

                            time.sleep(0.5)
                        else:
                            send_packet_message(opponent['wfile'], PACKET_TYPE_MESSAGE, " Opponent did not reconnect in time. Ending game.")
                            send_packet_message(opponent['wfile'], PACKET_TYPE_RESULT, "WIN")
                            return False
                        continue
                    else:
                        send_packet_message(opponent['wfile'], PACKET_TYPE_MESSAGE, " Opponent ID missing. Ending game.")
                        send_packet_message(opponent['wfile'], PACKET_TYPE_RESULT, "WIN")
                        return False
                elif status == "timeout":
                    send_packet_message(current['wfile'], PACKET_TYPE_MESSAGE, " Timeout occurred. Your turn was skipped.")
                    send_packet_message(opponent['wfile'], PACKET_TYPE_MESSAGE, " Opponent timed out. Their turn was skipped.")
                    turn = 1 - turn
                    continue
                pkt_type, checksum, payload = decode_packet(line)
                if pkt_type is None:
                    payload = line.strip()

                if payload.lower() == 'quit':
                    print(f"[INFO] Player {player_id} sent 'quit'. Treating as disconnect.")
                    raise ConnectionResetError("Player quit")  #


                if payload.upper().startswith("FIRE"):
                    broadcast_to_spectators(spectators, f"Player {turn + 1} fired at {line.split()[1]}")

                parts = payload.split()
                if len(parts) != 2 or parts[0].upper() != "FIRE":
                    send_packet_message(current['wfile'], PACKET_TYPE_MESSAGE, " Invalid command. Use 'FIRE <coordinate>' (e.g. FIRE B2).")
                    continue

                try:
                    row, col = parse_coordinate(parts[1])
                except Exception:
                    send_packet_message(current['wfile'], PACKET_TYPE_MESSAGE, " Invalid coordinate format. Use A1–J10.")
                    send_packet_message(current['wfile'], PACKET_TYPE_RESULT, "INVALID")
                    continue

                if not (0 <= row < 10 and 0 <= col < 10):
                    send_packet_message(current['wfile'], PACKET_TYPE_MESSAGE, " Coordinate out of bounds. Use A1–J10.")
                    send_packet_message(current['wfile'], PACKET_TYPE_RESULT, "INVALID")
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
                            send_packet_message(current['wfile'], PACKET_TYPE_RESULT, f" You sank a {sunk.upper()}!")
                            broadcast_to_spectators(spectators, f"They sank a {sunk.upper()}!")
                        else:
                            send_packet_message(current['wfile'], PACKET_TYPE_RESULT, " You hit!")
                        send_packet_message(current['wfile'], PACKET_TYPE_RESULT, " You won the game!")
                        send_packet_message(opponent['wfile'], PACKET_TYPE_RESULT, " You lost the game.")
                        broadcast_to_spectators(spectators, f"Player {turn + 1} won the game!")
                        return True
                    else:
                        if sunk:
                            send_packet_message(current['wfile'], PACKET_TYPE_RESULT, f" You sank a {sunk.upper()}!")
                            broadcast_to_spectators(spectators, f"They sank a {sunk.upper()}!")
                        else:
                            send_packet_message(current['wfile'], PACKET_TYPE_RESULT, " You hit!")
                elif result == 'miss':
                    send_packet_message(current['wfile'], PACKET_TYPE_RESULT, " You missed.")
                elif result == 'already_shot':
                    send_packet_message(current['wfile'], PACKET_TYPE_RESULT, " You already shot there.")

                send_board(current['wfile'], opponent['board'])
                turn = 1 - turn

            except Exception:
                send_packet_message(current['wfile'], PACKET_TYPE_MESSAGE, " Opponent disconnected unexpectedly")
                send_packet_message(current['wfile'], PACKET_TYPE_RESULT, "WIN")
                return False
    except Exception as e:
        print("[CRITICAL] run_single_game failed:", e)
        traceback.print_exc()
        return False


def send_board(wfile, board):
    # Send the opponent's board view to the player (only hits and misses are visible)
    send_packet_message(wfile, PACKET_TYPE_MESSAGE, " Opponent's board:")
    send_packet_message(wfile, PACKET_TYPE_MESSAGE, "GRID_OPPONENT")
    send_packet_message(wfile, PACKET_TYPE_MESSAGE, "  " + " ".join(str(i + 1).rjust(2) for i in range(board.size)))
    for r in range(board.size):
        row_label = chr(ord('A') + r)
        row_str = " ".join(board.display_grid[r][c] for c in range(board.size))
        send_packet_message(wfile, PACKET_TYPE_MESSAGE, f"{row_label:2} {row_str}")
    send_packet_message(wfile, PACKET_TYPE_MESSAGE, " End of board")

def send_own_board(wfile, board):
    # Send the player's full board including ship positions
    send_packet_message(wfile, PACKET_TYPE_MESSAGE, " Your board:")
    send_packet_message(wfile, PACKET_TYPE_MESSAGE, "GRID_SELF")
    send_packet_message(wfile, PACKET_TYPE_MESSAGE, "  " + " ".join(str(i + 1).rjust(2) for i in range(board.size)))
    for r in range(board.size):
        row_label = chr(ord('A') + r)
        row_str = " ".join(board.hidden_grid[r][c] for c in range(board.size))
        send_packet_message(wfile, PACKET_TYPE_MESSAGE, f"{row_label:2} {row_str}")
    send_packet_message(wfile, PACKET_TYPE_MESSAGE, " End of board")

def setup_player_board(player, opponent):
    try:
        wfile = player['wfile']
        rfile = player['rfile']

        # Check if player is alive before prompt
        if not check_alive(player, opponent):
            return False
        send_packet_message(wfile, PACKET_TYPE_MESSAGE, " Setting up your board...")
        send_packet_message(wfile, PACKET_TYPE_MESSAGE, "Place ships manually (M) or randomly (R)? [M/R]  (timeout in 15s):")

        status, choice_line = safe_readline_with_timeout(player, 15)
        if status != "ok":
            send_packet_message(opponent['wfile'], PACKET_TYPE_MESSAGE, " Opponent disconnected during setup (timeout or quit)")
            send_packet_message(opponent['wfile'], PACKET_TYPE_RESULT, "WIN")
            return False
        

        board = Board()
        pkt_type, checksum, payload = decode_packet(choice_line)
        if pkt_type is None:
            payload = choice_line.strip()

        choice = payload.strip().upper()
        if choice == 'M':
            for ship_name, ship_size in SHIPS:
                while True:
                    if not check_alive(player, opponent):
                        return False
                    send_packet_message(wfile, PACKET_TYPE_MESSAGE, f" Placing {ship_name} (size {ship_size})")
                    send_packet_message(wfile, PACKET_TYPE_MESSAGE, " Enter starting coordinate (e.g. A1):")

                    status, coord_line = safe_readline_with_timeout(player, 30)
                    if status != "ok":
                        send_packet_message(opponent['wfile'], PACKET_TYPE_MESSAGE, " Opponent disconnected during setup")
                        send_packet_message(opponent['wfile'], PACKET_TYPE_RESULT, "WIN")
                        return False

                    pkt_type, checksum, coord_payload = decode_packet(coord_line)
                    if pkt_type is None:
                        coord_payload = coord_line.strip()
                    coord_str = coord_payload.strip()
                    send_packet_message(wfile, PACKET_TYPE_MESSAGE, " Enter orientation (H for horizontal, V for vertical):")

                    status, orient_line = safe_readline_with_timeout(player, 30)
                    if status != "ok":
                        send_packet_message(opponent['wfile'], PACKET_TYPE_MESSAGE, " Opponent disconnected during setup")
                        send_packet_message(opponent['wfile'], PACKET_TYPE_RESULT, "WIN")
                        return False
                    pkt_type, checksum, orient_payload = decode_packet(orient_line)
                    if pkt_type is None:
                        orient_payload = orient_line.strip()
                    orientation_str = orient_payload.strip().upper()
                    try:
                        row, col = parse_coordinate(coord_str)
                        orientation = 0 if orientation_str == 'H' else 1 if orientation_str == 'V' else -1
                        if orientation == -1:
                            send_packet_message(wfile, PACKET_TYPE_MESSAGE, " Invalid orientation. Please enter H or V.")
                            continue

                        if board.can_place_ship(row, col, ship_size, orientation):
                            positions = board.do_place_ship(row, col, ship_size, orientation)
                            board.placed_ships.append({
                                'name': ship_name,
                                'positions': positions
                            })
                            break
                        else:
                            send_packet_message(wfile, PACKET_TYPE_MESSAGE, " Invalid position. Try again.")
                    except Exception as e:
                        send_packet_message(wfile, PACKET_TYPE_MESSAGE, " Error: Invalid input. Please try again.")
        else:
            board.place_ships_randomly(SHIPS)
            send_packet_message(wfile, PACKET_TYPE_MESSAGE, " Ships placed randomly.")

        player['board'] = board
        return True

    except Exception:
        send_packet_message(opponent['wfile'], PACKET_TYPE_MESSAGE, " Opponent disconnected unexpectedly during setup")
        send_packet_message(opponent['wfile'], PACKET_TYPE_RESULT, "WIN")
        return False

def ask_play_again(player):
    try:
        send_packet_message(player['wfile'], PACKET_TYPE_MESSAGE, " Play again? (Y/N)")
        status, line = safe_readline_with_timeout(player, 30)

        if status == "timeout":
            send_packet_message(player['wfile'], PACKET_TYPE_MESSAGE, " Timeout. Assuming No.")
            return False

        pkt_type, checksum, payload = decode_packet(line)
        if pkt_type is None:
            payload = line.strip()  # fallback for legacy

        response = payload.strip().lower()
        if response == 'y':
            return True
        elif response == 'n':
            return False
        else:
            send_packet_message(player['wfile'], PACKET_TYPE_MESSAGE, " Invalid response. Please enter Y or N.")
            return ask_play_again(player)

    except Exception as e:
        print(f"[WARN] ask_play_again failed: {e}")
        return False

