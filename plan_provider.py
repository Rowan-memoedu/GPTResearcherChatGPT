"""GPT Researcher model adapter for OpenAI's official ChatGPT plan DevKit."""
from __future__ import annotations

import atexit
import json
import os
import queue
import subprocess
import threading
from pathlib import Path
from typing import Any

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.outputs import ChatGeneration, ChatResult


def text_messages(messages: list[BaseMessage]) -> list[dict[str, str]]:
    roles = {"human": "user", "ai": "assistant", "system": "developer"}
    result = []
    for message in messages:
        role = roles.get(message.type)
        if role is None:
            raise ValueError(f"Unsupported message kind: {message.type}")
        content = message.content
        if isinstance(content, list):
            if any(not isinstance(part, dict) or part.get("type") != "text" for part in content):
                raise ValueError("This research adapter supports text messages only")
            content = "\n".join(part["text"] for part in content)
        if not isinstance(content, str):
            raise ValueError("Message content must be text")
        result.append({"role": role, "content": content})
    return result


class PlanBridge:
    def __init__(self):
        self.lock = threading.Lock()
        self.sequence = 0
        self.process = None
        self.responses = queue.Queue()
        self.fatal_error = None
        self.completed_requests = 0
        atexit.register(self.close)

    def _start(self):
        if self.process is not None and self.process.poll() is None:
            return
        self.responses = queue.Queue()
        self.process = subprocess.Popen(
            [os.getenv("GPTR_NODE", "node"), str(Path(__file__).with_name("chatgpt-worker.mjs"))],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=None,
            text=True, encoding="utf-8", bufsize=1,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
        output = self.process.stdout
        responses = self.responses

        def read_output():
            try:
                for line in output:
                    responses.put(json.loads(line))
            except Exception:
                responses.put({"error": {"code": "invalid_worker_output"}})
            finally:
                responses.put(None)

        threading.Thread(target=read_output, daemon=True).start()

    def call(self, operation: str, **values):
        with self.lock:
            if self.fatal_error and operation == "respond":
                raise RuntimeError(self.fatal_error)
            self._start()
            self.sequence += 1
            request = {"id": self.sequence, "op": operation, **values}
            self.process.stdin.write(json.dumps(request, ensure_ascii=False) + "\n")
            self.process.stdin.flush()
            try:
                response = self.responses.get(timeout=210)
            except queue.Empty:
                self.close()
                raise RuntimeError("Official ChatGPT response timed out") from None
            if response is None or response.get("id") != self.sequence:
                self.close()
                raise RuntimeError("ChatGPT worker ended or returned an unexpected response")
            if error := response.get("error"):
                code = error.get("code", "unknown")
                message = f"ChatGPT plan request failed: {code}"
                if code.startswith("subscription_sharing_") or code in {
                    "sign_in_required", "sharing_not_enabled", "invalid_id_token", "unauthorized", "forbidden"
                }:
                    self.fatal_error = message
                raise RuntimeError(message)
            if operation == "respond":
                if not response["result"].get("completed"):
                    raise RuntimeError("ChatGPT response was not completed")
                self.completed_requests += 1
            return response["result"]

    def close(self):
        if self.process is not None:
            try:
                self.process.stdin.close()
                self.process.wait(timeout=3)
            except Exception:
                self.process.kill()
            self.process = None


bridge = PlanBridge()


class ChatGPTPlanModel(BaseChatModel):
    model_name: str

    @property
    def _llm_type(self) -> str:
        return "official-chatgpt-plan"

    @property
    def _identifying_params(self) -> dict[str, Any]:
        return {"model": self.model_name, "billing": "chatgpt-plan"}

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        if stop:
            raise ValueError("Stop sequences are not supported by this plan route")
        result = bridge.call("respond", model=self.model_name, messages=text_messages(messages))
        message = AIMessage(content=result["text"], response_metadata={"billing": "chatgpt-plan", "completed": True})
        return ChatResult(generations=[ChatGeneration(message=message)])


def install_provider() -> None:
    from gpt_researcher.llm_provider.generic.base import GenericLLMProvider

    @classmethod
    def from_provider(cls, provider, chat_log=None, verbose=True, **kwargs):
        if provider != "openai":
            raise ValueError("This installation uses ChatGPT plan inference only; another billing path is not configured")
        return cls(ChatGPTPlanModel(model_name=kwargs["model"]), chat_log=None, verbose=verbose)

    GenericLLMProvider.from_provider = from_provider
