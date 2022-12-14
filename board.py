# -*- coding: utf-8 -*-
"""
Created on Thu Nov 24 20:10:32 2022

@author: anton
"""

from typing import List, Tuple, Union
import json

import matplotlib.pyplot as plt
import numpy as np

import pieces
from pieces import Team, Queen, Pawn, King, Bishop, Rook, Knight
from misc import chess_to_coord, get_json_file, coord_to_chess, to_both_coord, to_coord, ls2chess

RAN8 = range(8)


class Board:
    """Defines the board of the chess game.

    """
    def __init__(self, board=None) -> None:
        # TODO Change the argument board to pieces.
        self.board = np.zeros((8, 8), dtype=pieces.Piece)
        if board is not None:
            self.board[:] = board
        self._pieces = dict()

        self.kings = {pieces.Team('w'): None, pieces.Team('b'): None}
        self.en_passant = None, None # Saves the last pawn move. If the pawn moves two fields it stores only the next field. 

    def __getitem__(self, pos) -> pieces.Piece:
        col, row = chess_to_coord(*pos)
        return self.board[col, row]

    def __setitem__(self, pos, val) -> pieces.Piece:
        """Saves the value (piece) with the given position."""
        col, row = chess_to_coord(*pos)
        if self.board[col, row] != 0 or self._pieces.get((col, row)):
            raise ValueError(
                f"On {pos=} is already '{repr(self.board[col, row])}'. If you want to replace a piece use the move method instead.")
        self.board[col, row] = val
        self._pieces[col, row] = val

    def __repr__(self) -> str:
        return f"Board({repr(self.board)})"

    def __str__(self) -> str:
        # TODO. This is not hübsch.
        board = np.zeros_like(self.board, dtype=object)
        for i in RAN8:
            for j in RAN8:
                if self.board[i, j] != 0:
                    board[i, j] = str(self.board[i, j])
                else:
                    board[i, j] = ""
        return str(board)

    def get_pieces(self) -> List[pieces.Piece]:
        """Returns an iterable of the present pieces on the table."""
        return self._pieces

    def get_board(self) -> str:
        return self.board

    def remove(self, pos):
        self._pieces.pop(pos)
        self.board[pos] = 0

    def destroy(self, piece):
        self.remove(piece.position)
        piece.destroy()
    
    def move(self, piece: pieces.Piece, new_position: pieces.Position):
        """Moves the piece to the new position. It is not checked whether the new_position is a legal move.
        If on the new position is another piece it is removed from the list of pieces.

        The position should be given in chess coordinates. That is, e.g. ('h', 8) instead of (7,7).
        """
        npos = to_coord(*new_position)
        
        if isinstance(piece, Pawn):
            if npos == self.en_passant[0]:
                self.destroy(self.en_passant[1])
            
            # Save the possible en_passant move and the piece which made it.
            ms = piece.move_set[piece.position]
            self.en_passant = next(iter(ms), None) 
            self.en_passant = self.en_passant, piece
        else: 
            self.en_passant = None, None
            if self._pieces.get(npos) is not None:
                self.destroy(self._pieces[npos])
        self.remove(piece.position)
        piece.set_position(npos)
        self[new_position] = piece

    def plot_chessboard(self, highlighted=None):
        """Plots the chessboard with the current pieces.
        If highlighted is given then these fields are also depicted with the highlighted color.

        Args:
            highlighted (_type_, optional): A list of highlighted fields. Defaults to None.
        """
        # Declare color values
        cdict = get_json_file()
        cBlack = cdict['colors']['black_field']
        cWhite = cdict['colors']['white_field']
        cHighlightWhite = cdict['colors']['white_highlighted']
        cHighlightBlack = cdict['colors']['black_highlighted']
        cBPiece = np.array(cdict['colors']['black_pieces'])/255
        cWPiece = np.array(cdict['colors']['white_pieces'])/255

        fig, ax = plt.subplots(1, 1)
        res = np.add.outer(range(8), range(8)) % 2

        if highlighted is not None:
            for h in highlighted:
                hy, hx = h
                hx = 7 - hx
                if res[hx, hy] == 0:
                    res[hx, hy] = 2
                else:
                    res[hx, hy] = 3

        img = np.zeros((8, 8, 3))
        img[res == 0] = cWhite
        img[res == 1] = cBlack
        img[res == 2] = cHighlightWhite
        img[res == 3] = cHighlightBlack
        img /= 255
        ax.imshow(img)

        ax.set_xticks([i-1 for i in range(1, 9)])
        ax.set_yticks([i-2 for i in range(9, 1, -1)])

        ax.set_xticklabels(list("abcdefgh"))
        ax.set_yticklabels([i for i in range(1, 9)])

        for k in self._pieces:
            piece = self._pieces[k]
            x, y = piece.position
            y = 7 - y
            x -= 0.45
            y += 0.33
            ax.text(x, y, piece.icon_text, color=cBPiece if piece.team == 'b' else cWPiece,
                    fontsize=26)

        fig.suptitle("Chess Board")
        # plt.show()

    def get_danger_zone(self, team):
        """Returns the danger zone of the selected teamm, that is, all positions, that the selected team can attack.
        Returns a set of positions.
        Mainly here to get the dangerous positions for the king.

        Args:
            team (pieces.Teeam): The team to select the danger zone from.

        Returns:
            Set[Positions]: A set of positions the given team can attack on.
        """
        danger = set()
        for pos in self._pieces:
            piece = self._pieces[pos]
            if piece.team == team:
                dngzone = piece.danger_zone(self._pieces)
                danger.update(dngzone)
        return danger

    def is_check(self, team, danger_zone=None):
        """Returns True if the king of the given team is in check. 
        You can pass the danger zone if you have calculated it earlier. 
        Note that the danger zone should be of the other team.

        Args:
            team (pieces.Team): Team of the king which shall be checked 
            danger_zone (Set[Position], optional): A set of positions of the enemy team. Defaults to None.

        Returns:
            bool: Condition if king has been checked.
        """
        if danger_zone is None:
            danger_zone = self.get_danger_zone(~team)
        return self.kings[team].position in danger_zone

    def get_attackers(self, team):
        """Returns the number of pieces threatening the king of the given team.

        Args:
            team (pieces.Team): Team of the king which shall be checked 

        Returns:
            List[Tuple[Piece, Set[Position]]]: 
                A list containing tuples with pieces and the corresponding move set of this piece.
            The pieces which check the king. The king is checked if the list is not empty.
        """
        kingpos = self.kings[team].position
        rook = pieces.Rook(team, kingpos)
        bishop = pieces.Bishop(team, kingpos)
        knight = pieces.Knight(team, kingpos)
        pawn = pieces.Pawn(team, kingpos)

        rdng = rook.danger_zone(self._pieces)
        bdng = bishop.danger_zone(self._pieces)
        kdng = knight.danger_zone(self._pieces)
        pdng = pawn.danger_zone(self._pieces)

        attackers = []
        for pos in self._pieces:
            piece = self._pieces[pos]
            if piece.team == team or isinstance(piece, King):
                continue
            # Checks if a fitting piece is on a dangerous position.
            elif isinstance(piece, (Bishop, Queen)) and pos in bdng:
                attackers.append((piece, bdng & Bishop(
                    ~team, pos).get_moves(self._pieces)))
            elif isinstance(piece, (Rook, Queen)) and pos in rdng:
                attackers.append(
                    (piece, rdng & Rook(~team, pos).get_moves(self._pieces)))
            elif isinstance(piece, Knight) and pos in kdng:
                attackers.append((piece, {pos}))
            elif isinstance(piece, Pawn) and pos in pdng:
                attackers.append((piece, {pos}))

            if len(attackers) >= 2:
                # In a normal chess game it is not possible that more than 2 pieces simultaneously check the king
                return attackers
        return attackers

    def legal_moves(self, team):
        """Calculates the legal moves of the given team.

        Args:
            team (Dict[Position, Set[Position]]): A dictionary which maps the position to the legal move sets.
        """
        team = Team(team)
        king = self.kings[team]

        # First, calculate all possible moves the current team can make.
        pmoves = dict()  # All moves from the team.
        dzone = set()  # Danger zone of the enemy pieces for the king.
        for pos in self._pieces:
            piece = self._pieces[pos]
            if piece.team != team:
                dzone.update(piece.danger_zone(self._pieces))
            else:
                pmoves[pos] = piece.get_moves(self._pieces, en_passant = self.en_passant[0])

        # Tackle the pinning.
        pins = king.check_pins(self._pieces)
        for piece, rs in pins: 
            pmoves[piece.position] &= rs

        # Tackle Checks
        attackers = self.get_attackers(team)
        if len(attackers) > 0:
            # Check!
            capture_moves = set()  # Saves the positions which t
            # Saves the positions on which the given team can move.
            block_moves = set()

            if len(attackers) == 1:
                # You can only capture the attacker if there is only one.
                # This is also the only situation where you can block the attacker.
                capture_moves.add(attackers[0][0].position)
                block_moves.update(attackers[0][1])
                
            block_moves |= capture_moves
            for pos in pmoves:
                # The moves of the king are handled later.
                if pos != king.position:
                    pmoves[pos] &= block_moves
                    if self.en_passant[0] is not None and isinstance(self._pieces[pos], Pawn):
                        pmoves[pos].add(self.en_passant[0])
                    # pmoves[pos] |= capture_moves

        # Give the king special treatment.
        pmoves[king.position] -= dzone

        return pmoves

    def put_piece(self, posx: Union[str, int], posy: int, piece, team: Union[str, pieces.Team]):
        """Initializes the board with the given piece.

        Args:
            cposx (Union[char, int]): The x-coordinate of the position. Can be either a char or an integer. 
                If the position is a char it is assumed a chess coordinate is given (e.g. 'c', 4). 
                Otherwise it is assumed that is a normal coordinate.
            cposy (int): The other part of the coordinate.
            piece (constructor): The constructor of the piece.
            team (Union[char, pieces.Team]): The team this piece belongs to.
        """
        (cx, cy), (px, py) = to_both_coord(posx, posy)
        self[cx, cy] = piece(team, (px, py))

    def place_king(self, posx: Union[str, int], posy: int, team: Union[str, pieces.Team]):
        """Places the king to the given position. This method should be prefered to the normal put piece method as 
        it also save the position of the king in the class."""
        (cx, cy), (px, py) = to_both_coord(posx, posy)
        self[cx, cy] = self.kings[Team(team)] = King(team, (px, py))

    def init_board(self):
        """Initializes the chess board by placing all the pieces on the board.
        """
        # initialize pawns
        for c in "abcdefgh":
            self.put_piece(c, 2, Pawn, 'w')
            self.put_piece(c, 7, Pawn, 'b')

        # initialize the other pieces
        for i, c in ((1, 'w'), (8, 'b')):
            self.put_piece('a', i, Rook, c)
            self.put_piece('b', i, Knight, c)
            self.put_piece('c', i, Bishop, c)
            self.put_piece('d', i, Queen, c)
            self.put_piece('f', i, Bishop, c)
            self.put_piece('g', i, Knight, c)
            self.put_piece('h', i, Rook, c)
            self.place_king('e', i, c)

        # For testing purposes
        self.put_piece('c', 4, pieces.Queen, 'b')
        self.put_piece('e', 3, Pawn, 'b')
        self.put_piece('g', 3, Pawn, 'w')
        self.put_piece('f', 6, Pawn, 'w')
        self.put_piece('g', 5, Pawn, 'w')
        return self._pieces

    def board1(self):
        # Example for a check
        self.place_king('b', 6, 'b')
        self.place_king('e', 3, 'w')
        self.put_piece('e', 5, pieces.Queen, 'b')
        self.put_piece('c', 3, pieces.Bishop, 'w')
        self.put_piece('a', 4, Rook, 'w')
        
        self.put_piece('g', 5, Queen, 'w')
        self.put_piece('h', 6, Bishop, 'b')

        return self._pieces
    
    def board12(self):
        # Example for a check
        self.place_king('b', 6, 'b')
        self.place_king('e', 3, 'w')
        # self.put_piece('e', 8, pieces.Queen, 'b')
        self.put_piece('c', 3, pieces.Bishop, 'w')
        self.put_piece('a', 4, Rook, 'w')
        
        self.put_piece('g', 5, Queen, 'w')
        self.put_piece('h', 6, Bishop, 'b')
        self.put_piece('c', 5, Bishop, 'b')
        
        self.put_piece('f', 7, Pawn, 'w')
        self.put_piece('b', 4, Pawn, 'w')

        return self._pieces

    def board2(self):
        # Example for a pinned piece
        self.place_king('b', 6, 'b')
        self.place_king('h', 2, 'w')
        
        self.put_piece('c', 7, Bishop, 'b')
        self.put_piece('e', 5, Bishop, 'w')

        self.put_piece('h', 7, Rook, 'w')
        self.put_piece('h', 8, Rook, 'b')
        
        self.put_piece('b', 2, Queen, 'b')
        self.put_piece('d', 2, Queen, 'w')

        return self._pieces
    
    def board3(self):
        # Example for en passant
        self.place_king('a', 8, 'b')
        self.place_king('a', 1, 'w')
        
        # self.put_piece('c', 7, Bishop, 'b')
        # self.put_piece('e', 5, Bishop, 'w')
        
        self.put_piece('d', 7, Pawn, 'b')
        self.put_piece('e', 5, Pawn, 'w')
        self.put_piece('h', 7, Pawn, 'b')
        self.put_piece('g', 5, Pawn, 'w')

        return self._pieces
    
    def board4(self):
        # Example for en passant
        self.place_king('c', 5, 'b')
        self.place_king('a', 1, 'w')
        
        # self.put_piece('c', 7, Bishop, 'b')
        # self.put_piece('e', 5, Bishop, 'w')
        
        self.put_piece('e', 4, Pawn, 'b')
        self.put_piece('d', 2, Pawn, 'w')
        b.move(b['d', 2], ('d', 4))

        return self._pieces
    
    def board5(self):
        # Example for en passant
        self.place_king('b', 5, 'b')
        self.place_king('a', 1, 'w')
        
        # self.put_piece('c', 7, Bishop, 'b')
        # self.put_piece('e', 5, Bishop, 'w')
        
        self.put_piece('e', 4, Pawn, 'b')
        self.put_piece('d', 2, Pawn, 'w')
        self.put_piece('f', 1, Queen, 'w')
        
        # Enable the en passant
        b.move(b['d', 2], ('d', 4))

        return self._pieces

# plt.close('all')

b = Board()
# bpieces = b.init_board()
bpieces = b.board4()

# b.plot_chessboard(b.get_danger_zone(Team('b')))
# b.move(b['d', 2], ('d', 4))
moves = b.legal_moves('b')
dz = set()
for pos in moves:
    dz.update(moves[pos])
b.plot_chessboard(dz)
# b.move(b['d', 7], ('d', 5))
# b.plot_chessboard()
# b.move(b['e', 5], ('d', 6))
# b.plot_chessboard()

# b.plot_chessboard(moves[to_coord('g', 5)])
# dz = set()
# for pos in moves:
#     dz.update(moves[pos])
# b.plot_chessboard(dz)

# b.plot_chessboard(moves[to_coord('e', 3)])
# b.plot_chessboard(b['b', 7].get_moves(bpieces))
# r.get_legal_moves(b.get_pieces())
# r = b.list_of_pieces_on_board[0]
# pawn1 = pieces[1]
# pawn1.get_legal_moves(pieces)
# q1 = pieces[2]
# print(repr(q1.get_legal_moves(pieces)))

# [[coord_to_chess(*l) for l in l_] for l_ in q1.get_legal_moves(pieces)[0]]
# q1 = b['c', 4]
# # _, enmy = q1.get_legal_moves(b.get_pieces())
# dng = b.get_danger_zone(pieces.Team('b'))
# b.plot_chessboard(highlighted=dng)
# # print(ls2chess(q1.danger_zone(b.get_pieces())))
# bkn = b['b', 8]
# moves = bkn.get_legal_moves(b.get_pieces())
# p1 = b['b',7]
# dngp1 = p1.danger_zone(b.get_pieces())
# king = b['e', 1]
