#!/usr/bin/env python3
"""Tests for the Makiaveli solver."""

import unittest
from card import Card, parse_card, format_group
from solver import (
    CardPool, is_valid_set, is_valid_run, is_valid_group,
    solve, solve_hand, verify_solution,
    _sets_containing, _runs_containing,
)


class TestCard(unittest.TestCase):
    def test_parse_basic(self):
        self.assertEqual(parse_card('7S'), Card(7, 'S'))
        self.assertEqual(parse_card('AH'), Card(1, 'H'))
        self.assertEqual(parse_card('KD'), Card(13, 'D'))
        self.assertEqual(parse_card('10C'), Card(10, 'C'))
        self.assertEqual(parse_card('jh'), Card(11, 'H'))

    def test_str(self):
        self.assertEqual(str(Card(1, 'S')), 'A♠')
        self.assertEqual(str(Card(13, 'D')), 'K♦')
        self.assertEqual(str(Card(10, 'C')), '10♣')
        self.assertEqual(str(Card(7, 'H')), '7♥')


class TestValidation(unittest.TestCase):
    def test_valid_set(self):
        self.assertTrue(is_valid_set([Card(7, 'S'), Card(7, 'H'), Card(7, 'D')]))
        self.assertTrue(is_valid_set([Card(7, 'S'), Card(7, 'H'), Card(7, 'D'), Card(7, 'C')]))

    def test_invalid_set_too_small(self):
        self.assertFalse(is_valid_set([Card(7, 'S'), Card(7, 'H')]))

    def test_invalid_set_same_suit(self):
        self.assertFalse(is_valid_set([Card(7, 'S'), Card(7, 'S'), Card(7, 'H')]))

    def test_invalid_set_different_ranks(self):
        self.assertFalse(is_valid_set([Card(7, 'S'), Card(8, 'H'), Card(7, 'D')]))

    def test_valid_run(self):
        self.assertTrue(is_valid_run([Card(5, 'C'), Card(6, 'C'), Card(7, 'C')]))
        self.assertTrue(is_valid_run([Card(5, 'C'), Card(6, 'C'), Card(7, 'C'), Card(8, 'C')]))

    def test_valid_run_ace_low(self):
        self.assertTrue(is_valid_run([Card(1, 'S'), Card(2, 'S'), Card(3, 'S')]))

    def test_valid_run_ace_high(self):
        self.assertTrue(is_valid_run([Card(12, 'S'), Card(13, 'S'), Card(1, 'S')]))
        self.assertTrue(is_valid_run([Card(11, 'S'), Card(12, 'S'), Card(13, 'S'), Card(1, 'S')]))

    def test_invalid_run_wrap(self):
        # K, A, 2 — wrapping not allowed
        self.assertFalse(is_valid_run([Card(13, 'S'), Card(1, 'S'), Card(2, 'S')]))

    def test_invalid_run_mixed_suits(self):
        self.assertFalse(is_valid_run([Card(5, 'C'), Card(6, 'H'), Card(7, 'C')]))

    def test_invalid_run_duplicates(self):
        self.assertFalse(is_valid_run([Card(5, 'C'), Card(5, 'C'), Card(6, 'C')]))

    def test_invalid_run_too_small(self):
        self.assertFalse(is_valid_run([Card(5, 'C'), Card(6, 'C')]))


class TestCardPool(unittest.TestCase):
    def test_basic(self):
        pool = CardPool()
        pool.add(Card(7, 'S'))
        pool.add(Card(7, 'S'))
        self.assertEqual(pool.get(7, 'S'), 2)
        self.assertEqual(pool.total, 2)

        pool.remove(Card(7, 'S'))
        self.assertEqual(pool.get(7, 'S'), 1)
        self.assertEqual(pool.total, 1)

    def test_from_cards(self):
        cards = [Card(7, 'S'), Card(7, 'H'), Card(7, 'D')]
        pool = CardPool.from_cards(cards)
        self.assertEqual(pool.total, 3)
        self.assertEqual(pool.get(7, 'S'), 1)
        self.assertEqual(pool.get(7, 'C'), 0)


class TestEnumeration(unittest.TestCase):
    def test_sets(self):
        pool = CardPool.from_cards([Card(7, 'S'), Card(7, 'H'), Card(7, 'D'), Card(7, 'C')])
        sets = _sets_containing(7, 'S', pool)
        # Should have C(3,2) + C(3,3) = 3 + 1 = 4 sets
        self.assertEqual(len(sets), 4)
        for s in sets:
            self.assertTrue(is_valid_set(s))
            self.assertIn(Card(7, 'S'), s)

    def test_runs_normal(self):
        pool = CardPool.from_cards([Card(5, 'C'), Card(6, 'C'), Card(7, 'C'), Card(8, 'C')])
        runs = _runs_containing(6, 'C', pool)
        # Runs containing 6C: [5,6,7], [5,6,7,8], [6,7,8]
        self.assertEqual(len(runs), 3)
        for r in runs:
            self.assertTrue(is_valid_run(r))

    def test_runs_ace_high(self):
        pool = CardPool.from_cards([Card(12, 'S'), Card(13, 'S'), Card(1, 'S')])
        runs = _runs_containing(1, 'S', pool)
        self.assertEqual(len(runs), 1)
        self.assertTrue(is_valid_run(runs[0]))
        self.assertEqual(len(runs[0]), 3)

    def test_runs_ace_low(self):
        pool = CardPool.from_cards([Card(1, 'S'), Card(2, 'S'), Card(3, 'S')])
        runs = _runs_containing(1, 'S', pool)
        self.assertEqual(len(runs), 1)
        self.assertTrue(is_valid_run(runs[0]))


class TestSolver(unittest.TestCase):
    def test_simple_run(self):
        pool = CardPool.from_cards([Card(3, 'S'), Card(4, 'S'), Card(5, 'S')])
        result = solve(pool)
        self.assertIsNotNone(result)
        self.assertEqual(len(result), 1)

    def test_simple_set(self):
        pool = CardPool.from_cards([Card(7, 'S'), Card(7, 'H'), Card(7, 'D')])
        result = solve(pool)
        self.assertIsNotNone(result)
        self.assertEqual(len(result), 1)

    def test_two_groups(self):
        cards = [Card(7, 'S'), Card(7, 'H'), Card(7, 'D'),
                 Card(5, 'C'), Card(6, 'C'), Card(7, 'C')]
        pool = CardPool.from_cards(cards)
        result = solve(pool)
        self.assertIsNotNone(result)
        self.assertEqual(len(result), 2)
        valid, _ = verify_solution(cards, result)
        self.assertTrue(valid)

    def test_impossible_two_cards(self):
        pool = CardPool.from_cards([Card(7, 'S'), Card(8, 'H')])
        result = solve(pool)
        self.assertIsNone(result)

    def test_impossible_no_valid_groups(self):
        # 3 cards, all different suits AND ranks — can't form set or run
        pool = CardPool.from_cards([Card(2, 'S'), Card(5, 'H'), Card(9, 'D')])
        result = solve(pool)
        self.assertIsNone(result)

    def test_backtracking_needed(self):
        # 7S can go into a set or a run — only one choice works
        cards = [Card(7, 'S'), Card(7, 'H'), Card(7, 'D'),
                 Card(8, 'S'), Card(9, 'S')]
        pool = CardPool.from_cards(cards)
        # Only solution: run [7S,8S,9S] + can't form set [7H,7D] (too small)
        # Actually: [7S,8S,9S] leaves [7H,7D] — only 2, impossible
        # So need: set [7S,7H,7D] + can't form group from [8S,9S] — impossible
        # Wait, this IS impossible
        result = solve(pool)
        self.assertIsNone(result)

    def test_backtracking_with_solution(self):
        # 7S can go into a set or a run, but only run works
        cards = [Card(7, 'S'), Card(7, 'H'), Card(7, 'D'), Card(7, 'C'),
                 Card(8, 'S'), Card(9, 'S')]
        pool = CardPool.from_cards(cards)
        # Solution: run [7S,8S,9S] + set [7H,7D,7C]
        result = solve(pool)
        self.assertIsNotNone(result)
        self.assertEqual(len(result), 2)
        valid, _ = verify_solution(cards, result)
        self.assertTrue(valid)

    def test_ace_high_run(self):
        pool = CardPool.from_cards([Card(12, 'S'), Card(13, 'S'), Card(1, 'S')])
        result = solve(pool)
        self.assertIsNotNone(result)
        self.assertEqual(len(result), 1)

    def test_ace_low_run(self):
        pool = CardPool.from_cards([Card(1, 'S'), Card(2, 'S'), Card(3, 'S')])
        result = solve(pool)
        self.assertIsNotNone(result)
        self.assertEqual(len(result), 1)

    def test_two_deck_duplicates(self):
        # Two copies of 7S, 7H + one 7D, 7C
        cards = [Card(7, 'S'), Card(7, 'S'), Card(7, 'H'), Card(7, 'H'),
                 Card(7, 'D'), Card(7, 'C')]
        pool = CardPool.from_cards(cards)
        # Solution: set [7S,7H,7D] + set [7S,7H,7C]
        result = solve(pool)
        self.assertIsNotNone(result)
        self.assertEqual(len(result), 2)
        valid, _ = verify_solution(cards, result)
        self.assertTrue(valid)


class TestSolveHand(unittest.TestCase):
    def test_extend_cross(self):
        hand = [Card(3, 'S'), Card(4, 'S')]
        floor = [[Card(2, 'S')]]
        solvable, groups, remaining = solve_hand(hand, floor)
        self.assertTrue(solvable)

    def test_with_rearrangement(self):
        hand = [Card(7, 'D')]
        floor = [[Card(7, 'S'), Card(7, 'H'), Card(7, 'C')],
                 [Card(8, 'C'), Card(9, 'C'), Card(10, 'C')]]
        solvable, groups, remaining = solve_hand(hand, floor)
        self.assertTrue(solvable)

    def test_impossible(self):
        hand = [Card(2, 'H')]
        floor = [[Card(7, 'S'), Card(7, 'H'), Card(7, 'D')]]
        solvable, groups, remaining = solve_hand(hand, floor)
        self.assertFalse(solvable)

    def test_complex_rearrangement(self):
        # Need to split a floor group and recombine
        hand = [Card(8, 'S'), Card(9, 'S')]
        floor = [[Card(5, 'S'), Card(6, 'S'), Card(7, 'S')],
                 [Card(7, 'H'), Card(7, 'D'), Card(7, 'C')]]
        solvable, groups, remaining = solve_hand(hand, floor)
        # Solution: [5S,6S,7S,8S,9S] + [7H,7D,7C]
        self.assertTrue(solvable)
        all_cards = list(hand)
        for g in floor:
            all_cards.extend(g)
        valid, _ = verify_solution(all_cards, groups)
        self.assertTrue(valid)


class TestCrossCards(unittest.TestCase):
    def test_cross_can_stay_as_singles(self):
        """Cross cards that can't be placed should remain as singles."""
        hand = [Card(3, 'S'), Card(4, 'S')]
        floor = [[Card(2, 'S'), Card(3, 'S'), Card(4, 'S'), Card(5, 'S')]]
        cross = [Card(8, 'H')]  # can't go anywhere
        solvable, groups, remaining = solve_hand(hand, floor, cross)
        self.assertTrue(solvable)
        self.assertEqual(remaining, [Card(8, 'H')])

    def test_cross_incorporated_when_possible(self):
        """Cross cards should be used if they fit."""
        hand = [Card(3, 'S'), Card(4, 'S')]
        floor = []
        cross = [Card(2, 'S')]  # can join the run
        solvable, groups, remaining = solve_hand(hand, floor, cross)
        self.assertTrue(solvable)
        self.assertEqual(remaining, [])  # cross card was used

    def test_user_reported_case(self):
        """The exact case from the bug report — cross A♠, 3♦, 3♦, Q♥."""
        hand = [Card(3, 'S'), Card(5, 'S'), Card(1, 'D'),
                Card(13, 'D'), Card(4, 'C'), Card(8, 'C')]
        cross = [Card(1, 'S'), Card(3, 'D'), Card(3, 'D'), Card(12, 'H')]
        floor = [
            [Card(1,'S'),Card(2,'S'),Card(3,'S'),Card(4,'S'),
             Card(5,'S'),Card(6,'S'),Card(7,'S')],
            [Card(4,'C'),Card(4,'D'),Card(4,'H'),Card(4,'S')],
            [Card(12,'C'),Card(12,'D'),Card(12,'H')],
            [Card(9,'S'),Card(10,'S'),Card(11,'S'),Card(12,'S')],
            [Card(5,'C'),Card(6,'C'),Card(7,'C')],
        ]
        solvable, groups, remaining = solve_hand(hand, floor, cross)
        self.assertTrue(solvable)
        # All 4 cross cards should remain as singles
        self.assertEqual(len(remaining), 4)
        # All hand cards must be placed
        all_placed = list(hand)
        for g in floor:
            all_placed.extend(g)
        for c in cross:
            if c not in remaining:
                all_placed.append(c)
        valid, _ = verify_solution(all_placed, groups)
        self.assertTrue(valid)

    def test_multiple_cross_some_used(self):
        """Some cross cards get incorporated, others stay."""
        hand = [Card(3, 'S'), Card(4, 'S')]
        floor = []
        cross = [Card(2, 'S'), Card(9, 'H')]
        # 2S joins the run [2S,3S,4S], 9H can't go anywhere
        solvable, groups, remaining = solve_hand(hand, floor, cross)
        self.assertTrue(solvable)
        self.assertEqual(remaining, [Card(9, 'H')])


if __name__ == '__main__':
    unittest.main()
