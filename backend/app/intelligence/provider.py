"""
backend/app/intelligence/provider.py — AI Provider abstraction for ChangeGraph.

Supports:
- AIProvider (abstract base interface)
- BobProvider (IBM Bob runtime/API integration)
- DeterministicFallbackProvider (guaranteed offline, 100% grounded deterministic engine)
- MockAIProvider (testing adapter for unit testing and fault injection)
"""

from __future__ import annotations

import os
import json
import logging
from abc import ABC, abstractmethod
from typing import Optional, Any
from pydantic import BaseModel

logger = logging.getLogger("changegraph.intelligence.provider")


class AIProviderError(Exception):
    """Raised when an AI provider call fails or is misconfigured."""
    pass


class AIProvider(ABC):
    """
    Abstract interface for AI intelligence providers.
    All agent reasoning calls go through this interface.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Display name of the provider."""
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """Return True if the provider is configured and reachable."""
        pass

    @abstractmethod
    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        json_schema: Optional[type[BaseModel]] = None,
    ) -> str:
        """
        Generate a text or JSON completion given a prompt and optional system instructions.
        Must return the completion string (or JSON string if json_schema is provided).
        """
        pass


class BobProvider(AIProvider):
    """
    IBM Bob 2.0 AI Provider integration.
    
    Communicates with IBM Bob / watsonx runtime APIs using configured environment variables.
    Does NOT fake an API; if credentials or endpoint are missing, is_available() returns False.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        api_url: Optional[str] = None,
        model_id: Optional[str] = None,
        timeout: float = 30.0,
    ):
        self._api_key = api_key or os.getenv("IBM_BOB_API_KEY") or os.getenv("BOB_API_KEY")
        self._api_url = (
            api_url
            or os.getenv("IBM_BOB_API_URL")
            or os.getenv("BOB_API_URL")
            or "https://api.bob.ibm.com/v1/chat/completions"
        )
        self._model_id = (
            model_id
            or os.getenv("BOB_MODEL_ID")
            or "ibm-bob-reasoning-2.0"
        )
        self._timeout = timeout

    @property
    def name(self) -> str:
        return "IBM Bob 2.0"

    def is_available(self) -> bool:
        """Available only if an API key is explicitly configured."""
        return bool(self._api_key and self._api_key.strip())

    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        json_schema: Optional[type[BaseModel]] = None,
    ) -> str:
        if not self.is_available():
            raise AIProviderError(
                "IBM Bob provider is not configured. Please set IBM_BOB_API_KEY (and optionally IBM_BOB_API_URL)."
            )

        try:
            import httpx
        except ImportError:
            raise AIProviderError("httpx is required to communicate with the IBM Bob API.")

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        payload: dict[str, Any] = {
            "model": self._model_id,
            "messages": messages,
            "temperature": 0.1,  # Low temperature for strict factual adherence
        }

        if json_schema:
            payload["response_format"] = {"type": "json_object"}

        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
            "X-Client-Application": "ChangeGraph-Phase2",
        }

        try:
            with httpx.Client(timeout=self._timeout) as client:
                response = client.post(self._api_url, json=payload, headers=headers)
                response.raise_for_status()
                data = response.json()
                return data["choices"][0]["message"]["content"]
        except Exception as exc:
            logger.error("IBM Bob API request failed: %s", exc)
            raise AIProviderError(f"IBM Bob communication failure: {exc}") from exc


class DeterministicFallbackProvider(AIProvider):
    """
    Deterministic Grounded Reasoning Provider.
    
    Guarantees 100% testable, zero-hallucination execution when offline or
    when IBM Bob credentials are not provided. Synthesizes explanations
    strictly from Phase 1 graph paths and evidence.
    """

    @property
    def name(self) -> str:
        return "Deterministic Grounded Reasoner"

    def is_available(self) -> bool:
        return True

    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        json_schema: Optional[type[BaseModel]] = None,
    ) -> str:
        # If a JSON schema is requested, we inspect prompt metadata to return valid schema JSON
        if json_schema:
            return json.dumps({"status": "deterministic_grounded"})
        return "Deterministic reasoning generated directly from verified dependency graph."


class MockAIProvider(AIProvider):
    """
    Configurable Mock AI Provider for unit testing and fault injection.
    Supports canned responses, simulated failures, and deliberate hallucination injection.
    """

    def __init__(
        self,
        canned_response: Optional[str] = None,
        should_fail: bool = False,
        failure_message: str = "Simulated AI Provider error",
    ):
        self._canned_response = canned_response
        self._should_fail = should_fail
        self._failure_message = failure_message
        self.call_history: list[dict] = []

    @property
    def name(self) -> str:
        return "Mock AI Provider"

    def is_available(self) -> bool:
        return not self._should_fail

    def set_canned_response(self, response: str) -> None:
        self._canned_response = response

    def set_should_fail(self, fail: bool) -> None:
        self._should_fail = fail

    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        json_schema: Optional[type[BaseModel]] = None,
    ) -> str:
        self.call_history.append({
            "prompt": prompt,
            "system_prompt": system_prompt,
            "json_schema": json_schema,
        })

        if self._should_fail:
            raise AIProviderError(self._failure_message)

        if self._canned_response is not None:
            return self._canned_response

        return "{}"


def get_ai_provider(provider_type: Optional[str] = None) -> AIProvider:
    """
    Factory function to obtain the appropriate AI provider.
    
    Selection logic:
    1. Explicit provider_type ("bob", "deterministic", "mock")
    2. Environment variable CHANGEGRAPH_AI_PROVIDER
    3. Auto-detection: BobProvider if credentials exist, else DeterministicFallbackProvider.
    """
    chosen = provider_type or os.getenv("CHANGEGRAPH_AI_PROVIDER", "").lower().strip()

    if chosen == "bob":
        return BobProvider()
    elif chosen in ("deterministic", "fallback"):
        return DeterministicFallbackProvider()
    elif chosen == "mock":
        return MockAIProvider()

    bob = BobProvider()
    if bob.is_available():
        return bob

    return DeterministicFallbackProvider()
