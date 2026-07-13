"""
llm_service.py
===============
Wraps calls to an OPEN-SOURCE LLM hosted on Hugging Face.

WHY THE INFERENCE API (instead of downloading the model locally):
For a working prototype, downloading a 7B+ parameter model and running
it locally requires a beefy GPU and a lot of setup. Hugging Face's
Inference API/Inference Providers let you call hosted open-source
models (Mistral, Llama, Zephyr, etc.) over HTTPS with just an API
token - perfect for a fast prototype. When you're ready to scale, you
can swap this file's internals for a self-hosted model (e.g. via
`text-generation-inference` or `vllm`) WITHOUT changing any other file,
since the rest of the app only calls `generate_reply(messages)`.

This uses `huggingface_hub.InferenceClient`, which supports the same
OpenAI-style `messages=[{"role": ..., "content": ...}]` chat format.
"""

from huggingface_hub import InferenceClient
from huggingface_hub.errors import HfHubHTTPError

from app.config import settings


class LLMServiceError(Exception):
    """Raised when the LLM call fails, so the API layer can return a
    clean HTTP error instead of leaking a raw stack trace."""


class HuggingFaceLLMService:
    """
    Thin wrapper around the Hugging Face InferenceClient.

    Kept as a class (rather than bare functions) so that:
      - The client connection is set up once and reused.
      - It's easy to swap in a different backend later (just implement
        a new class with the same `generate_reply` method signature).
    """

    def __init__(self):
        self.client = InferenceClient(token=settings.HF_TOKEN)
        self.model = settings.HF_MODEL

    def generate_reply(self, messages: list[dict]) -> str:
        """
        Send a full conversation (system + history + new message) to
        the hosted LLM and return just the assistant's reply text.

        `messages` format:
            [{"role": "system"|"user"|"assistant", "content": "..."}]
        """
        try:
            completion = self.client.chat_completion(
                messages=messages,
                model=self.model,
                max_tokens=settings.LLM_MAX_NEW_TOKENS,
                temperature=settings.LLM_TEMPERATURE,
            )
            # chat_completion() returns an OpenAI-compatible response object
            reply_text = completion.choices[0].message.content
            return reply_text.strip()

        except HfHubHTTPError as e:
            # Common causes: invalid HF_TOKEN, model requires a paid
            # provider, or the model name is wrong/unsupported.
            raise LLMServiceError(
                f"Hugging Face API error while calling model '{self.model}': {e}"
            ) from e

        except Exception as e:  # noqa: BLE001 - we want to catch-all here
            # broad catch to fail into a clean HTTP error instead of a
            # 500 with an unreadable trace, useful during prototyping.
            raise LLMServiceError(f"Unexpected error generating LLM reply: {e}") from e


# A single shared instance, imported wherever the app needs to talk to the LLM.
llm_service = HuggingFaceLLMService()
