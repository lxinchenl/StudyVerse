from openai import AsyncOpenAI

from app.interfaces.contracts import LLMProvider

WEB_SEARCH_MODEL_PREFIXES = ("deepseek-v4-pro",)


class MockLLMProvider(LLMProvider):
    async def complete(self, prompt: str, *, system: str | None = None) -> str:
        preview = prompt.strip().replace("\n", " ")[:160]
        return f"基于课程资料与上下文生成：{preview}"


class OpenAICompatibleLLMProvider(LLMProvider):
    """Doubao / Volcengine ARK and other OpenAI-compatible APIs."""

    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        model: str,
        use_responses_api: bool = False,
    ):
        self.model = model
        self.use_responses_api = use_responses_api
        self.client = AsyncOpenAI(base_url=base_url.rstrip("/"), api_key=api_key)

    def _uses_web_search_responses_api(self) -> bool:
        # Web search Responses tool is Volcengine/Doubao-specific; only when responses mode is on.
        return self.use_responses_api and any(
            self.model.startswith(prefix) for prefix in WEB_SEARCH_MODEL_PREFIXES
        )

    async def complete(self, prompt: str, *, system: str | None = None) -> str:
        if self.use_responses_api or self._uses_web_search_responses_api():
            return await self._complete_via_responses(
                prompt,
                system=system,
                with_web_search=self._uses_web_search_responses_api(),
            )

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

    async def _complete_via_responses(
        self,
        prompt: str,
        *,
        system: str | None = None,
        with_web_search: bool = False,
    ) -> str:
        input_messages: list[dict[str, str]] = []
        if system:
            input_messages.append({"role": "system", "content": system})
        input_messages.append({"role": "user", "content": prompt})
        kwargs: dict = {
            "model": self.model,
            "input": input_messages,
        }
        if with_web_search:
            kwargs["tools"] = [{"type": "web_search", "max_keyword": 2}]
        response = await self.client.responses.create(**kwargs)
        text = getattr(response, "output_text", None) or ""
        return text.strip()


def build_llm_provider(config: dict) -> LLMProvider:
    provider = config.get("provider", "mock")
    if provider == "openai_compatible" and config.get("api_key"):
        return OpenAICompatibleLLMProvider(
            base_url=str(config.get("base_url") or ""),
            api_key=str(config["api_key"]),
            model=str(config.get("model") or ""),
            use_responses_api=bool(config.get("use_responses_api")),
        )
    return MockLLMProvider()


class ProviderRegistry:
    def __init__(self, providers: dict[str, LLMProvider], default: str = "mock"):
        self._providers = providers
        self._default = default

    def get(self, name: str | None = None) -> LLMProvider:
        return self._providers.get(name or self._default, self._providers["mock"])
