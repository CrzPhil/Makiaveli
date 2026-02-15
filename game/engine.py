"""Makiaveli game engine — state management and rules."""

import random
from dataclasses import dataclass, field
from collections import Counter

from card import Card, SUITS, card_to_dict
from solver import is_valid_group


@dataclass
class GameState:
    deck: list[Card]
    hands: dict[str, list[Card]]       # "human" / "bot"
    floor_groups: list[list[Card]]
    cross: list[Card | None]           # 4 slots, None = incorporated
    current_player: str
    game_over: bool = False
    winner: str | None = None


def _make_deck() -> list[Card]:
    """Create and shuffle a 2-deck (104 card) deck."""
    cards = [Card(rank, suit) for _ in range(2)
             for suit in SUITS for rank in range(1, 14)]
    random.shuffle(cards)
    return cards


def new_game() -> GameState:
    """Start a new game: shuffle, deal 5 each, lay 4 cross cards."""
    deck = _make_deck()
    human_hand = [deck.pop() for _ in range(5)]
    bot_hand = [deck.pop() for _ in range(5)]
    cross = [deck.pop() for _ in range(4)]
    return GameState(
        deck=deck,
        hands={"human": human_hand, "bot": bot_hand},
        floor_groups=[],
        cross=cross,
        current_player="human",
    )


def draw_card(gs: GameState, player: str) -> Card | None:
    """Draw a card from the deck. Returns the drawn card or None if empty."""
    if not gs.deck:
        return None
    card = gs.deck.pop()
    gs.hands[player].append(card)
    gs.current_player = "bot" if player == "human" else "human"
    return card


def _card_counter(cards: list[Card]) -> Counter:
    """Build a Counter from a card list keyed by (rank, suit)."""
    c = Counter()
    for card in cards:
        c[(card.rank, card.suit)] += 1
    return c


def validate_play(
    gs: GameState,
    player: str,
    new_floor: list[list[Card]],
    cards_played: list[Card],
) -> tuple[bool, str]:
    """
    Validate a proposed play.

    Checks:
    - At least 1 card played from hand
    - All cards_played are in the player's hand
    - Card conservation: old floor + active cross + cards_played == new floor
    - All new floor groups are valid (3+ cards, valid set or run)
    """
    if not cards_played:
        return False, "Must play at least 1 card"

    # Check cards_played are in hand
    hand_counter = _card_counter(gs.hands[player])
    played_counter = _card_counter(cards_played)
    for key, count in played_counter.items():
        if hand_counter.get(key, 0) < count:
            rank, suit = key
            return False, f"Card {Card(rank, suit)} not in hand (or not enough copies)"

    # Card conservation: old floor + incorporated cross + cards_played == new floor
    # Cross cards that remain unincorporated (untouched singles) stay as cross,
    # so we only count cross cards that actually appear in the new floor.
    old_floor_cards = Counter()
    for group in gs.floor_groups:
        for card in group:
            old_floor_cards[(card.rank, card.suit)] += 1

    new_cards = Counter()
    for group in new_floor:
        for card in group:
            new_cards[(card.rank, card.suit)] += 1

    # What the new floor needs beyond old floor + cards_played must come from cross
    from_cross = Counter(new_cards)
    from_cross.subtract(old_floor_cards)
    from_cross.subtract(played_counter)

    # Verify no negative counts (can't create cards out of thin air)
    for key, count in from_cross.items():
        if count < 0:
            rank, suit = key
            return False, f"Card conservation violated: extra {Card(rank, suit)} unaccounted for"

    # Verify what's needed from cross is actually available in active cross
    cross_available = _card_counter([c for c in gs.cross if c is not None])
    for key, count in from_cross.items():
        if count > 0 and cross_available.get(key, 0) < count:
            rank, suit = key
            return False, f"Card conservation violated: {Card(rank, suit)} not available from cross"

    # All groups must be valid (3+ cards)
    for i, group in enumerate(new_floor):
        if len(group) < 3:
            return False, f"Group {i} has fewer than 3 cards"
        if not is_valid_group(group):
            return False, f"Group {i} is not a valid set or run"

    # Cross cards are anchored: each active cross card must appear in a
    # separate floor group (you can't merge two cross cards into one group)
    active_cross = [c for c in gs.cross if c is not None]
    if active_cross:
        cross_set = {(c.rank, c.suit) for c in active_cross}
        # Build a counter of cross cards to handle duplicates
        cross_counter = _card_counter(active_cross)
        cross_remaining = Counter(cross_counter)
        for group in new_floor:
            cross_in_group = 0
            for card in group:
                key = (card.rank, card.suit)
                if key in cross_set and cross_remaining.get(key, 0) > 0:
                    cross_remaining[key] -= 1
                    cross_in_group += 1
            if cross_in_group > 1:
                return False, "Cross cards are anchored — each must be in its own group"

    return True, "OK"


def apply_play(
    gs: GameState,
    player: str,
    new_floor: list[list[Card]],
    cards_played: list[Card],
) -> None:
    """
    Apply a validated play: remove cards from hand, update floor,
    mark incorporated cross as None, check win, advance turn.
    """
    # Remove played cards from hand
    hand = gs.hands[player]
    played_remaining = _card_counter(cards_played)
    new_hand = []
    for card in hand:
        key = (card.rank, card.suit)
        if played_remaining.get(key, 0) > 0:
            played_remaining[key] -= 1
        else:
            new_hand.append(card)
    gs.hands[player] = new_hand

    # Figure out which cross cards were incorporated into the new floor
    new_floor_counter = _card_counter([c for g in new_floor for c in g])
    old_floor_counter = _card_counter([c for g in gs.floor_groups for c in g])
    played_counter = _card_counter(cards_played)

    # Cards that must come from cross = new_floor - old_floor - cards_played
    # (whatever is left must be cross cards that got incorporated)
    remaining = Counter()
    remaining.update(new_floor_counter)
    remaining.subtract(old_floor_counter)
    remaining.subtract(played_counter)

    # Mark incorporated cross cards as None
    for i, cross_card in enumerate(gs.cross):
        if cross_card is not None:
            key = (cross_card.rank, cross_card.suit)
            if remaining.get(key, 0) > 0:
                remaining[key] -= 1
                gs.cross[i] = None

    gs.floor_groups = new_floor

    # Check win
    if len(gs.hands[player]) == 0:
        gs.game_over = True
        gs.winner = player
        return

    gs.current_player = "bot" if player == "human" else "human"


def game_state_to_dict(gs: GameState, for_player: str = "human") -> dict:
    """Serialize game state for API response. Hides opponent's hand."""
    active_cross = [card_to_dict(c) if c is not None else None
                    for c in gs.cross]
    return {
        "hand": [card_to_dict(c) for c in gs.hands[for_player]],
        "opponent_card_count": len(gs.hands["bot" if for_player == "human" else "human"]),
        "floor_groups": [
            [card_to_dict(c) for c in group] for group in gs.floor_groups
        ],
        "cross": active_cross,
        "deck_count": len(gs.deck),
        "current_player": gs.current_player,
        "game_over": gs.game_over,
        "winner": gs.winner,
    }
