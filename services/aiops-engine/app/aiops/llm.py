"""
Shared LLM factory for the AIOps agents.

All four agents talk to a Groq-hosted model through this one factory, so the
backend is interchangeable: override the model id (GROQ_MODEL) without code
changes, or — for a local/self-hosted deployment — replace ChatGroq with a
ChatOllama here and nothing in the agent code changes. (Note: a GPU-less local
model trades away the interactive latency, so that path is a documented option,
not the evaluated configuration.)

Auth: ChatGroq reads GROQ_API_KEY from the environment (injected from the
netguard-secrets Secret). The model id comes from GROQ_MODEL in the ConfigMap.
"""

import os

from langchain_groq import ChatGroq

# Pinned 2026-06-27 to a current Groq production model. The previous default,
# llama-3.3-70b-versatile, is on Groq's deprecation path (shutdown 2026-08-16);
# Groq recommends openai/gpt-oss-120b. Hosted-model churn is a documented
# limitation of cloud inference — override with GROQ_MODEL, no code change.
DEFAULT_MODEL = "openai/gpt-oss-120b"


def get_llm(temperature: float = 0.0, json_mode: bool = True) -> ChatGroq:
    """
    Build a ChatGroq client.

    Args:
        temperature: 0 for deterministic classification/RCA, slightly higher
                     for the postmortem prose.
        json_mode:   when True, force Groq's JSON object response format. Only
                     valid for the no-tool reasoning calls (every agent here is
                     a single summarization call, so this is always safe). The
                     prompt must mention "JSON" for Groq to honor it — all of
                     ours do.
    """
    kwargs: dict = {
        "model": os.getenv("GROQ_MODEL", DEFAULT_MODEL),
        "temperature": temperature,
    }
    if json_mode:
        kwargs["model_kwargs"] = {"response_format": {"type": "json_object"}}
    return ChatGroq(**kwargs)
