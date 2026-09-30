class StatisticsService:
    def __init__(self):
        self.history = []
        self.whisper_history = []

    def add(self, stats):
        self.history.append(stats)

    @property
    def latest(self):
        return self.history[-1] if self.history else None
