from main import *

g = Game(4)
g.setup()

p = g.players[0]

print("Player hand before running")
p.show_hand()

print("Floor before running")
g.floor.show()

#for i in range(3):
#    p.hand.append(Card(int(input("value: ")), input("suit: ")))
#
#p.show_hand()

#actions = g.enumerate_sub_actions(p)
#sub_actions = g.generate_sub_action_sequences(actions)
#
#for i in range(1):
#    print(sub_actions[i])
#    if g.validate_and_apply_sub_action_sequence(p, sub_actions[i]):
#        print(sub_actions)
#        g.floor.show()
#
#
#print("Player hand after running")
#p.show_hand()
#
#print("Floor after running")
#g.floor.show()

for i in range(10):
    p.hand.append(g.deck.draw())

print("Player hand before running")
p.show_hand()

actions = g.enumerate_sub_actions(p)
sub_actions = g.generate_sub_action_sequences(actions, max_depth=4)

for i in range(100):
    val = g.validate_and_apply_sub_action_sequence(p, sub_actions[i])
    if val[0]:
        print("Valid sub_action_sequence!")
        print("sub actions:")
        print(val[1])
        print("floor:")
        g.floor.show()

print("Player hand after running")
p.show_hand()

print("Floor after running")
g.floor.show()


