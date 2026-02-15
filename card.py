from collections import namedtuple

SUITS = ('S', 'H', 'D', 'C')
SUIT_SYMBOLS = {'S': '♠', 'H': '♥', 'D': '♦', 'C': '♣'}
RANK_NAMES = {1: 'A', 11: 'J', 12: 'Q', 13: 'K'}


class Card(namedtuple('Card', ['rank', 'suit'])):
    """A playing card with rank (1=A, 2-10, 11=J, 12=Q, 13=K) and suit (S/H/D/C)."""

    def __str__(self):
        r = RANK_NAMES.get(self.rank, str(self.rank))
        return f"{r}{SUIT_SYMBOLS[self.suit]}"

    def __repr__(self):
        return str(self)


def parse_card(text):
    """Parse a card string like '7S', 'AH', '10D', 'KC'."""
    text = text.strip().upper()
    if len(text) < 2:
        raise ValueError(f"Invalid card: {text}")

    suit = text[-1]
    rank_str = text[:-1]

    rank_map = {'A': 1, 'J': 11, 'Q': 12, 'K': 13}
    if rank_str in rank_map:
        rank = rank_map[rank_str]
    else:
        rank = int(rank_str)

    if not (1 <= rank <= 13):
        raise ValueError(f"Invalid card: {text}")
    if suit not in SUITS:
        raise ValueError(f"Invalid suit in '{text}'. Use S, H, D, or C.")

    return Card(rank, suit)


def format_group(group):
    """Format a group of cards for display, sorted sensibly."""
    if not group:
        return '[]'

    suits = set(c.suit for c in group)
    ranks = set(c.rank for c in group)

    # Ace-high run detection: same suit, has A and K but not 2
    if len(suits) == 1 and 1 in ranks and 13 in ranks and 2 not in ranks:
        sorted_group = sorted(group, key=lambda c: 14 if c.rank == 1 else c.rank)
    else:
        sorted_group = sorted(group, key=lambda c: (c.rank, c.suit))

    return '[' + ', '.join(str(c) for c in sorted_group) + ']'
