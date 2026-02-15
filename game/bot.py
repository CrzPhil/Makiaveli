"""Heuristic bot for Makiaveli — wraps the solver."""

import time
from dataclasses import dataclass, field
from itertools import combinations

from card import Card, card_to_dict
from solver import solve_hand
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


def _try_solve(hand_cards, floor_groups, cross, timeout=3.0):
    """Try to solve with a timeout. Returns (solvable, groups, remaining_cross)."""
    import solver
    old_timeout = solver._OVERALL_TIMEOUT
    solver._OVERALL_TIMEOUT = timeout
    try:
        return solve_hand(hand_cards, floor_groups, cross)
    finally:
        solver._OVERALL_TIMEOUT = old_timeout


def bot_turn(gs: GameState) -> BotMove:
    """
    Decide and execute the bot's turn.

    Strategy:
    1. Try full hand — if solvable, play all (win!)
    2. Try subsets largest-first with 3s budget per attempt
    3. If nothing works, draw
    """
    hand = list(gs.hands["bot"])
    floor = [list(g) for g in gs.floor_groups]
    cross = _active_cross(gs)

    # 1. Try playing entire hand
    solvable, groups, remaining_cross = _try_solve(hand, floor, cross, timeout=3.0)
    if solvable:
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

    # 2. Try subsets, largest first
    deadline = time.time() + 5.0
    for k in range(len(hand) - 1, 0, -1):
        if time.time() > deadline:
            break
        for combo in combinations(range(len(hand)), k):
            if time.time() > deadline:
                break
            subset = [hand[i] for i in combo]
            remaining = 3.0 - (time.time() - (deadline - 5.0))
            if remaining < 0.5:
                break
            solvable, groups, remaining_cross = _try_solve(
                subset, floor, cross, timeout=min(remaining, 2.0)
            )
            if solvable:
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

    # 3. Draw
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
