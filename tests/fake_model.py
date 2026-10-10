"""A scripted chat model that supports tool calling, for offline tests (no API key needed)."""
from __future__ import annotations

from typing import Any

from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel


class ScriptedToolModel(FakeMessagesListChatModel):
    """Returns the given AIMessages in order; bind_tools is a no-op."""

    def bind_tools(self, tools: Any, **kwargs: Any):  # noqa: D401
        return self
