import time
from itertools import combinations
from collections import Counter
from card import Card, SUITS

SUIT_IDX = {s: i for i, s in enumerate(SUITS)}


class CardPool:
    """Tracks available cards as a 13x4 count matrix (handles 2-deck duplicates)."""

    def __init__(self):
        self._counts = [[0] * 4 for _ in range(13)]
        self._total = 0

    def add(self, card):
        self._counts[card.rank - 1][SUIT_IDX[card.suit]] += 1
        self._total += 1

    def remove(self, card):
        ri, si = card.rank - 1, SUIT_IDX[card.suit]
        assert self._counts[ri][si] > 0, f"Cannot remove {card}: count is 0"
        self._counts[ri][si] -= 1
        self._total -= 1

    def get(self, rank, suit):
        return self._counts[rank - 1][SUIT_IDX[suit]]

    @property
    def total(self):
        return self._total

    def is_empty(self):
        return self._total == 0

    def remove_group(self, group):
        for c in group:
            self.remove(c)

    def add_group(self, group):
        for c in group:
            self.add(c)

    @classmethod
    def from_cards(cls, cards):
        pool = cls()
        for c in cards:
            pool.add(c)
        return pool


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def is_valid_set(group):
    """Same rank, different suits, 3+ cards."""
    if len(group) < 3:
        return False
    return (len(set(c.rank for c in group)) == 1
            and len(set(c.suit for c in group)) == len(group))


def is_valid_run(group):
    """Same suit, consecutive ranks, no duplicates, 3+ cards. Ace can be high or low."""
    if len(group) < 3:
        return False
    if len(set(c.suit for c in group)) != 1:
        return False
    ranks = sorted(c.rank for c in group)
    if len(ranks) != len(set(ranks)):
        return False
    # Normal consecutive
    if all(ranks[i] + 1 == ranks[i + 1] for i in range(len(ranks) - 1)):
        return True
    # Ace-high: treat 1 as 14
    if 1 in ranks and 13 in ranks:
        high = sorted(14 if r == 1 else r for r in ranks)
        return all(high[i] + 1 == high[i + 1] for i in range(len(high) - 1))
    return False


def is_valid_group(group):
    return is_valid_set(group) or is_valid_run(group)


# ---------------------------------------------------------------------------
# Group enumeration (used by the solver)
# ---------------------------------------------------------------------------

def _sets_containing(rank, suit, pool):
    """All valid sets (same rank, 3-4 different suits) that include (rank, suit)."""
    others = [s for s in SUITS if s != suit and pool.get(rank, s) > 0]
    results = []
    for size in range(2, len(others) + 1):
        for combo in combinations(others, size):
            results.append(tuple(Card(rank, s) for s in (suit,) + combo))
    return results


def _runs_containing(rank, suit, pool):
    """All valid runs (same suit, consecutive, 3+) that include (rank, suit)."""
    avail = {r for r in range(1, 14) if pool.get(r, suit) > 0}
    if rank not in avail:
        return []

    results = []

    # Normal runs: consecutive sequences within [1..13]
    lo = rank
    while lo - 1 >= 1 and (lo - 1) in avail:
        lo -= 1
    hi = rank
    while hi + 1 <= 13 and (hi + 1) in avail:
        hi += 1

    for start in range(lo, rank + 1):
        for end in range(max(rank, start + 2), hi + 1):
            results.append(tuple(Card(r, suit) for r in range(start, end + 1)))

    # Ace-high runs: sequences ending with ace as rank 14
    # E.g., [Q, K, A] = ranks [12, 13, 1]
    if 1 in avail and 13 in avail:
        ace_lo = 13
        while ace_lo - 1 >= 2 and (ace_lo - 1) in avail:
            ace_lo -= 1

        for start in range(ace_lo, 13):  # need at least 3: start..13, A
            run_ranks = list(range(start, 14)) + [1]
            if rank in run_ranks:
                results.append(tuple(Card(r, suit) for r in run_ranks))

    return results


def _groups_for(card, pool):
    """All valid groups that include the given card."""
    return _sets_containing(card.rank, card.suit, pool) + \
           _runs_containing(card.rank, card.suit, pool)


# ---------------------------------------------------------------------------
# Solver (backtracking with most-constrained-first heuristic)
# ---------------------------------------------------------------------------

def solve(pool, deadline=None):
    """
    Partition all cards in pool into valid groups.

    Returns list of groups (each a tuple of Cards) if solvable, None otherwise.
    Optional deadline (time.time() value) for timeout.
    """
    if pool.is_empty():
        return []

    if pool.total < 3:
        return None

    if deadline is not None and time.time() > deadline:
        return None

    # Find the most constrained card (fewest valid groups)
    best_card = None
    best_groups = None
    best_n = float('inf')

    for r in range(13):
        for si, s in enumerate(SUITS):
            if pool._counts[r][si] > 0:
                card = Card(r + 1, s)
                groups = _groups_for(card, pool)
                if not groups:
                    return None  # dead end — this card can't go anywhere
                if len(groups) < best_n:
                    best_n = len(groups)
                    best_card = card
                    best_groups = groups
                    if best_n == 1:
                        break
        if best_n == 1:
            break

    for group in best_groups:
        pool.remove_group(group)
        result = solve(pool, deadline)
        if result is not None:
            pool.add_group(group)
            return [group] + result
        pool.add_group(group)

    return None


# ---------------------------------------------------------------------------
# Incremental solver for solve_hand
# ---------------------------------------------------------------------------

_MAX_ATTEMPTS = 50000    # cap on total sub-problems tried
_SUB_TIMEOUT = 5.0       # seconds per sub-problem solve
_OVERALL_TIMEOUT = 60.0  # seconds for entire solve_hand call


def _relevance_scores(hand_cards, floor_groups):
    """
    Score each floor group by how relevant it is to placing the hand cards.
    Higher score = more likely to need dissolution.
    """
    hand_ranks = set(c.rank for c in hand_cards)
    hand_suits = set(c.suit for c in hand_cards)

    scores = []
    for i, g in enumerate(floor_groups):
        score = 0
        for c in g:
            if c.rank in hand_ranks:
                score += 2
            if c.suit in hand_suits:
                score += 1
        scores.append((i, score))

    return scores


def _solve_incremental(hand_cards, floor_groups, deadline):
    """
    Place hand_cards while keeping as many floor groups intact as possible.

    Strategy: iteratively dissolve 0, 1, 2, ... floor groups (most relevant
    first) and re-partition only the dissolved cards + hand.  This is vastly
    faster than re-partitioning all cards from scratch.
    """
    if not hand_cards:
        return [tuple(g) for g in floor_groups]

    if not floor_groups:
        pool = CardPool.from_cards(hand_cards)
        return solve(pool, deadline)

    # Sort groups by relevance (highest first); only keep score > 0
    scored = _relevance_scores(hand_cards, floor_groups)
    relevant = [i for i, score in sorted(scored, key=lambda x: -x[1])
                if score > 0]

    # Iterative deepening: dissolve k groups at a time
    total_tried = 0
    for k in range(len(relevant) + 1):
        for indices in combinations(relevant, k):
            if time.time() > deadline:
                return None
            total_tried += 1
            if total_tried > _MAX_ATTEMPTS:
                break

            # Pool = hand cards + dissolved groups' cards
            pool_cards = list(hand_cards)
            for i in indices:
                pool_cards.extend(floor_groups[i])

            pool = CardPool.from_cards(pool_cards)
            sub_deadline = min(deadline, time.time() + _SUB_TIMEOUT)
            result = solve(pool, sub_deadline)

            if result is not None:
                # Combine with unchanged floor groups
                full_result = list(result)
                idx_set = set(indices)
                for i, g in enumerate(floor_groups):
                    if i not in idx_set:
                        full_result.append(tuple(g))
                return full_result

        if total_tried > _MAX_ATTEMPTS or time.time() > deadline:
            break

    # Fallback: full solve (dissolve everything) with remaining time
    if time.time() < deadline:
        all_cards = list(hand_cards)
        for g in floor_groups:
            all_cards.extend(g)
        pool = CardPool.from_cards(all_cards)
        return solve(pool, deadline)

    return None


def solve_hand(hand, floor_groups, cross=None):
    """
    Given a player's hand, floor groups, and unincorporated cross cards,
    determine if the player can empty their hand.

    Uses incremental solving: keeps most floor groups intact and only
    re-partitions the minimum necessary cards.

    Cross cards may remain as singles — they are not required to be in
    valid groups.  The solver tries to include as many as possible,
    falling back to excluding them one-by-one.

    Returns (solvable, target_groups, remaining_cross) where
      target_groups  — the partition of placed cards into valid groups
      remaining_cross — cross cards left as singles (not in any group)
    """
    if cross is None:
        cross = []

    deadline = time.time() + _OVERALL_TIMEOUT

    # Try including as many cross cards as possible (0 excluded first)
    for n_exclude in range(len(cross) + 1):
        for excluded in combinations(range(len(cross)), n_exclude):
            if time.time() > deadline:
                break
            excluded_set = set(excluded)
            included = [cross[i] for i in range(len(cross))
                        if i not in excluded_set]

            result = _solve_incremental(hand + included, floor_groups, deadline)
            if result is not None:
                left = [cross[i] for i in excluded]
                return True, result, left

    return False, None, []


def verify_solution(all_cards, groups):
    """Verify that groups form a valid partition of all_cards."""
    for g in groups:
        if not is_valid_group(g):
            return False, f"Invalid group: {g}"

    group_counts = Counter()
    for g in groups:
        for c in g:
            group_counts[(c.rank, c.suit)] += 1

    card_counts = Counter()
    for c in all_cards:
        card_counts[(c.rank, c.suit)] += 1

    if group_counts != card_counts:
        return False, "Card counts don't match"

    return True, "Valid"
