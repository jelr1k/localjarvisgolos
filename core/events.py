from PySide6.QtCore import QObject, Signal

class EventBus(QObject):
    message_received = Signal(object)
    generation_finished = Signal(object)
    error = Signal(str)
