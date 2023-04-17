from main import *

g = Game(4)
g.setup()

p = g.players[0]

print("Player hand before running")
p.show_hand()

print("Floor before running")
g.floor.show()

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
sub_actions = g.generate_sub_action_sequences(actions)

for i in range(1):
    print(sub_actions[i])
    if g.validate_and_apply_sub_action_sequence(p, sub_actions[i]):
        print(sub_actions[i])
        g.floor.show()
        print("GARABASFGSFGSD")

print("Player hand after running")
p.show_hand()

print("Floor after running")
g.floor.show()


