#!/usr/bin/env python3
"""Makiaveli Solver — web API."""

import time
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from card import parse_card, SUIT_SYMBOLS, RANK_NAMES
from solver import solve_hand, is_valid_group, is_valid_set, is_valid_run
from step_planner import plan_steps

app = FastAPI()


# ── Models ──────────────────────────────────────────────────────────────

class SolveRequest(BaseModel):
    hand: list[str]
    cross: list[str] = []
    floor_groups: list[list[str]] = []


class ValidateGroupRequest(BaseModel):
    cards: list[str]


# ── Helpers ─────────────────────────────────────────────────────────────

def card_to_dict(card):
    r = RANK_NAMES.get(card.rank, str(card.rank))
    return {
        "code": f"{r}{card.suit}",
        "rank": card.rank,
        "suit": card.suit,
        "display": f"{r}{SUIT_SYMBOLS[card.suit]}",
    }


# ── Endpoints ───────────────────────────────────────────────────────────

@app.post("/api/solve")
def api_solve(req: SolveRequest):
    try:
        hand = [parse_card(c) for c in req.hand]
        cross = [parse_card(c) for c in req.cross]
        floor_groups = [[parse_card(c) for c in g] for g in req.floor_groups]
    except (ValueError, IndexError) as e:
        return {"error": str(e)}

    t0 = time.time()
    solvable, target_groups, remaining_cross = solve_hand(
        hand, floor_groups, cross
    )
    elapsed = round(time.time() - t0, 3)

    if not solvable:
        return {"solvable": False, "elapsed_seconds": elapsed}

    # Figure out which cross cards were included vs remaining
    remaining_copy = list(remaining_cross)
    included_cross = []
    for c in cross:
        if c in remaining_copy:
            remaining_copy.remove(c)
        else:
            included_cross.append(c)

    # Build initial floor for step planning (includes incorporated cross)
    initial_floor = list(floor_groups)
    for c in included_cross:
        initial_floor.append([c])

    steps = plan_steps(initial_floor, target_groups, hand)

    return {
        "solvable": True,
        "target_groups": [
            [card_to_dict(c) for c in group] for group in target_groups
        ],
        "remaining_cross": [card_to_dict(c) for c in remaining_cross],
        "steps": [
            {"step_number": i + 1, "description": s}
            for i, s in enumerate(steps)
        ],
        "elapsed_seconds": elapsed,
    }


@app.post("/api/validate-group")
def api_validate_group(req: ValidateGroupRequest):
    try:
        cards = [parse_card(c) for c in req.cards]
    except (ValueError, IndexError) as e:
        return {"valid": False, "error": str(e)}

    valid = is_valid_group(cards)
    group_type = None
    if valid:
        if is_valid_set(cards):
            group_type = "set"
        elif is_valid_run(cards):
            group_type = "run"

    return {
        "valid": valid,
        "group_type": group_type,
        "display": [card_to_dict(c) for c in cards],
    }


# Static files — must be last so it doesn't shadow /api routes
app.mount("/", StaticFiles(directory="static", html=True), name="static")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
