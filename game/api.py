"""Makiaveli game — API endpoints."""

import uuid
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from card import parse_card
from game.engine import (
    GameState, new_game, draw_card, validate_play, apply_play,
    game_state_to_dict,
)
from game.bot import bot_turn, bot_move_to_dict

router = APIRouter(prefix="/api/game")

# In-memory session store
games: dict[str, GameState] = {}


class PlayRequest(BaseModel):
    floor_groups: list[list[str]]
    cards_played: list[str]


def _get_game(game_id: str) -> GameState:
    gs = games.get(game_id)
    if gs is None:
        raise HTTPException(status_code=404, detail="Game not found")
    return gs


@router.post("/new")
def api_new_game():
    game_id = str(uuid.uuid4())[:8]
    gs = new_game()
    games[game_id] = gs
    state = game_state_to_dict(gs)
    state["game_id"] = game_id
    return state


@router.get("/{game_id}/state")
def api_game_state(game_id: str):
    gs = _get_game(game_id)
    state = game_state_to_dict(gs)
    state["game_id"] = game_id
    return state


@router.post("/{game_id}/draw")
def api_draw(game_id: str):
    gs = _get_game(game_id)

    if gs.game_over:
        raise HTTPException(status_code=400, detail="Game is over")
    if gs.current_player != "human":
        raise HTTPException(status_code=400, detail="Not your turn")

    drawn = draw_card(gs, "human")
    from card import card_to_dict
    drawn_dict = card_to_dict(drawn) if drawn else None

    # Bot plays its turn
    bot_move = None
    if not gs.game_over and gs.current_player == "bot":
        move = bot_turn(gs)
        bot_move = bot_move_to_dict(move)

    state = game_state_to_dict(gs)
    state["game_id"] = game_id
    state["drawn_card"] = drawn_dict
    state["bot_move"] = bot_move
    return state


@router.post("/{game_id}/play")
def api_play(game_id: str, req: PlayRequest):
    gs = _get_game(game_id)

    if gs.game_over:
        raise HTTPException(status_code=400, detail="Game is over")
    if gs.current_player != "human":
        raise HTTPException(status_code=400, detail="Not your turn")

    try:
        new_floor = [[parse_card(c) for c in group] for group in req.floor_groups]
        cards_played = [parse_card(c) for c in req.cards_played]
    except (ValueError, IndexError) as e:
        raise HTTPException(status_code=400, detail=str(e))

    ok, msg = validate_play(gs, "human", new_floor, cards_played)
    if not ok:
        raise HTTPException(status_code=400, detail=msg)

    apply_play(gs, "human", new_floor, cards_played)

    # Bot plays its turn
    bot_move = None
    if not gs.game_over and gs.current_player == "bot":
        move = bot_turn(gs)
        bot_move = bot_move_to_dict(move)

    state = game_state_to_dict(gs)
    state["game_id"] = game_id
    state["bot_move"] = bot_move
    return state
