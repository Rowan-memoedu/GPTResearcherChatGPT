import io
import types
import unittest
from unittest.mock import patch

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from plan_provider import ChatGPTPlanModel, PlanBridge, install_provider, text_messages


class ProviderTests(unittest.TestCase):
    def test_instruction_role_and_text_parts(self):
        messages = text_messages([
            SystemMessage(content="Use cited evidence."),
            HumanMessage(content=[{"type": "text", "text": "Question"}]),
            AIMessage(content="Earlier answer"),
        ])
        self.assertEqual([item["role"] for item in messages], ["developer", "user", "assistant"])
        self.assertEqual(messages[1]["content"], "Question")

    def test_unsupported_input_is_not_silently_discarded(self):
        with self.assertRaises(ValueError):
            text_messages([ToolMessage(content="result", tool_call_id="synthetic")])
        with self.assertRaises(ValueError):
            text_messages([HumanMessage(content=[{"type": "image_url", "image_url": {"url": "https://example.org/image"}}])])

    def test_researcher_parameters_do_not_escape_to_official_route(self):
        install_provider()
        from gpt_researcher.llm_provider.generic.base import GenericLLMProvider
        provider = GenericLLMProvider.from_provider(
            "openai", model="test-model", temperature=0.4, max_tokens=3000,
            api_key="synthetic-not-a-real-key", openai_api_base="https://example.org")
        self.assertIsInstance(provider.llm, ChatGPTPlanModel)
        with patch("plan_provider.bridge.call", return_value={"text": "Verified", "completed": True}) as call:
            self.assertEqual(provider.llm.invoke([HumanMessage(content="Check")]).content, "Verified")
        self.assertEqual(call.call_args.kwargs, {
            "model": "test-model", "messages": [{"role": "user", "content": "Check"}],
        })

    def test_other_billing_provider_fails_closed(self):
        install_provider()
        from gpt_researcher.llm_provider.generic.base import GenericLLMProvider
        with self.assertRaises(ValueError):
            GenericLLMProvider.from_provider("deepseek", model="synthetic")

    def test_partial_response_is_not_success(self):
        bridge = PlanBridge()
        fake_process = types.SimpleNamespace(stdin=io.StringIO())
        bridge.process = fake_process
        bridge.responses.put({"id": 1, "result": {"text": "partial", "completed": False}})
        try:
            with patch.object(bridge, "_start"), self.assertRaisesRegex(RuntimeError, "not completed"):
                bridge.call("respond", model="synthetic", messages=[])
            self.assertEqual(bridge.completed_requests, 0)
        finally:
            bridge.process = None

    def test_quota_error_prevents_repeated_inference(self):
        bridge = PlanBridge()
        bridge.fatal_error = "ChatGPT plan request failed: subscription_sharing_usage_limit_exceeded"
        with patch.object(bridge, "_start") as start, self.assertRaisesRegex(RuntimeError, "usage_limit_exceeded"):
            bridge.call("respond", model="synthetic", messages=[])
        start.assert_not_called()


if __name__ == "__main__":
    unittest.main()
