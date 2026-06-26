"""
Postmortem Agent — generates a structured blameless postmortem document.

No tools — one LLM call that takes all prior agent outputs and produces
a postmortem following Google SRE blameless postmortem format.
"""

import json
from langchain_core.prompts import ChatPromptTemplate

from ..llm import get_llm

POSTMORTEM_SYSTEM_PROMPT = """You are a senior SRE writing a blameless postmortem.
You have the full incident context: triage scope, evidence, and root cause analysis.

Write a structured postmortem following the Google SRE blameless postmortem format.
Focus on systems and processes, not individuals. Never assign blame to a person.

Return ONLY a valid JSON object with these exact fields:
{{
  "title": "Short incident title (under 80 chars)",
  "impact": "Who was affected and how. Quantify if possible (e.g., 90 minutes of downtime).",
  "timeline": [
    {{"time": "HH:MM:SS", "event": "what happened"}},
    {{"time": "HH:MM:SS", "event": "what happened"}}
  ],
  "root_cause": "One clear paragraph. Use the RCA output. Be specific.",
  "contributing_factors": [
    "Factor 1 (system/process issue, not person)",
    "Factor 2"
  ],
  "what_went_well": [
    "What helped or limited the impact"
  ],
  "action_items": [
    {{"action": "specific action", "priority": "P0|P1|P2", "owner": "team or role"}},
    {{"action": "specific action", "priority": "P0|P1|P2", "owner": "team or role"}}
  ],
  "lessons_learned": "Two to three sentences on what this incident reveals about the system.",
  "blameless_statement": "One sentence affirming no individual is at fault and why."
}}

Priority guide:
- P0: must be done before this can happen again (immediate)
- P1: should be done within a week
- P2: longer-term improvement

Keep the tone factual. Avoid filler phrases.
"""


async def run_postmortem(
    triage_output:   dict,
    evidence_output: dict,
    rca_output:      dict,
    incident_id:     str,
) -> dict:
    """
    Generate a blameless postmortem from the full incident context.
    """
    llm = get_llm(temperature=0.1, json_mode=True)  # slight creativity for prose

    prompt = ChatPromptTemplate.from_messages([
        ("system", POSTMORTEM_SYSTEM_PROMPT),
        ("human", """INCIDENT ID: {incident_id}

TRIAGE SCOPE:
{triage}

KEY EVIDENCE:
{evidence}

ROOT CAUSE ANALYSIS:
{rca}

Write the blameless postmortem. Return JSON only."""),
    ])

    chain = prompt | llm

    # Strip raw evidence — too large for this context
    evidence_for_llm = {k: v for k, v in evidence_output.items() if k != "raw_evidence"}

    try:
        result = await chain.ainvoke({
            "incident_id": incident_id,
            "triage":      json.dumps(triage_output,      indent=2),
            "evidence":    json.dumps(evidence_for_llm,   indent=2),
            "rca":         json.dumps(rca_output,         indent=2),
        })
        output = result.content
        if "```" in output:
            output = output.split("```")[1].lstrip("json").strip()
        return json.loads(output)
    except Exception as e:
        return {
            "title":                "Postmortem generation failed",
            "impact":               "Unknown",
            "timeline":             [],
            "root_cause":           rca_output.get("root_cause", "Unknown"),
            "contributing_factors": rca_output.get("contributing_factors", []),
            "what_went_well":       [],
            "action_items":         [],
            "lessons_learned":      "Postmortem could not be generated automatically.",
            "blameless_statement":  "No individual is at fault.",
            "error":                str(e),
        }
