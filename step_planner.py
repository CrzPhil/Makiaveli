from collections import Counter
from card import Card, format_group


def _counter(cards):
    """Card list → Counter keyed by (rank, suit)."""
    c = Counter()
    for card in cards:
        c[(card.rank, card.suit)] += 1
    return c


def _cards_from_counter(counter):
    """Counter → sorted list of Card objects."""
    cards = [Card(r, s) for (r, s), n in counter.items() for _ in range(n)]
    return sorted(cards)


def plan_steps(floor_groups, target_groups, hand):
    """
    Compare initial floor state to the solver's target partition and produce
    human-readable steps describing how to get there.

    Returns a list of step description strings.
    """
    hand_ctr = _counter(hand)
    floor_ctrs = [_counter(g) for g in floor_groups]
    target_ctrs = [_counter(g) for g in target_groups]

    # --- Match target groups to floor groups (greedy, by highest overlap) ---
    pairs = []
    for ti, tc in enumerate(target_ctrs):
        for fi, fc in enumerate(floor_ctrs):
            overlap = sum((tc & fc).values())
            if overlap > 0:
                pairs.append((overlap, ti, fi))
    pairs.sort(reverse=True)

    match_t2f = {}   # target_idx → floor_idx
    used_floor = set()
    for overlap, ti, fi in pairs:
        if ti not in match_t2f and fi not in used_floor:
            match_t2f[ti] = fi
            used_floor.add(fi)

    # --- Figure out which floor cards were "released" (left their group) ---
    floor_staying = {}   # fi → Counter of cards staying in the matched target
    for ti, fi in match_t2f.items():
        floor_staying[fi] = target_ctrs[ti] & floor_ctrs[fi]

    released = Counter()          # total pool of cards freed from floor groups
    released_by_group = {}        # fi → Counter of freed cards
    for fi, fc in enumerate(floor_ctrs):
        staying = floor_staying.get(fi, Counter())
        freed = fc - staying
        released_by_group[fi] = freed
        released += freed

    # --- Generate steps ---
    steps = []
    remaining_hand = hand_ctr.copy()
    remaining_released = released.copy()

    for ti, target in enumerate(target_groups):
        tc = target_ctrs[ti]

        if ti in match_t2f:
            fi = match_t2f[ti]
            staying = floor_staying[fi]
            needed = tc - staying

            if not needed:
                continue  # group unchanged

            from_hand = needed & remaining_hand
            remaining_hand -= from_hand
            from_floor = needed - from_hand
            remaining_released -= from_floor

            parts = []
            if from_hand:
                cards_str = ', '.join(str(c) for c in _cards_from_counter(from_hand))
                parts.append(f"play {cards_str} from hand")
            if from_floor:
                cards_str = ', '.join(str(c) for c in _cards_from_counter(from_floor))
                # Try to identify source group(s)
                sources = _find_sources(from_floor, released_by_group)
                if sources:
                    src_desc = ', '.join(
                        f"{', '.join(str(c) for c in cs)} from group {fi}"
                        for fi, cs in sources.items()
                    )
                    parts.append(f"move {src_desc}")
                else:
                    parts.append(f"move {cards_str} from floor")

            action = ' + '.join(parts)
            old_str = format_group(list(floor_groups[fi]))
            new_str = format_group(list(target))
            steps.append(f"{action} → {old_str} becomes {new_str}")

        else:
            # Entirely new group
            from_hand = tc & remaining_hand
            remaining_hand -= from_hand
            from_floor = tc - from_hand
            remaining_released -= from_floor

            parts = []
            if from_hand:
                cards_str = ', '.join(str(c) for c in _cards_from_counter(from_hand))
                parts.append(f"{cards_str} from hand")
            if from_floor:
                sources = _find_sources(from_floor, released_by_group)
                if sources:
                    src_desc = ', '.join(
                        f"{', '.join(str(c) for c in cs)} from group {fi}"
                        for fi, cs in sources.items()
                    )
                    parts.append(src_desc)
                else:
                    cards_str = ', '.join(str(c) for c in _cards_from_counter(from_floor))
                    parts.append(f"{cards_str} from floor")

            source = ' + '.join(parts)
            new_str = format_group(list(target))
            steps.append(f"new group {new_str} ← {source}")

    return steps


def _find_sources(needed_ctr, released_by_group):
    """
    Given a Counter of cards needed from the floor, figure out which
    floor group each card came from.  Returns {floor_idx: [Card, ...]}.
    """
    result = {}
    remaining = needed_ctr.copy()

    for fi, freed in released_by_group.items():
        overlap = remaining & freed
        if overlap:
            result[fi] = _cards_from_counter(overlap)
            remaining -= overlap
            released_by_group[fi] -= overlap
        if not remaining:
            break

    return result if not remaining else {}
