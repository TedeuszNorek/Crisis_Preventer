"""LLM provider abstraction — swap between Claude, DeepSeek, OpenAI, or any OpenAI-compatible API.

Set LLM_PROVIDER in .env to choose:
  - claude      → Anthropic API (claude-sonnet-4-6 default)
  - deepseek    → DeepSeek API (openai-compatible, cheap, strong reasoning)
  - openai      → OpenAI API
  - openrouter  → OpenRouter (access to many models via one key)
  - local       → any local OpenAI-compatible server (Ollama, LM Studio, vLLM)
"""
from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class LLMResponse:
    tool_calls: List[Dict[str, Any]]
    text: Optional[str]
    model: str
    provider: str


class LLMClient:
    """Unified client that routes to the right provider based on LLM_PROVIDER env var."""

    def __init__(self) -> None:
        self.provider = os.getenv("LLM_PROVIDER", "claude").lower()
        self.model = os.getenv("LLM_MODEL", self._default_model())
        self._client = self._build_client()
        logger.info(f"[LLM] Provider: {self.provider} | Model: {self.model}")

    def _default_model(self) -> str:
        return {
            "claude":     "claude-sonnet-4-6",
            "deepseek":   "deepseek-reasoner",
            "openai":     "gpt-4o",
            "openrouter": "deepseek/deepseek-r1",
            "local":      "llama3",
        }.get(self.provider, "claude-sonnet-4-6")

    def _build_client(self) -> Any:
        if self.provider == "claude":
            try:
                import anthropic
                key = os.getenv("ANTHROPIC_API_KEY")
                if not key:
                    raise RuntimeError("ANTHROPIC_API_KEY not set")
                return anthropic.Anthropic(api_key=key)
            except ImportError:
                raise RuntimeError("pip install anthropic")

        # All others use OpenAI-compatible interface
        try:
            from openai import AsyncOpenAI
        except ImportError:
            raise RuntimeError("pip install openai")

        base_urls = {
            "deepseek":   "https://api.deepseek.com/v1",
            "openai":     "https://api.openai.com/v1",
            "openrouter": "https://openrouter.ai/api/v1",
            "local":      os.getenv("LOCAL_LLM_URL", "http://localhost:11434/v1"),
        }
        api_keys = {
            "deepseek":   os.getenv("DEEPSEEK_API_KEY", ""),
            "openai":     os.getenv("OPENAI_API_KEY", ""),
            "openrouter": os.getenv("OPENROUTER_API_KEY", ""),
            "local":      "ollama",  # local servers usually ignore the key
        }
        return AsyncOpenAI(
            api_key=api_keys.get(self.provider, ""),
            base_url=base_urls.get(self.provider, "https://api.openai.com/v1"),
        )

    # ── Unified call ─────────────────────────────────────────────────────────

    async def call(
        self,
        system: str,
        user: str,
        tools: List[Dict],
        max_tokens: int = 1024,
    ) -> LLMResponse:
        if self.provider == "claude":
            return await self._call_claude(system, user, tools, max_tokens)
        return await self._call_openai_compat(system, user, tools, max_tokens)

    async def _call_claude(self, system, user, tools, max_tokens) -> LLMResponse:
        import asyncio
        # Anthropic client is sync — run in thread pool
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            lambda: self._client.messages.create(
                model=self.model,
                max_tokens=max_tokens,
                system=system,
                tools=tools,
                messages=[{"role": "user", "content": user}],
            ),
        )
        tool_calls = []
        text = None
        for block in response.content:
            if block.type == "tool_use":
                tool_calls.append({"name": block.name, "input": block.input})
            elif block.type == "text":
                text = block.text
        return LLMResponse(tool_calls=tool_calls, text=text,
                           model=self.model, provider="claude")

    async def _call_openai_compat(self, system, user, tools, max_tokens) -> LLMResponse:
        # Convert Anthropic tool schema → OpenAI function schema
        oai_tools = [
            {
                "type": "function",
                "function": {
                    "name": t["name"],
                    "description": t.get("description", ""),
                    "parameters": t.get("input_schema", {}),
                },
            }
            for t in tools
        ]
        response = await self._client.chat.completions.create(
            model=self.model,
            max_tokens=max_tokens,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            tools=oai_tools,
            tool_choice="auto",
        )
        msg = response.choices[0].message
        tool_calls = []
        if msg.tool_calls:
            for tc in msg.tool_calls:
                try:
                    args = json.loads(tc.function.arguments)
                except json.JSONDecodeError:
                    args = {}
                tool_calls.append({"name": tc.function.name, "input": args})
        return LLMResponse(tool_calls=tool_calls, text=msg.content,
                           model=self.model, provider=self.provider)
