from battleship import Board, parse_coordinate, SHIPS
import threading

def run_two_player_game(p1, p2):
    #Koda: Initialize game boards for both players
    p1['board'] = Board()
    p2['board'] = Board()
    p1['board'].place_ships_randomly(SHIPS)
    p2['board'].place_ships_randomly(SHIPS)

    #Koda: Notify players of their boards
    p1['wfile'].write("Game started! You are Player 1.\n")
    p2['wfile'].write("Game started! You are Player 2.\n")
    p1['wfile'].flush()
    p2['wfile'].flush()

    players = [p1, p2]
    turn = 0  #Koda: Player 1 starts

    while True:
        current = players[turn]
        opponent = players[1 - turn]

        #Koda: Current player's turn
        current['wfile'].write("Your turn! Enter coordinate to fire at (e.g. B5):\n")
        current['wfile'].flush()

        coord_str = current['rfile'].readline()
        if not coord_str:
            break  #Koda: Player disconnected

        coord_str = coord_str.strip()

        #Koda: Sepcial command to quit
        if coord_str.lower() == 'quit':
            current['wfile'].write("You forfeited the game.\n")
            opponent['wfile'].write("Opponent forfeited. You win!\n")
            current['wfile'].flush()
            opponent['wfile'].flush()
            break

        #Koda: Coordinate validation and hit/miss logic
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
                continue  #Koda: Don't switch turns if already shot

            current['wfile'].write(msg)
            opponent['wfile'].write(f"Opponent fired at {coord_str} → {result.upper()}\n")
            current['wfile'].flush()
            opponent['wfile'].flush()

            if opponent['board'].all_ships_sunk():
                current['wfile'].write("\nYou WIN!\n")
                opponent['wfile'].write("\nYou LOSE! All your ships have been sunk.\n")
                current['wfile'].flush()
                opponent['wfile'].flush()
                break

            turn = 1 - turn  #Koda: Switch turns

        except Exception as e:
            current['wfile'].write(f"Invalid input: {e}\n")
            current['wfile'].flush()
            continue

    #Koda: Close connections
    p1['conn'].close()
    p2['conn'].close()
