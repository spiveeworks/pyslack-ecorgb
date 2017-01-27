import re
from datetime import datetime
import random

#import requests
api = __import__('fake_api')
websocket = __import__('fake_websocket')

import idt

app_key = api.make_keys()['identity_theft']
slack = api.API(app_key)

users = {}
game = idt.GameWorld()

def find_user(player):
    for k, v in users.items():
        if v is player:
            return k

def yield_id_if(pred):
    def yield_func(game, *args, **kwargs):
        for pid in game.all_identities():
            if pred(pid, *args, **kwargs): yield pid
    return yield_func

@yield_id_if
def all_strangers(test_each, perspective):
    return test_each not in perspective.ids

def get_id_or_complain(channel, player, name):
    try:
        return player.per.names[name.lower()]
    except KeyError:
        pb_send(channel, "\"{name}\" is not the name of anyone you know.".format(name=name))

def complain_if_not(channel, player, id):
    if idt.find_player(game, id) is not player:
        pb_send(channel, "You are not *{name}*... yet.".format(name=player.per.ids[id]))
        return True
    return False

class Name:
    def __init__(self):
        self.names = 'Alice, Bob, Eve, Carol, Carlos, Charlie, \
Chuck, Craig, Dan, Dave, Erin, Eve, Faythe, Frank, Grace, Mallet, \
Mallory, Trudy, Oscar, Peggy, Pat, Victor, Vanna, Sybil, Trent, \
Walter, Wendy'.split(', ')
        self.used = []
        self.num = 0
    
    def pop(self):
        if not self.names:
            self.names = self.used
            self.used = []
            self.num += 1
        name = self.names.pop(0)#randrange(len(self.names)))
        self.used.append(name)
        return name + (' {}'.format(self.num + 1) if self.num else '')


def pb_send(channel, message):
    slack.post_as_bot(
        channel,
        message,
        'Pybot',
        ':godmode:'
    )


def PLAY_spawn(time, user, channel, **message):
    if any([channel == this_channel for this_user, this_channel in users]):
        pb_send(channel, "There is already a player associated with this channel/DM")
        return
    id = game.get_tnum()
    player = idt.Player(id, idt.Perspective(Name()))
    users[user, channel] = player
    game.players.append(player)
    name = player.per[id]
    pb_send(channel, "You call yourself {name}.".format(name=name))

def PLAY_abandon(time, user, channel, **message):
    if (user, channel) not in users:
        pb_send(channel, "End that which has not begun? Illogical.")
        return
    del users[user, channel]
    pb_send(channel, "This channel is now free. Use `PLAY spawn` to start as a new player!")

def MEET(time, user, channel, text, **message):
    if (user, channel) not in users: return
    player = users[user, channel]
    text = text[len('MEET as: '):]
    player_id = get_id_or_complain(channel, player, text)
    if player_id is None: return
    if complain_if_not(channel, player, player_id): return
    candidate_ids = list(all_strangers(game, player.per))
    idt.meet(game, time, player_id, random.choice(candidate_ids))
    
def CAP(time, user, channel, text, **message):
    if (user, channel) not in users: return
    player = users[user, channel]
    text = text[len('CAP '):].partition(', as: ')
    capping = get_id_or_complain(channel, player, text[2])
    capped = get_id_or_complain(channel, player, text[0])
    if capping is None or capped is None: return
    if complain_if_not(channel, player, capping): return
    idt.cap(game, time, capping, capped)
    
def TELL(time, user, channel, text, **message):
    if (user, channel) not in users: return
    player = users[user, channel]
    target_name, sep, text = text[len('TELL '):].partition(', as: ')
    tell_as_name, sep, text = text.partition(': ')
    target = get_id_or_complain(channel, player, target_name)
    tell_as = get_id_or_complain(channel, player, tell_as_name)
    if target is None or tell_as is None: return
    if complain_if_not(channel, player, tell_as): return
    target_p = idt.find_player(game, target)
    target_user = find_user(target_p)
    text = tell_as_name + ' (to ' + target_name + '): ' + text
    text = target_p.per.alias_up(*player.per.alias_down(text))
    if target_user: pb_send(target_user[1], text)
    
def ALIASES(time, user, channel, **message):
    if (user, channel) not in users: return
    player = users[user, channel]
    output = ['Your aliases:']
    for id in player.char.pids:
        output.append('    *' + player.per.ids[id] + '*')
    if player.char.hostage:
        output.append('Your hostage\'s aliases:')
        for id in player.char.hostage.pids:
            output.append('    *' + player.per.ids[id] + '*')
    output.append
    names_left = ['    *' + name + '*' for id, name in player.per.ids.items() if id not in player.char]
    if names_left:
        output.append('Your peers:')
        output.extend(names_left)
    pb_send(channel, '\n'.join(output))
    
    

responses = {}
functions = {
    #(r'pb .+', pb_commands)
    (r'PLAY spawn', PLAY_spawn),
    (r'PLAY abandon', PLAY_abandon),
    (r'MEET as: .+', MEET),
    (r'CAP .+, as: .+', CAP),
    (r'TELL .+, as: .+', TELL),
    (r'ALIASES', ALIASES),
}

output_format = {
    'bleed_begin': [
        ('hostage', "Your alias *{{hostage_id}}* was capped by *{{taker_id}}*! You will bleed out in ten minutes.", ('hostage_id', 'taker_id')),
        ('taker', "You have taken *{{hostage_id}}* hostage! They will bleed out in ten minutes.", ('hostage_id',)),
    ],
    'bleed_end': [
        ('hostage', "You bled out! Your alias *{{hostage_id}}* was capped by *{{taker_id}}*", ('hostage_id','taker_id')),
        ('taker', "Your hostage, *{{hostage_id}}*, bled out!", ('hostage_id',)),
    ],
    'meet': [
        ('active', "You meet someone and call them *{{passive_id}}*.", ('passive_id',)),
        ('passive', "As *{{passive_id}}*, you have been met by *{{active_id}}*.", ('active_id', 'passive_id')),
    ],
}

w = websocket.WebSocket()

wss_url = api.get_url(app_key)
init_time = datetime.now()
w.connect(wss_url)

while True:
    n = w.next().replace('true', 'True').replace('false', 'False').replace('none', 'None')
    print(n)
    n = eval(n)
    time_now = datetime.fromtimestamp(float(n.pop('ts'))) if 'ts' in n else None
    if time_now:
        game.update(time_now)
    if all([
        n['type'] == 'message',
        n['hidden'] if 'hidden' in n else True,  # why is this here
        'bot_id' not in n,
        time_now is not None
    ]):
        for key, func in functions:
            if re.match(key, n['text']):
                func(time_now, **n)
                continue
       # for response in responses:
       #     if re.match(response, n['text']):
       #         pb_send(n['channel'], responses[response])
       #         continue
    for msg in game.flush_messages():
        for player_arg, raw_output, id_args in output_format[msg.pop('type')]:
            player = msg[player_arg]
            if player not in users.values(): continue
            user, channel = find_user(player)
            basic_output = raw_output.format(**msg)
            id_assocs = {arg: msg[arg] for arg in id_args}
            personal_output = player.per.alias_up(basic_output, id_assocs)
            pb_send(channel, personal_output)
    

