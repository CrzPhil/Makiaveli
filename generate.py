#!/usr/bin/env python3
"""
Generate random Makiaveli game states for testing the solver.

Usage:
  python generate.py                         # one solvable state, 6 floor groups, ~2 hand groups
  python generate.py --floor 12 --hand-groups 4  # bigger game
  python generate.py --random --hand 8       # random state (may not be solvable)
  python generate.py --benchmark 50          # time 50 random solves
  python generate.py --seed 42               # reproducible
  python generate.py --feed                  # pipe directly into the interactive solver
"""

import argparse
import random
import sys
import time
from collections import Counter

from card import Card, SUITS, format_group
from solver import CardPool, solve, solve_hand, verify_solution, is_valid_group, is_valid_run, is_valid_set


# ---------------------------------------------------------------------------
# Random group generation
# ---------------------------------------------------------------------------

def _try_random_set(available, rng):
    """Try to form a random valid set from available cards."""
    by_rank = {}
    for (r, s), n in available.items():
        if n > 0:
            by_rank.setdefault(r, []).append(s)

    candidates = [(r, ss) for r, ss in by_rank.items() if len(ss) >= 3]
    if not candidates:
        return None

    rank, suits = rng.choice(candidates)
    size = rng.randint(3, min(4, len(suits)))
    chosen = rng.sample(suits, size)
    return [Card(rank, s) for s in chosen]


def _try_random_run(available, rng):
    """Try to form a random valid run from available cards."""
    suit = rng.choice(SUITS)
    ranks = sorted(r for r in range(1, 14) if available.get((r, suit), 0) > 0)
    if len(ranks) < 3:
        return None

    # Find maximal consecutive stretches
    seqs = []
    seq = [ranks[0]]
    for i in range(1, len(ranks)):
        if ranks[i] == seq[-1] + 1:
            seq.append(ranks[i])
        else:
            if len(seq) >= 3:
                seqs.append(seq)
            seq = [ranks[i]]
    if len(seq) >= 3:
        seqs.append(seq)

    if not seqs:
        return None

    seq = rng.choice(seqs)
    length = rng.randint(3, min(len(seq), 7))
    start = rng.randint(0, len(seq) - length)
    return [Card(r, suit) for r in seq[start:start + length]]


def _try_random_group(available, rng):
    if rng.random() < 0.4:
        return _try_random_set(available, rng)
    return _try_random_run(available, rng)


def generate_random_groups(count, rng, available=None):
    """Generate up to `count` valid groups from available cards."""
    if available is None:
        available = Counter({(r, s): 2 for r in range(1, 14) for s in SUITS})

    groups = []
    failures = 0
    while len(groups) < count and failures < 500:
        g = _try_random_group(available, rng)
        if g:
            groups.append(g)
            for c in g:
                available[(c.rank, c.suit)] -= 1
            failures = 0
        else:
            failures += 1
    return groups


# ---------------------------------------------------------------------------
# State generators
# ---------------------------------------------------------------------------

def generate_solvable(floor_count, hand_groups, rng):
    """
    Guaranteed-solvable state.

    Generates floor_count + hand_groups valid groups, uses the first
    floor_count as the floor and flattens the rest into the hand.
    """
    total = floor_count + hand_groups
    groups = generate_random_groups(total, rng)
    if len(groups) < total:
        return None, None

    rng.shuffle(groups)
    floor = [list(g) for g in groups[:floor_count]]
    hand = [c for g in groups[floor_count:] for c in g]
    return hand, floor


def generate_solvable_with_rearrangement(floor_count, hand_groups, rng):
    """
    Guaranteed-solvable state where the floor partition differs from
    the target, forcing the solver to rearrange.

    Strategy: generate target groups, split into hand + floor cards,
    then re-solve the floor cards into a different partition.
    """
    total = floor_count + hand_groups
    target_groups = generate_random_groups(total, rng)
    if len(target_groups) < total:
        return None, None

    rng.shuffle(target_groups)

    # Hand cards come from the last hand_groups groups
    hand = [c for g in target_groups[floor_count:] for c in g]

    # Floor cards come from the first floor_count groups
    floor_cards = [c for g in target_groups[:floor_count] for c in g]

    # Re-solve floor cards to get a (potentially different) partition
    pool = CardPool.from_cards(floor_cards)
    floor_groups = solve(pool)

    if floor_groups is None:
        # Fallback: use original groups
        floor = [list(g) for g in target_groups[:floor_count]]
    else:
        floor = [list(g) for g in floor_groups]

    return hand, floor


def generate_random_state(floor_count, hand_size, rng):
    """Random state — not guaranteed solvable."""
    available = Counter({(r, s): 2 for r in range(1, 14) for s in SUITS})
    floor = [list(g) for g in generate_random_groups(floor_count, rng, available.copy())]

    used = Counter()
    for g in floor:
        for c in g:
            used[(c.rank, c.suit)] += 1

    remaining = []
    for r in range(1, 14):
        for s in SUITS:
            remaining.extend([Card(r, s)] * (2 - used.get((r, s), 0)))
    rng.shuffle(remaining)
    hand = remaining[:hand_size]
    return hand, floor


# ---------------------------------------------------------------------------
# Display
# ---------------------------------------------------------------------------

def display_state(hand, floor, label=""):
    if label:
        print(f"\n--- {label} ---")
    print(f"Hand ({len(hand)}): {', '.join(str(c) for c in sorted(hand))}")
    total_floor = sum(len(g) for g in floor)
    print(f"Floor ({len(floor)} groups, {total_floor} cards):")
    for i, g in enumerate(floor):
        print(f"  [{i:2d}] {format_group(g)}")


def solver_input(hand, floor):
    """
    Format state as input lines for the interactive solver (main.py).

    The solver expects:
      line 1: hand (space-separated)
      line 2: cross cards (blank = none)
      lines 3+: one floor group per line
      blank line: end of floor
      s: solve
      n: don't try another
    """
    def card_code(c):
        from card import RANK_NAMES
        r = RANK_NAMES.get(c.rank, str(c.rank))
        return f"{r}{c.suit}"

    lines = []
    lines.append(' '.join(card_code(c) for c in hand))
    lines.append('')  # no cross cards (they're already in floor groups)
    for g in floor:
        lines.append(' '.join(card_code(c) for c in g))
    lines.append('')  # end of floor
    lines.append('s')  # solve
    lines.append('n')  # don't try another
    return '\n'.join(lines)


# ---------------------------------------------------------------------------
# Benchmark
# ---------------------------------------------------------------------------

def run_benchmark(args, rng):
    solved = 0
    total = 0
    times = []

    for i in range(args.benchmark):
        if args.random:
            hand_size = args.hand or 5
            hand, floor = generate_random_state(args.floor, hand_size, rng)
        elif args.rearrange:
            hand, floor = generate_solvable_with_rearrangement(
                args.floor, args.hand_groups, rng)
        else:
            hand, floor = generate_solvable(args.floor, args.hand_groups, rng)

        if hand is None:
            continue

        total += 1
        hand_n = len(hand)
        floor_n = sum(len(g) for g in floor)
        card_count = hand_n + floor_n

        t0 = time.time()
        solvable, _, _ = solve_hand(hand, floor)
        elapsed = time.time() - t0
        times.append(elapsed)

        if solvable:
            solved += 1

        if not args.quiet:
            tag = "OK" if solvable else "NO"
            print(f"  [{i + 1:3d}] {tag}  hand={hand_n:2d}  "
                  f"floor={floor_n:2d}  groups={len(floor):2d}  "
                  f"total={card_count:3d}  {elapsed:.4f}s")

    print(f"\nResults: {solved}/{total} solved")
    if times:
        avg = sum(times) / len(times)
        print(f"Time: min={min(times):.4f}s  avg={avg:.4f}s  max={max(times):.4f}s  "
              f"total={sum(times):.2f}s")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    p = argparse.ArgumentParser(
        description="Generate Makiaveli game states for testing")

    p.add_argument('--floor', type=int, default=6,
                   help='Number of floor groups (default: 6)')
    p.add_argument('--hand-groups', type=int, default=2,
                   help='Groups flattened into hand — solvable mode (default: 2)')
    p.add_argument('--hand', type=int, default=0,
                   help='Exact hand size — random mode (default: 5)')
    p.add_argument('--random', action='store_true',
                   help='Random state (may be unsolvable)')
    p.add_argument('--rearrange', action='store_true',
                   help='Generate solvable state that requires rearrangement')
    p.add_argument('--benchmark', type=int, default=0, metavar='N',
                   help='Benchmark N iterations')
    p.add_argument('--seed', type=int, default=None,
                   help='Random seed for reproducibility')
    p.add_argument('--feed', action='store_true',
                   help='Print solver-compatible input (pipe into main.py)')
    p.add_argument('--quiet', action='store_true',
                   help='Minimal output (benchmark mode)')

    args = p.parse_args()
    rng = random.Random(args.seed)

    if args.benchmark:
        run_benchmark(args, rng)
        return

    # Generate
    if args.random:
        hand, floor = generate_random_state(args.floor, args.hand or 5, rng)
    elif args.rearrange:
        hand, floor = generate_solvable_with_rearrangement(
            args.floor, args.hand_groups, rng)
    else:
        hand, floor = generate_solvable(args.floor, args.hand_groups, rng)

    if hand is None:
        print("Failed to generate state. Try different parameters.", file=sys.stderr)
        sys.exit(1)

    # Output
    if args.feed:
        print(solver_input(hand, floor))
        return

    display_state(hand, floor, "Generated State")

    # Solve
    print(f"\nSolving...")
    t0 = time.time()
    solvable, target, _ = solve_hand(hand, floor)
    elapsed = time.time() - t0

    if solvable:
        print(f"SOLVABLE  ({elapsed:.4f}s)\n")
        print("Target layout:")
        for i, g in enumerate(target):
            print(f"  [{i:2d}] {format_group(list(g))}")

        from step_planner import plan_steps
        steps = plan_steps(floor, target, hand)
        if steps:
            print(f"\nSteps ({len(steps)}):")
            for i, step in enumerate(steps, 1):
                print(f"  {i}. {step}")
    else:
        print(f"NOT SOLVABLE  ({elapsed:.4f}s)")

    # Show pipeable input
    print(f"\n--- Solver input (pipe with: python generate.py --feed | python main.py) ---")
    print(solver_input(hand, floor))


if __name__ == '__main__':
    main()
