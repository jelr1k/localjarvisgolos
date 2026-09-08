from abc import ABC, abstractmethod

class LLMProvider(ABC):
    @abstractmethod
    def list_models(self):
        raise NotImplementedError

    @abstractmethod
    def stream_chat(self, request):
        raise NotImplementedError
