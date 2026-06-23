from openai import AsyncOpenAI

from app.interfaces.contracts import LLMProvider


class MockLLMProvider(LLMProvider):
    async def complete(self, prompt: str, *, system: str | None = None) -> str:
        preview = prompt.strip().replace("\n", " ")[:160]
        return f"基于课程资料与上下文生成：{preview}"


class OpenAICompatibleLLMProvider(LLMProvider):
    """Doubao / Volcengine ARK and other OpenAI-compatible APIs."""

    def __init__(self, *, base_url: str, api_key: str, model: str):
        self.model = model
        self.client = AsyncOpenAI(base_url=base_url, api_key=api_key)

    async def complete(self, prompt: str, *, system: str | None = None) -> str:
        messages: list[dict[str, str]] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=0.7,
        )
        content = response.choices[0].message.content
        return content.strip() if content else ""


def build_llm_provider(config: dict) -> LLMProvider:
    provider = config.get("provider", "mock")
    if provider == "openai_compatible" and config.get("api_key"):
        return OpenAICompatibleLLMProvider(
            base_url=config["base_url"],
            api_key=config["api_key"],
            model=config["model"],
        )
    return MockLLMProvider()


class ProviderRegistry:
    def __init__(self, providers: dict[str, LLMProvider], default: str = "mock"):
        self._providers = providers
        self._default = default

    def get(self, name: str | None = None) -> LLMProvider:
        return self._providers.get(name or self._default, self._providers["mock"])
