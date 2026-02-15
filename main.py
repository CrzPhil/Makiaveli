#!/usr/bin/env python3
"""
Makiaveli Solver — CLI entry point.

Usage:
    python main.py

Interactively enter your hand and the current floor state, and the solver
will determine if you can empty your hand and show you the steps.
"""

from card import parse_card, format_group
from solver import solve_hand, verify_solution
from step_planner import plan_steps


def read_cards(prompt):
    """Read a space-separated list of cards from stdin."""
    raw = input(prompt).strip()
    if not raw:
        return []
    return [parse_card(tok) for tok in raw.split()]


def read_floor():
    """Read floor groups, one group per line, blank line to finish."""
    print("Enter floor groups (one group per line, blank line to finish):")
    groups = []
    while True:
        raw = input("  > ").strip()
        if not raw:
            break
        group = [parse_card(tok) for tok in raw.split()]
        groups.append(group)
    return groups


def display_state(hand, floor_groups):
    """Pretty-print the current game state."""
    print("\n--- Current State ---")
    print(f"Hand: {', '.join(str(c) for c in hand)}")
    print("Floor:")
    if not floor_groups:
        print("  (empty)")
    for i, group in enumerate(floor_groups):
        print(f"  [{i}] {format_group(group)}")
    print()


def main():
    print("=== Makiaveli Solver ===\n")

    hand = read_cards("Enter your hand (e.g. '3S 4S 7D'): ")
    floor_groups = read_floor()

    display_state(hand, floor_groups)

    if not hand:
        print("Hand is empty — you've already won!")
        return

    print("Solving...\n")
    solvable, target_groups = solve_hand(hand, floor_groups)

    if not solvable:
        print("No solution found. You cannot empty your hand from this state.")
        return

    # Verify the solution is correct
    all_cards = list(hand)
    for g in floor_groups:
        all_cards.extend(g)
    valid, msg = verify_solution(all_cards, target_groups)
    if not valid:
        print(f"Internal error: solver produced invalid result ({msg})")
        return

    # Show target layout
    print("Solution found!\n")
    print("Target layout:")
    for i, group in enumerate(target_groups):
        print(f"  [{i}] {format_group(list(group))}")

    # Show steps
    steps = plan_steps(floor_groups, target_groups, hand)
    if steps:
        print(f"\nSteps ({len(steps)}):")
        for i, step in enumerate(steps, 1):
            print(f"  {i}. {step}")
    else:
        print("\nNo rearrangement needed — just play your cards!")


if __name__ == '__main__':
    main()
