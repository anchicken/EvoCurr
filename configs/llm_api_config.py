class LLMModelConfig:
    def __init__(self, api_key, base_url, model_name):
        self.api_key = api_key
        self.base_url = base_url
        self.model_name = model_name

    def __repr__(self):
        masked_api_key = self.api_key[:6] + "*" * (len(self.api_key) - 6)
        return f"LLMModelConfig(api_key='{masked_api_key}', base_url='{self.base_url}', model_name = '{self.model_name}')"


class LLMAPIConfig:
    MODELS = {
        "deepseek-v3.2": LLMModelConfig(
            api_key="your_api_key",
            base_url="api_base_url",
            model_name="api_name"
        )
    }
    """
    test
    """

    TASK_MODELS = {
        "planner": "deepseek-v3.2",
        "coder": "deepseek-v3.2",
        "designer": "deepseek-v3.2"
    }

    @classmethod
    def get_model_config(cls, model_name):
        return cls.MODELS.get(model_name)

    @classmethod
    def get_task_model(cls, task):
        model_name = cls.TASK_MODELS.get(task)
        return cls.get_model_config(model_name)

    @classmethod
    def get_model_dict(cls):
        return cls.TASK_MODELS


if __name__ == '__main__':
    config = LLMAPIConfig()
    print("Model config for gpt-4o:")
    print(config.MODELS[config.TASK_MODELS["planner"]].model_name)
    print(config.get_model_config("gpt-4o"))
    print("\nModel config for planner task:")
    print(config.get_task_model("summarizer"))