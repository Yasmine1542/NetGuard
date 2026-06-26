"""
Shared LLM factory for the AIOps agents.

All four agents talk to a Groq-hosted Llama model through this one factory, so
the backend is interchangeable: swap the model id (GROQ_MODEL) or, for an
air-gapped deployment, replace ChatGroq with a local ChatOllama here and nothing
in the agent code changes.

Auth: ChatGroq reads GROQ_API_KEY from the environment (injected from the
netguard-groq-secret). The model id comes from GROQ_MODEL in the ConfigMap.
"""

import os

from langchain_groq import ChatGroq

DEFAULT_MODEL = "llama-3.3-70b-versatile"


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
