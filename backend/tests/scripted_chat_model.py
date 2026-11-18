"""A LangChain chat model that replays scripted replies, for testing the agent without network.

Unlike LangChain's own fakes it supports `bind_tools` and streams tool calls, and it records
the messages it was sent, so tests can assert what the model saw (memory, trimming).
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, AIMessageChunk, BaseMessage
from langchain_core.outputs import ChatGeneration, ChatGenerationChunk, ChatResult
from pydantic import ConfigDict, Field

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Sequence

    from langchain_core.callbacks import (
        AsyncCallbackManagerForLLMRun,
        CallbackManagerForLLMRun,
    )


def tool_call(name: str, call_id: str = "call-1", **args: Any) -> AIMessage:
    return AIMessage(content="", tool_calls=[{"name": name, "args": args, "id": call_id}])


class ScriptedChatModel(BaseChatModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    replies: list[AIMessage]
    repeat_last: bool = False  # keep replaying the last reply (e.g. an endless tool loop)
    error: Exception | None = None
    received: list[list[BaseMessage]] = Field(default_factory=list)

    @property
    def _llm_type(self) -> str:
        return "scripted"

    def bind_tools(self, tools: Sequence[Any], **kwargs: Any) -> ScriptedChatModel:  # type: ignore[override]
        return self

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: CallbackManagerForLLMRun | None = None,
        **kwargs: Any,
    ) -> ChatResult:
        return ChatResult(generations=[ChatGeneration(message=self._next(messages))])

    async def _astream(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: AsyncCallbackManagerForLLMRun | None = None,
        **kwargs: Any,
    ) -> AsyncIterator[ChatGenerationChunk]:
        reply = self._next(messages)
        if reply.tool_calls:
            chunks = [
                {"name": c["name"], "args": json.dumps(c["args"]), "id": c["id"], "index": i}
                for i, c in enumerate(reply.tool_calls)
            ]
            yield ChatGenerationChunk(message=AIMessageChunk(content="", tool_call_chunks=chunks))
            return
        for i, word in enumerate(str(reply.content).split(" ")):
            yield ChatGenerationChunk(
                message=AIMessageChunk(content=word if i == 0 else f" {word}")
            )

    def _next(self, messages: list[BaseMessage]) -> AIMessage:
        self.received.append(list(messages))
        if self.error is not None:
            raise self.error
        if self.repeat_last and len(self.replies) == 1:
            return self.replies[0]
        return self.replies.pop(0)
