"""
RCA Agent — reasons over Triage + Evidence output to identify root cause.

No tools — pure LLM chain-of-thought reasoning on structured input.
Uses structured output format for reliable JSON parsing.
"""

import json
from langchain_core.prompts import ChatPromptTemplate

from ..llm import get_llm

RCA_SYSTEM_PROMPT = """You are a senior Kubernetes SRE performing root cause analysis.
You have received an incident scope (from Triage) and an evidence bundle (from Evidence collection).

Reason step by step. Cite specific values, timestamps, and log lines from the evidence.
Do not speculate beyond what the evidence supports.

Think through these steps:
1. What are the primary symptoms? (what failed, how, when)
2. What do the metrics reveal? (trends, spikes, saturation)
3. What do the logs reveal? (last lines, errors, warnings)
4. Did a recent deployment precede this? (could be the cause)
5. What is the most probable root cause?
6. What can be ruled out and why?

Return ONLY a valid JSON object with these exact fields:
{{
  "reasoning_steps": [
    "step 1 reasoning...",
    "step 2 reasoning...",
    "step 3 reasoning...",
    "step 4 reasoning...",
    "step 5 reasoning...",
    "step 6 reasoning..."
  ],
  "root_cause": "specific, one-paragraph description of the root cause",
  "confidence": 0.0,
  "contributing_factors": [
    "factor 1",
    "factor 2"
  ],
  "ruled_out": [
    "what was ruled out and why"
  ],
  "severity": "HIGH|MED|LOW",
  "affected_components": ["component1", "component2"]
}}

Confidence scale:
- 0.9–1.0: evidence is conclusive (e.g., log line directly shows the cause)
- 0.7–0.9: strong evidence pointing to one cause
- 0.5–0.7: most likely cause but multiple possibilities
- below 0.5: insufficient evidence, flag this
"""


async def run_rca(triage_output: dict, evidence_output: dict) -> dict:
    """
    Run the RCA Agent over combined Triage + Evidence output.
    Returns structured root cause analysis.
    """
    llm = get_llm(temperature=0, json_mode=True)

    prompt = ChatPromptTemplate.from_messages([
        ("system", RCA_SYSTEM_PROMPT),
        ("human", """INCIDENT SCOPE (from Triage Agent):
{triage}

EVIDENCE BUNDLE (from Evidence Agent):
{evidence}

Perform root cause analysis. Return JSON only."""),
    ])

    chain = prompt | llm

    # Trim raw_evidence from the evidence output to keep context window manageable
    evidence_for_llm = {k: v for k, v in evidence_output.items() if k != "raw_evidence"}

    try:
        result = await chain.ainvoke({
            "triage":   json.dumps(triage_output, indent=2),
            "evidence": json.dumps(evidence_for_llm, indent=2),
        })
        output = result.content
        if "```" in output:
            output = output.split("```")[1].lstrip("json").strip()
        return json.loads(output)
    except Exception as e:
        return {
            "reasoning_steps":     ["RCA agent failed to complete reasoning"],
            "root_cause":          "Unable to determine root cause — analysis failed",
            "confidence":          0.0,
            "contributing_factors": [],
            "ruled_out":           [],
            "severity":            triage_output.get("severity", "LOW"),
            "affected_components": triage_output.get("affected_pods", []),
            "error":               str(e),
        }
