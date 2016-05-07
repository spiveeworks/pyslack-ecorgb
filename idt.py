anon = __import__ ('idt_anon')
import heapq
from datetime import timedelta

class GameWorld:
    def __init__(game):
        game.players = []
        game.queue = []
        game.next_tnum = 0
        game.msg = []
    
    def get_tnum(game):
        game.next_tnum += 1
        return game.next_tnum - 1
    
    def queue_event(game, time, event):
        heapq.heappush(
            game.queue, 
            (time, game.get_tnum(), event)
        )
    
    def update(game, time):
        while game.queue and game.queue[0][0] <= time:
            event_time, tnum, event = heapq.heappop(game.queue)
            event.execute(game, event_time)
    
    def post(game, msg):
        game.msg.append(msg)
    
    def flush_messages(game):
        ret = game.msg
        game.msg = []
        return ret
    
    def all_identities(game):
        for player in game.players:
            for pid in player.char.pids:
                yield pid
            if player.char.hostage:
                for pid in player.char.hostage.pids:
                    yield pid
                

class Perspective:
    invalid_separator = ''.join([chr(x + ord('A')) + chr(x + ord('a')) for x in range(26)]) + ''.join([str(x) for x in range(10)])
    valid_name = ' -' + invalid_separator
    
    def __init__(self, name_gen):
        self.ids = {}
        self.names = {}
        self.name_gen = name_gen
    
    def __getitem__(self, id):
        if id not in self.ids:
            name = self.name_gen.pop()
            self.ids[id] = name
            self.names[name.lower()] = id
        return self.ids[id]
    
    def alias_down(perspective, text):
        text = text.replace('{', '{{').replace('}', '}}')  # joys of str.format
        otext = ''
        omap = {}
        is_token = True
        while text:
            found = False
            if is_token and text[0] in Perspective.valid_name:
                for name, id in perspective.names.items():
                    if (
                        len(text) >= len(name) 
                        and text[:len(name)].lower() == name.lower() 
                        and (
                            len(text) == len(name) 
                            or text[len(name)] not in Perspective.invalid_separator
                        )
                    ):
                        otext += name.join('{}')
                        omap[name] = id
                        text = text[len(name):]
                        found = True
                        break
            if not found:
                is_token = text[0] not in Perspective.invalid_separator
                otext += text[0]
                text = text[1:]
        return otext, omap
    
    def alias_up(perspective, text, map):
        map = {name: perspective[id] for name, id in map.items()}
        return text.format(**map)
    

class Player:
    def __init__(self, pid, per):
        self.char = anon.Char(pid)
        self.per = per
    
    

class BleedEvent:
    def __init__(e, capped, capping, capped_id, capping_id):  # argument order?
        e.capped = capped
        e.capped_id = capped_id
        e.capping = capping
        e.capping_id = capping_id
        e.abort = False
        capping.char.hostage_bleed = e
        
    def execute(e, game, time):
        if e.abort: return
        e.capping.char.pids.update(e.capped.char.pids)
        e.capping.char.hostage = None
        e.capping.char.hostage_bleed = None
        game.post({
            'type': 'bleed_end',
            'hostage': e.capped,
            'hostage_id': e.capped_id,
            'taker': e.capping,
            'taker_id': e.capping_id,
        })
        

def find_player(game, pid):
    for player in game.players:
        if pid in player.char:
            return player


def cap(game, time, capping_id, capped_id):
    capping_p = find_player(game, capping_id)
    capping = capping_p.char
    capped_p = find_player(game, capped_id)
    capped = capped_p.char
    if capping.hostage: return
    if capped.hostage: capped.release_hostage()
    capping.hostage = capped
    del game.players[game.players.index(capped_p)]
    game.queue_event(time + timedelta(seconds=3), BleedEvent(capped_p, capping_p, capped_id, capping_id))
    game.post({
        'type': 'bleed_begin',
        'hostage': capped_p,
        'hostage_id': capped_id,
        'taker': capping_p,
        'taker_id': capping_id,
    })
    
def meet(game, time, active_id, passive_id):
    game.post({
        'type': 'meet',
        'active': find_player(game, active_id),
        'active_id': active_id,
        'passive': find_player(game, passive_id),
        'passive_id': passive_id,
    })

