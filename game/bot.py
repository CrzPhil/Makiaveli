"""Heuristic bot for Makiaveli — wraps the solver."""

import time
from dataclasses import dataclass, field
from collections import Counter, defaultdict
from itertools import combinations

from card import Card, SUITS, card_to_dict
from solver import solve_hand, is_valid_group
from game.engine import GameState, draw_card, apply_play


@dataclass
class BotMove:
    action: str                          # "play" | "draw"
    cards_played: list[Card] = field(default_factory=list)
    new_floor_groups: list[list[Card]] = field(default_factory=list)
    drawn_card: Card | None = None
    steps: list[str] = field(default_factory=list)


def _active_cross(gs: GameState) -> list[Card]:
    """Return non-None cross cards."""
    return [c for c in gs.cross if c is not None]


def _respects_cross_anchoring(groups, cross_cards):
    """Check that no group contains more than one cross card."""
    if not cross_cards:
        return True
    cross_set = {(c.rank, c.suit) for c in cross_cards}
    cross_counter = Counter((c.rank, c.suit) for c in cross_cards)
    remaining = Counter(cross_counter)
    for group in groups:
        count = 0
        for card in group:
            key = (card.rank, card.suit)
            if key in cross_set and remaining.get(key, 0) > 0:
                remaining[key] -= 1
                count += 1
        if count > 1:
            return False
    return True


def _try_solve(hand_cards, floor_groups, cross, timeout=3.0):
    """Try to solve with a timeout. Returns (solvable, groups, remaining_cross)."""
    import solver
    old_timeout = solver._OVERALL_TIMEOUT
    solver._OVERALL_TIMEOUT = timeout
    try:
        return solve_hand(hand_cards, floor_groups, cross)
    finally:
        solver._OVERALL_TIMEOUT = old_timeout


# ── Direct group finding (no solver needed) ─────────────────────────

def _find_sets(hand):
    """Find all valid sets (same rank, 3-4 different suits) from hand cards."""
    by_rank = defaultdict(list)
    for card in hand:
        by_rank[card.rank].append(card)

    sets = []
    for rank, cards in by_rank.items():
        # Deduplicate by suit (keep one per suit)
        by_suit = {}
        for c in cards:
            if c.suit not in by_suit:
                by_suit[c.suit] = c
        unique = list(by_suit.values())
        if len(unique) >= 3:
            # Prefer the largest set
            sets.append(unique)
            if len(unique) > 3:
                # Also offer 3-card subsets
                for combo in combinations(unique, 3):
                    sets.append(list(combo))
    return sets


def _find_runs(hand):
    """Find all valid runs (same suit, 3+ consecutive) from hand cards."""
    by_suit = defaultdict(list)
    for card in hand:
        by_suit[card.suit].append(card)

    runs = []
    for suit, cards in by_suit.items():
        # Deduplicate by rank
        by_rank = {}
        for c in cards:
            by_rank[c.rank] = c
        ranks = sorted(by_rank.keys())

        # Find consecutive sequences of length 3+
        i = 0
        while i < len(ranks):
            j = i
            while j + 1 < len(ranks) and ranks[j + 1] == ranks[j] + 1:
                j += 1
            seq_len = j - i + 1
            if seq_len >= 3:
                # Add all sub-runs of length 3+ (prefer longest)
                for start in range(i, j - 1):
                    for end in range(start + 2, j + 1):
                        run = [by_rank[ranks[r]] for r in range(start, end + 1)]
                        runs.append(run)
            i = j + 1

        # Ace-high runs: check if we have A and K and a sequence ending at K
        if 1 in by_rank and 13 in by_rank:
            hi = 13
            while hi - 1 >= 2 and (hi - 1) in by_rank:
                hi -= 1
            # sequences ending at K that include A as high
            for start in range(hi, 13):
                if 13 - start + 1 >= 2:  # need at least 2 + ace = 3
                    run = [by_rank[r] for r in range(start, 14)] + [by_rank[1]]
                    if len(run) >= 3:
                        runs.append(run)

    return runs


def _find_hand_groups(hand):
    """Find all valid groups playable directly from hand, sorted largest first."""
    groups = _find_sets(hand) + _find_runs(hand)
    # Deduplicate and sort by size descending
    seen = set()
    unique = []
    for g in groups:
        key = tuple(sorted((c.rank, c.suit) for c in g))
        if key not in seen:
            seen.add(key)
            unique.append(g)
    unique.sort(key=lambda g: -len(g))
    return unique


def _find_cross_groups(hand, cross):
    """Find valid groups that incorporate a cross card with hand cards."""
    groups = []
    for cross_card in cross:
        # Try sets: same rank from hand + cross card
        same_rank = [c for c in hand if c.rank == cross_card.rank and c.suit != cross_card.suit]
        by_suit = {}
        for c in same_rank:
            if c.suit not in by_suit:
                by_suit[c.suit] = c
        unique_suits = list(by_suit.values())
        if len(unique_suits) >= 2:
            group = [cross_card] + unique_suits
            if is_valid_group(group):
                groups.append(group)
            # Also try 3-card subsets
            for combo in combinations(unique_suits, 2):
                group = [cross_card] + list(combo)
                if is_valid_group(group):
                    groups.append(group)

        # Try runs: same suit, consecutive with cross card
        same_suit = {c.rank: c for c in hand if c.suit == cross_card.suit}
        same_suit[cross_card.rank] = cross_card
        ranks = sorted(same_suit.keys())
        # Find consecutive sequences containing cross_card.rank
        for i in range(len(ranks)):
            for j in range(i + 2, len(ranks)):
                seq = ranks[i:j + 1]
                if all(seq[k] + 1 == seq[k + 1] for k in range(len(seq) - 1)):
                    if cross_card.rank in seq:
                        run = [same_suit[r] for r in seq]
                        if is_valid_group(run):
                            groups.append(run)

    # Deduplicate
    seen = set()
    unique = []
    for g in groups:
        key = tuple(sorted((c.rank, c.suit) for c in g))
        if key not in seen:
            seen.add(key)
            unique.append(g)
    unique.sort(key=lambda g: -len(g))
    return unique


def _find_floor_extensions(hand, floor):
    """
    Find hand cards that can extend existing floor groups.
    Returns list of (floor_index, card, new_group) tuples, sorted by
    number of cards played descending.
    """
    extensions = []
    for fi, group in enumerate(floor):
        for card in hand:
            extended = group + [card]
            if is_valid_group(extended):
                extensions.append((fi, card, extended))
    return extensions


# ── Greedy multi-group play ─────────────────────────────────────────

def _greedy_play(hand, floor, cross):
    """
    Find multiple non-overlapping plays at once: new groups from hand,
    cross incorporations, and extensions to existing floor groups.
    Returns (new_floor, cards_played) or (None, []) if nothing found.
    """
    remaining = list(hand)
    modified_floor = [list(g) for g in floor]
    played_cards = []
    made_any = False

    for _ in range(10):  # cap iterations
        # Find all candidate plays from remaining hand
        new_groups = _find_hand_groups(remaining) + _find_cross_groups(remaining, cross)
        extensions = _find_floor_extensions(remaining, modified_floor)

        # Score: new groups by number of hand cards used, extensions by 1 card
        best_play = None  # ("new", group) or ("ext", fi, card, new_group)
        best_score = 0

        for group in new_groups:
            hand_cards = [c for c in group if c in remaining]
            cross_in = [c for c in group if c not in remaining
                        and any(cr.rank == c.rank and cr.suit == c.suit for cr in cross)]
            if len(hand_cards) + len(cross_in) == len(group):
                score = len(hand_cards)
                if score > best_score:
                    best_score = score
                    best_play = ("new", group)

        for fi, card, new_group in extensions:
            if card in remaining:
                if 1 > best_score:  # extensions play 1 card, prefer new groups
                    best_score = 1
                    best_play = ("ext", fi, card, new_group)

        if best_play is None:
            break

        made_any = True
        if best_play[0] == "new":
            group = best_play[1]
            modified_floor.append(group)
            for c in group:
                if c in remaining:
                    remaining.remove(c)
                    played_cards.append(c)
        else:
            _, fi, card, new_group = best_play
            modified_floor[fi] = new_group
            remaining.remove(card)
            played_cards.append(card)

    if not made_any:
        return None, []
    return modified_floor, played_cards


# ── Main bot logic ──────────────────────────────────────────────────

def bot_turn(gs: GameState) -> BotMove:
    """
    Decide and execute the bot's turn.

    Strategy:
    1. Try full hand — if solvable, play all (win!)
    2. Find obvious groups directly from hand (no solver needed)
    3. Try solver for floor-rearrangement plays
    4. If nothing works, draw
    """
    hand = list(gs.hands["bot"])
    floor = [list(g) for g in gs.floor_groups]
    cross = _active_cross(gs)

    # 1. Try playing entire hand (win check)
    solvable, groups, remaining_cross = _try_solve(hand, floor, cross, timeout=1.0)
    if solvable and _respects_cross_anchoring(groups, cross):
        cards_played = list(hand)
        new_floor = [list(g) for g in groups]
        steps = [f"Bot plays all {len(cards_played)} cards and wins!"]
        apply_play(gs, "bot", new_floor, cards_played)
        return BotMove(
            action="play",
            cards_played=cards_played,
            new_floor_groups=new_floor,
            steps=steps,
        )

    # 2. Find obvious plays directly from hand (instant, no solver)
    new_floor, play_cards = _greedy_play(hand, floor, cross)
    if new_floor is not None:
        steps = [f"Bot plays {len(play_cards)} card(s)"]
        for c in play_cards:
            steps.append(f"  Played {c}")
        apply_play(gs, "bot", new_floor, play_cards)
        return BotMove(
            action="play",
            cards_played=play_cards,
            new_floor_groups=new_floor,
            steps=steps,
        )

    # 3. Try solver-based plays with floor rearrangement (small subsets only)
    if floor:
        deadline = time.time() + 2.0
        # Try small subsets (3-6 cards) that might work with floor rearrangement
        for k in range(3, min(len(hand) + 1, 7)):
            if time.time() > deadline:
                break
            for combo in combinations(range(len(hand)), k):
                if time.time() > deadline:
                    break
                subset = [hand[i] for i in combo]
                remaining = deadline - time.time()
                if remaining < 0.1:
                    break
                solvable, groups, remaining_cross = _try_solve(
                    subset, floor, cross, timeout=min(remaining, 0.5)
                )
                if solvable and _respects_cross_anchoring(groups, cross):
                    cards_played = subset
                    new_floor = [list(g) for g in groups]
                    steps = [f"Bot plays {len(cards_played)} card(s)"]
                    for c in cards_played:
                        steps.append(f"  Played {c}")
                    apply_play(gs, "bot", new_floor, cards_played)
                    return BotMove(
                        action="play",
                        cards_played=cards_played,
                        new_floor_groups=new_floor,
                        steps=steps,
                    )

    # 4. Draw
    drawn = draw_card(gs, "bot")
    steps = ["Bot draws a card"] if drawn else ["Bot passes (deck empty)"]
    return BotMove(action="draw", drawn_card=drawn, steps=steps)


def bot_move_to_dict(move: BotMove) -> dict:
    """Serialize a BotMove for the API response."""
    result = {
        "action": move.action,
        "steps": move.steps,
    }
    if move.action == "play":
        result["cards_played"] = [card_to_dict(c) for c in move.cards_played]
        result["new_floor_groups"] = [
            [card_to_dict(c) for c in g] for g in move.new_floor_groups
        ]
    return result
