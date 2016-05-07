

class Char:  # more like a disguise set than an entire character
    def __init__(self, pid):
        self.pids = {pid}
        self.hostage = None
        self.hostage_bleed = None

    def __contains__(self, pid):
        return pid in self.pids or self.hostage and pid in self.hostage.pids
    
