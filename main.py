#!/usr/bin/env python3
"""
Makiaveli Solver — interactive CLI.

Walks you through entering your hand, cross cards, and floor groups,
validates as you go, shows a summary, and lets you edit before solving.
"""

from card import Card, parse_card, format_group
from solver import solve_hand, verify_solution, is_valid_group
from step_planner import plan_steps


def prompt_cards(prompt, *, allow_empty=False):
    """Read space-separated cards with validation. Returns list of Cards."""
    while True:
        raw = input(prompt).strip()
        if not raw and allow_empty:
            return []
        if not raw:
            print("  Please enter at least one card.")
            continue
        try:
            cards = [parse_card(tok) for tok in raw.split()]
            return cards
        except (ValueError, IndexError) as e:
            print(f"  Bad input: {e}  — try again.")


def input_hand():
    """Prompt for the player's hand."""
    print("Your hand")
    print("  Cards you're holding, space-separated.")
    print("  Format: rank + suit letter (S/H/D/C)")
    print("  e.g.  3S 4S 7D AH 10C KD\n")
    cards = prompt_cards("  Hand: ")
    print(f"  -> {', '.join(str(c) for c in cards)}\n")
    return cards


def input_cross():
    """Prompt for cross cards (0-4 single cards around the deck)."""
    print("Cross cards")
    print("  The single cards around the deck (up to 4).")
    print("  Leave blank if all cross cards have already been played on.\n")
    cards = prompt_cards("  Cross: ", allow_empty=True)
    if cards:
        if len(cards) > 4:
            print("  Warning: more than 4 cross cards entered.")
        print(f"  -> {', '.join(str(c) for c in cards)}\n")
    else:
        print("  -> (none)\n")
    return cards


def input_floor():
    """Prompt for floor groups (existing combinations on the table)."""
    print("Floor groups")
    print("  Existing combinations on the table (not the cross).")
    print("  Enter one group per line, blank line when done.\n")
    groups = []
    n = 1
    while True:
        raw = input(f"  Group {n}: ").strip()
        if not raw:
            break
        try:
            group = [parse_card(tok) for tok in raw.split()]
        except (ValueError, IndexError) as e:
            print(f"  Bad input: {e}  — try again.")
            continue

        if not is_valid_group(group):
            print(f"  Warning: {format_group(group)} is not a valid combination.")
            confirm = input("  Add anyway? [y/N] ").strip().lower()
            if confirm != 'y':
                continue

        groups.append(group)
        print(f"       -> {format_group(group)}")
        n += 1

    if groups:
        print()
    else:
        print("  -> (no floor groups)\n")
    return groups


def display_summary(hand, cross, floor_groups):
    """Show a full summary of the entered state."""
    print("=" * 44)
    print("  SUMMARY")
    print("=" * 44)

    print(f"\n  Hand ({len(hand)}):  {', '.join(str(c) for c in hand)}")

    if cross:
        print(f"  Cross ({len(cross)}): {', '.join(str(c) for c in cross)}")
    else:
        print("  Cross:    (none)")

    print("  Floor:")
    all_groups = build_floor(cross, floor_groups)
    if not all_groups:
        print("    (empty)")
    for i, group in enumerate(all_groups):
        label = "(cross)" if len(group) == 1 and group[0] in cross else ""
        print(f"    [{i}] {format_group(group)}  {label}")

    total = len(hand) + sum(len(g) for g in all_groups)
    print(f"\n  Total cards: {total}")
    print("=" * 44)
    print()


def build_floor(cross, floor_groups):
    """Merge cross cards (as single-card groups) with floor groups."""
    groups = [[c] for c in cross]
    groups.extend(floor_groups)
    return groups


def prompt_action():
    """Ask the user what to do: solve, edit, or quit."""
    while True:
        choice = input("[S]olve / [E]dit / [Q]uit: ").strip().lower()
        if choice in ('s', 'solve', ''):
            return 'solve'
        if choice in ('e', 'edit'):
            return 'edit'
        if choice in ('q', 'quit'):
            return 'quit'
        print("  Please enter S, E, or Q.")


def prompt_edit():
    """Ask what to re-enter."""
    while True:
        choice = input("  Re-enter [H]and / [C]ross / [F]loor / [A]ll: ").strip().lower()
        if choice in ('h', 'hand'):
            return 'hand'
        if choice in ('c', 'cross'):
            return 'cross'
        if choice in ('f', 'floor'):
            return 'floor'
        if choice in ('a', 'all'):
            return 'all'
        print("  Please enter H, C, F, or A.")


def run_solver(hand, cross, floor_groups):
    """Run the solver and display results."""
    print("Solving...\n")
    solvable, target_groups, remaining_cross = solve_hand(
        hand, floor_groups, cross)

    if not solvable:
        print("No solution. You cannot empty your hand from this state.\n")
        return

    # Verify correctness — only placed cards should be in the partition
    # Use consume-from-copy to handle duplicate cross cards correctly
    remaining_copy = list(remaining_cross)
    included_cross = []
    for c in cross:
        if c in remaining_copy:
            remaining_copy.remove(c)
        else:
            included_cross.append(c)
    all_placed = list(hand) + included_cross
    for g in floor_groups:
        all_placed.extend(g)
    valid, msg = verify_solution(all_placed, target_groups)
    if not valid:
        print(f"Internal error: solver produced invalid result ({msg})\n")
        return

    # Target layout
    print("Solution found!\n")
    print("Target layout:")
    for i, group in enumerate(target_groups):
        print(f"  [{i}] {format_group(list(group))}")

    if remaining_cross:
        print(f"\n  Cross cards left in place: "
              f"{', '.join(str(c) for c in remaining_cross)}")

    # Steps — initial floor includes incorporated cross cards as singles
    initial_floor = list(floor_groups)
    for c in included_cross:
        initial_floor.append([c])
    steps = plan_steps(initial_floor, target_groups, hand)
    if steps:
        print(f"\nSteps ({len(steps)}):")
        for i, step in enumerate(steps, 1):
            print(f"  {i}. {step}")
    else:
        print("\nNo rearrangement needed — just play your cards!")
    print()


def main():
    print()
    print("=" * 44)
    print("        MAKIAVELI SOLVER")
    print("=" * 44)
    print()

    hand = input_hand()
    cross = input_cross()
    floor_groups = input_floor()

    while True:
        display_summary(hand, cross, floor_groups)
        action = prompt_action()

        if action == 'quit':
            print("Bye!")
            return

        if action == 'edit':
            part = prompt_edit()
            print()
            if part in ('hand', 'all'):
                hand = input_hand()
            if part in ('cross', 'all'):
                cross = input_cross()
            if part in ('floor', 'all'):
                floor_groups = input_floor()
            continue

        # Solve
        run_solver(hand, cross, floor_groups)

        again = input("Try another configuration? [y/N] ").strip().lower()
        if again == 'y':
            part = prompt_edit()
            print()
            if part in ('hand', 'all'):
                hand = input_hand()
            if part in ('cross', 'all'):
                cross = input_cross()
            if part in ('floor', 'all'):
                floor_groups = input_floor()
        else:
            print("Bye!")
            return


if __name__ == '__main__':
    main()
