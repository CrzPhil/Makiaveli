import random
import itertools

class Card:
    values = list(range(1, 14))
    suits = ['H', 'C', 'S', 'D']

    def __init__(self, value: int, suit: chr):
        self.special_values = {1: 'A', 11: 'J', 12: 'Q', 13: 'K'}
        self._value = value
        self._suit = suit

    def __str__(self):
        if self.value in self.special_values.keys():
            return f'{self.special_values[self.value]}{self._suit}'
        return f"{self._value}{self._suit}"

    def __repr__(self):
        if self.value in self.special_values.keys():
            return f'{self.special_values[self.value]}{self._suit}'
        return f"{self._value}{self._suit}"

    @property
    def suit(self):
        return self._suit

    @property
    def value(self):
        return self._value


class Deck:
    def __init__(self):
        self._cards = [Card(Card.values[i], suit) for i in range(13) for suit in Card.suits] * 2

    @property
    def cards(self):
        return self._cards

    def shuffle(self):
        random.shuffle(self._cards)

    def count(self):
        return len(self._cards)

    def draw(self):
        if self.count() > 0:
            return self._cards.pop()
        else:
            print("Tried to draw from an empty deck.")


class Player:
    def __init__(self, name):
        self.name = name
        self.hand = []

    def __str__(self):
        hand_str = ", ".join([str(card) for card in self.hand])
        return f"{self.name}: {hand_str}"

    def play(self):
        pass

    def show_hand(self):
        return self.__str__()

    def remove_card_from_hand(self, card):
        """
        Pop a card from the player's hand.

        :return: 1 -> Card doesn't exist.
        :return: None -> All good.
        """
        for index, existing_card in enumerate(self.hand):
            if existing_card.suit == card.suit and existing_card.value == card.value:
                self.hand.pop(index)
                return

        return 1

    def remove_cards_from_hand(self, combination):
        """
        Pop multiple cards from the player's hand.

        :return: 1 -> One or more cards didn't exist.
        :return: None -> All good.
        """
        for card in combination:
            val = self.remove_card_from_hand(card)
            if val:
                return 1


class Floor:
    def __init__(self, deck):
        """
        Initialize floor using a deck.

        Four cards are drawn and marked as the Anchor cards.
        self.modifications ->   A dictionary marking the index of a combination and whether it has been modified or not.
                                Using this we can skip over non-modified combinations since they will already have been validated previously.
        """
        # 4 initially anchored  cards
        self.floor = [[deck.draw()] for i in range(4)]
        # Index of achors and if they have been modified
        self.modifications = {0: False,
                              1: False,
                              2: False,
                              3: False}

    def show(self):
        """
        Visualise the floor.
        """
        for i, combination in enumerate(self.floor):
            print(f"{i + 1}: {', '.join(map(str, combination))}")

    def get_floor(self):
        """
        Save the state before "casino". Can be restored if validation checks fail afterwards
        """
        return (self.floor, self.modifications)

    def restore_floor(self, floor, modifications):
        """
        Restore saved state after "casino" fails.
        """
        self.floor = floor
        self.modifications = modifications

    def add_card_to_combination(self, card: Card, combination_index: int):
        """
        Add a card from the player's hand to an existing combination.

        :return: 0 -> Invalid combination_index
        :return: None -> All good, but not validated yet.
        """
        if 0 > combination_index or combination_index > len(self.floor):
            print("Debug: Tried to add_card_to_combination() where combination_index is not in valid range.")
            return 0

        self.floor[combination_index].append(card)
        self.modifications[combination_index] = True

    def create_new_combination(self, combination: list):
        """
        Play a new combination on the floor. Can be partial, since a card may be moved to it afterwards.
        """
        self.floor.append(combination)
        self.modifications[len(self.floor)] = True

    def move(self, source_combination: int, card: Card, destination_combination: int):
        """
        Move a card from one combination to another.

        :return: 0 -> Invalid indeces
        :return: 1 -> Card not found in the source_combination
        :return: None -> All good, but not validated yet.
        """
        if (0 > source_combination or source_combination > len(self.floor)) or (0 > destination_combination or destination_combination > len(self.floor)):
            return 0

        card_index = None
        for index, existing_card in enumerate(self.floor[source_combination]):
            if existing_card.suit == card.suit and existing_card.value == card.value:
                card_index = index
                break

        if card_index is None:
            return 1

        tmp_card = self.floor[source_combination].pop(card_index)
        self.floor[destination_combination].append(tmp_card)

        self.modifications[source_combination] = True
        self.modifications[destination_combination] = True

    def play_is_valid(self, play: list):
        """
        Check a user's play to see whether it is valid
        """
        if len(play) >= 3:
            # Check if all cards' suit is the same
            if len(set([card.suit for card in play])) == 1:
                if self.is_sorted(lst=[card.value for card in play], order='ascending'):
                    return True

            return False

    def check_combination(self, combination: list):
        """
        Check a combination's validity.
        """
        if len(combination) < 3:
            return False

        # Sort cards by value, keeping suit information
        sorted_cards = sorted(combination, key=lambda x: (x.value, x.suit))

        # Check if cards have the same value with different suits
        same_value = all(card.value == sorted_cards[0].value for card in sorted_cards)
        unique_suits = len(set(card.suit for card in sorted_cards)) == len(sorted_cards)

        if same_value and unique_suits:
            return True

        # Check if cards are in a consecutive sequence with the same suit
        same_suit = all(card.suit == sorted_cards[0].suit for card in sorted_cards)
        consecutive_values = all(sorted_cards[i].value == sorted_cards[i - 1].value + 1 for i in range(1, len(sorted_cards)))

        if same_suit and consecutive_values:
            return True

        return False

    def is_valid(self):
        """
        Run after a play to verify that the floor is in a valid state before proceeding.
        """
        modified_combinations = [combination for combination, modified in self.modifications.items() if modified]

        if len(modified_combinations) == 0:
            print("Debug: nothing was modified.")
            return True

        # There are always at least 4 anchored cards on the floor
        if len(self.floor) < 4:
            return False
        
        # Check if all combinations in the rest of the floor (excluding anchors) contain >=3 cards
        if any(len(self.floor[combination_index]) < 3 for combination_index in modified_combinations):
            return False

        # Check combinations
        if any(not self.check_combination(self.floor[combination_index]) for combination_index in modified_combinations):
            return False

        return True


class Game:
    def __init__(self, player_count):
        self.deck = Deck()
        self.floor = None
        self.players = [Player(i) for i in range(1, player_count+1)]
        self.current_player_index = 0
        self.game_over = False

    def setup(self):
        """
        Shuffle the deck and deal five cards to each player, as well as four anchored cards
        """
        self.deck.shuffle()

        # Deal cards
        for player in self.players:
            for i in range(5):
                player.hand.append(self.deck.draw())
        
        # Initialize floor and deal anchored cards
        self.floor = Floor(self.deck)

    def enumerate_sub_actions(self, player):
        """
        Find all possible actions a player can do.

        Checks for combinations on-hand, checks for valid combinations on the floor, checks for single-card laydowns. 
        :return: array of sub_actions a player can perform.
        """
        sub_actions = []

        # Enumerate possible combinations in player's hand
        for length in range(3, len(player.hand) + 1):
            for combination in itertools.combinations(player.hand, length):
                if self.floor.check_combination(list(combination)):
                    sub_actions.append(('create_new_combination', combination))

        # Enumerate possible cards to add to existing combinations
        for card in player.hand:
            for i in range(len(self.floor.floor)):
                sub_actions.append(('add_card_to_combination', card, i))
    
        # Enumerate possible card moves between combinations
        for i, source_combination in enumerate(self.floor.floor):
            for j, destination_combination in enumerate(self.floor.floor):
                if i != j:
                    for card in source_combination:
                        sub_actions.append(('move', i, card, j))

        return sub_actions

    def generate_sub_action_sequences(self, sub_actions, max_depth=3):
        """
        Create an array of sequences of sub_actionsself.
        """
        return list(itertools.product(sub_actions, repeat=max_depth))

    def validate_and_apply_sub_action_sequence(self, player, sub_action_sequence):
        # Save initial game state
        initial_floor, initial_modifications = self.floor.get_floor()
        initial_hand = player.hand.copy()
    
        for action, *args in sub_action_sequence:
            if action == 'create_new_combination':
                combination = list(args[0])
                player.remove_cards_from_hand(combination)
                self.floor.create_new_combination(combination)
    
            elif action == 'add_card_to_combination':
                card, combination_index = args
                player.remove_card_from_hand(card)
                self.floor.add_card_to_combination(card, combination_index)
    
            elif action == 'move':
                source_combination, card, destination_combination = args
                self.floor.move(source_combination, card, destination_combination)
    
        is_valid = self.floor.is_valid()
    
        # Restore initial game state
        self.floor.restore_floor(initial_floor, initial_modifications)
        player.hand = initial_hand
    
        return is_valid

    def end_turn(self):
        """
        Finish turn and move to next player.
        """
        self.current_player_index = ((self.current_player_index + 1) % (len(self.players) + 1)) + 1 

    def integrity_check(self):
        """
        Check if any new cards have appeared or have been removed.
        """
        card_count = 0
        for combination in self.floor.floor:
            card_count += len(combination)
        for player in self.players:
            card_count += len(player.hand)
        
        return card_count == 104

    def play(self):
        """
        Main function starting the game cycle.
        To be called *after* setup() function.
        """
        while not self.game_over:
            current_player = self.players[self.current_player_index]

            # Show floor and player hand
            self.floor.show()
            self.player.show_hand()

            # Choose action (draw or play)

            # If play, save the floor's state
            floor, modifications = self.floor.get_floor()

            self.end_turn()

