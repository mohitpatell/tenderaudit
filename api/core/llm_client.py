"""Pluggable LLM client for OpenAI Structured Outputs.

Backends are selected via the ``LLM_BACKEND`` env var (``openai`` | ``vllm``).
The vLLM path is intentionally a stub for the hackathon demo.
"""

from __future__ import annotations

import os
from typing import Any, Optional, Type, TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


class LLMClient:
    """Thin wrapper that returns parsed Pydantic models from a chat completion."""

    def __init__(
        self,
        backend: Optional[str] = None,
        model: Optional[str] = None,
        api_key: Optional[str] = None,
    ) -> None:
        self.backend = (backend or os.getenv("LLM_BACKEND", "openai")).lower()
        self.model = model or os.getenv("OPENAI_MODEL", "gpt-4o-2024-08-06")
        self._api_key = api_key or os.getenv("OPENAI_API_KEY")
        self._client: Any = None

    def _ensure_openai(self) -> Any:
        if self._client is not None:
            return self._client
        try:
            from openai import OpenAI
        except ImportError as e:  # pragma: no cover
            raise RuntimeError("install openai: pip install openai>=1.30") from e
        self._client = OpenAI(api_key=self._api_key)
        return self._client

    def parse(
        self,
        *,
        system: str,
        user: str,
        response_format: Type[T],
        temperature: float = 0.0,
    ) -> T:
        """Run the LLM and return a validated Pydantic model.

        Raises
        ------
        NotImplementedError
            If ``LLM_BACKEND=vllm``.
        RuntimeError
            If the OpenAI SDK refuses to parse / returns no completion.
        """
        if self.backend == "vllm":
            raise NotImplementedError(
                "vllm path documented in docs/airgap_deployment.md"
            )
        if self.backend != "openai":
            raise ValueError(f"unknown LLM_BACKEND: {self.backend!r}")

        client = self._ensure_openai()
        completion = client.beta.chat.completions.parse(
            model=self.model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            response_format=response_format,
            temperature=temperature,
        )
        choice = completion.choices[0]
        parsed = choice.message.parsed
        if parsed is None:
            raise RuntimeError(
                f"LLM returned no parsed payload (refusal={choice.message.refusal!r})"
            )
        return parsed

    def extract(
        self,
        *,
        spans_text: str,
        prompt: str,
        response_format: Type[T],
        temperature: float = 0.0,
    ) -> T:
        """Convenience: run a single extraction over span text with a system prompt."""
        return self.parse(
            system=prompt,
            user=spans_text,
            response_format=response_format,
            temperature=temperature,
        )
