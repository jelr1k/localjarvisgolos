class History:
    def __init__(self):
        self.items = []

    def add(self, item):
        self.items.append(item)

    def clear(self):
        self.items.clear()
