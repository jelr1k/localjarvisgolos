class ModelService:
    def __init__(self, provider):
        self.provider = provider

    def get_models(self):
        return self.provider.list_models()
