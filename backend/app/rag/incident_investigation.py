"""Stage 8: AI SOC Incident Investigation Engine."""

import json
import logging
import re
from pathlib import Path
from typing import Any

from app.alerts.schemas import IncidentInvestigation
from app.rag.config import (
    DEFAULT_COLLECTION_NAME,
    DEFAULT_EMBEDDING_MODEL,
    DEFAULT_RAG_MAX_CONTEXT_CHARS,
    DEFAULT_RAG_SCORE_THRESHOLD,
    DEFAULT_RAG_TOP_K,
    DEFAULT_VECTOR_STORE_DIRECTORY,
)
from app.rag.generator import build_sources_list, construct_context
from app.rag.llm import GeminiProvider, LLMProvider
from app.rag.schemas import RAGSource
from app.rag.search import search_chunks

logger = logging.getLogger(__name__)

INCIDENT_INVESTIGATOR_SYSTEM_PROMPT = (
    "You are an AI assistant supporting a Security Operations Center analyst.\n"
    "Analyze the supplied incident using ONLY:\n"
    "1. the observed alert data,\n"
    "2. the deterministic correlation/risk information,\n"
    "3. the retrieved cybersecurity knowledge.\n"
    "Do not invent evidence.\n"
    "Do not invent attack attribution.\n"
    "Do not claim that compromise occurred unless the supplied evidence explicitly establishes it.\n"
    "Do not invent MITRE ATT&CK technique IDs.\n"
    "Only mention a MITRE technique when it is supported by the retrieved source context.\n"
    "Clearly distinguish observed evidence from security guidance and analyst recommendations.\n"
    "The deterministic risk score is supplied by the system and must not be changed by the LLM."
)

FALLBACK_INVESTIGATION_SUMMARY = (
    "I could not find sufficient information in the security knowledge base to complete "
    "an in-depth threat context investigation for this incident."
)


def _get_attr(item: Any, key: str, default: Any = "") -> Any:
    """Extract attribute safely from object or dictionary."""
    if isinstance(item, dict):
        return item.get(key, default)
    return getattr(item, key, default)


def build_incident_retrieval_query(incident: Any, alerts: list[Any] | None = None) -> str:
    """Construct a focused retrieval query from correlated incident attributes."""
    if alerts is None:
        alerts = _get_attr(incident, "alerts", [])

    attack_types = [str(at).strip() for at in _get_attr(incident, "attack_types", []) if str(at).strip()]
    if not attack_types:
        attack_types = list({str(_get_attr(a, "attack_type", "")).strip() for a in alerts if _get_attr(a, "attack_type", "")})

    protocols = list({str(_get_attr(a, "protocol", "")).strip() for a in alerts if _get_attr(a, "protocol", "")})
    dest_ports = list({str(_get_attr(a, "destination_port", "")).strip() for a in alerts if _get_attr(a, "destination_port", "")})

    query_parts: list[str] = []
    if attack_types:
        query_parts.append(" ".join(attack_types))
    if protocols:
        query_parts.append(" ".join(protocols))
    if dest_ports:
        query_parts.append(f"destination port {' '.join(dest_ports)}")

    query_parts.append("investigation detection mitigation incident response")

    query = " ".join(query_parts).strip()
    return re.sub(r"\s+", " ", query)


def build_incident_investigation_prompt(incident: Any, context: str, alerts: list[Any] | None = None) -> str:
    """Build user prompt containing structured incident data, alert details, and retrieved context."""
    if alerts is None:
        alerts = _get_attr(incident, "alerts", [])

    incident_id = str(_get_attr(incident, "incident_id", "N/A"))
    alert_count = str(_get_attr(incident, "alert_count", len(alerts)))
    first_seen = str(_get_attr(incident, "first_seen", "N/A"))
    last_seen = str(_get_attr(incident, "last_seen", "N/A"))
    source_ips = ", ".join(list(_get_attr(incident, "source_ips", []))) or str(_get_attr(incident, "source_ip", "N/A"))
    destination_ips = ", ".join(list(_get_attr(incident, "destination_ips", []))) or ", ".join(list(_get_attr(incident, "target_ips", []))) or "N/A"
    attack_types = ", ".join(list(_get_attr(incident, "attack_types", []))) or ", ".join(list(_get_attr(incident, "distinct_attack_types", []))) or "N/A"
    risk_score = str(_get_attr(incident, "risk_score", "N/A"))
    risk_factors = "\n".join([f"  - {rf}" for rf in _get_attr(incident, "risk_factors", [])]) or "  - None specified"

    alert_breakdown_lines = []
    for idx, a in enumerate(alerts, 1):
        alert_breakdown_lines.append(
            f"  {idx}. ID: {_get_attr(a, 'id', 'N/A')} | Time: {_get_attr(a, 'timestamp', 'N/A')} | "
            f"Type: {_get_attr(a, 'attack_type', 'N/A')} | Severity: {_get_attr(a, 'severity', 'N/A')} | "
            f"Conf: {_get_attr(a, 'confidence', 'N/A')} | Proto: {_get_attr(a, 'protocol', 'N/A')} | "
            f"Src: {_get_attr(a, 'source_ip', 'N/A')}:{_get_attr(a, 'source_port', 'N/A')} -> "
            f"Dst: {_get_attr(a, 'destination_ip', 'N/A')}:{_get_attr(a, 'destination_port', 'N/A')}"
        )
    alert_breakdown = "\n".join(alert_breakdown_lines)

    return (
        "CORRELATED INCIDENT CAMPAIGN SUMMARY:\n"
        "----------------------------------------\n"
        f"- Incident ID: {incident_id}\n"
        f"- Total Correlated Alerts: {alert_count}\n"
        f"- First Seen: {first_seen}\n"
        f"- Last Seen: {last_seen}\n"
        f"- Source IPs: {source_ips}\n"
        f"- Destination IPs: {destination_ips}\n"
        f"- Attack Types: {attack_types}\n"
        f"- System Deterministic Risk Score: {risk_score} / 100\n"
        f"- System Risk Factors:\n{risk_factors}\n"
        "----------------------------------------\n\n"
        "UNDERLYING OBSERVED ALERTS:\n"
        "----------------------------------------\n"
        f"{alert_breakdown}\n"
        "----------------------------------------\n\n"
        "RETRIEVED CYBERSECURITY KNOWLEDGE:\n"
        "----------------------------------------\n"
        f"{context}\n"
        "----------------------------------------\n\n"
        "INSTRUCTIONS:\n"
        "As an AI SOC Analyst Assistant, produce a grounded incident investigation report based ONLY on the supplied "
        "incident facts, deterministic risk information, and retrieved cybersecurity knowledge.\n"
        "Do NOT alter or question the system's deterministic risk score.\n"
        "Do NOT invent evidence, attack attribution, or MITRE ATT&CK technique IDs.\n"
        "Only list a MITRE technique in 'mitre_context' if it is explicitly present in the retrieved context.\n\n"
        "Format your entire response as a valid JSON object with the following keys:\n"
        '{\n'
        '  "executive_summary": "High-level summary of the incident campaign based strictly on supplied evidence",\n'
        '  "observed_evidence": ["List of specific observed evidence and event facts"],\n'
        '  "threat_context": ["List of threat mechanisms and security context derived strictly from retrieved sources"],\n'
        '  "investigation_priorities": ["List of priority triage questions for the SOC analyst"],\n'
        '  "recommended_actions": ["List of concrete analyst verification and containment steps"],\n'
        '  "mitigations": ["List of system mitigations supported by retrieved context"],\n'
        '  "mitre_context": ["List of MITRE ATT&CK techniques explicitly mentioned in retrieved sources (empty if none)"],\n'
        '  "limitations": ["List of analytical boundaries (e.g. advisory decision-support, scope limitations)"]\n'
        '}\n'
        "Return ONLY the JSON object. Do not include markdown code block syntax or text outside the JSON."
    )


def _clean_json_text(text: str) -> str:
    """Strip markdown code block fences if present."""
    cleaned = text.strip()
    if cleaned.startswith("```json"):
        cleaned = cleaned[7:]
    elif cleaned.startswith("```"):
        cleaned = cleaned[3:]
    if cleaned.endswith("```"):
        cleaned = cleaned[:-3]
    return cleaned.strip()


def parse_investigation_response(raw_text: str, incident: Any, alerts: list[Any] | None = None) -> IncidentInvestigation:
    """Robustly parse the LLM's response into an IncidentInvestigation model."""
    if alerts is None:
        alerts = _get_attr(incident, "alerts", [])

    cleaned = _clean_json_text(raw_text)

    # Attempt 1: Direct JSON parsing
    try:
        data = json.loads(cleaned)
        if isinstance(data, dict):
            return IncidentInvestigation(
                executive_summary=str(data.get("executive_summary", "")).strip() or "Incident investigation completed.",
                observed_evidence=[str(x).strip() for x in data.get("observed_evidence", []) if str(x).strip()],
                threat_context=[str(x).strip() for x in data.get("threat_context", []) if str(x).strip()],
                investigation_priorities=[str(x).strip() for x in data.get("investigation_priorities", []) if str(x).strip()],
                recommended_actions=[str(x).strip() for x in data.get("recommended_actions", []) if str(x).strip()],
                mitigations=[str(x).strip() for x in data.get("mitigations", []) if str(x).strip()],
                mitre_context=[str(x).strip() for x in data.get("mitre_context", []) if str(x).strip()],
                limitations=[str(x).strip() for x in data.get("limitations", []) if str(x).strip()],
            )
    except (json.JSONDecodeError, TypeError) as exc:
        logger.warning("LLM investigation response was not valid JSON; using fallback parser: %s", exc)

    # Attempt 2: Text/Markdown heuristic fallback
    summary_match = re.search(
        r"(?:###?\s*Executive Summary|Summary:?)\s*(.*?)(?=(?:###?\s*[A-Z]|Observed Evidence|Threat Context|\Z))",
        raw_text,
        re.DOTALL | re.IGNORECASE,
    )
    summary = summary_match.group(1).strip() if summary_match else raw_text.strip()[:500]

    attack_types = ", ".join(list(_get_attr(incident, "attack_types", []))) or ", ".join(list(_get_attr(incident, "distinct_attack_types", []))) or "Unknown"

    return IncidentInvestigation(
        executive_summary=summary or f"Incident campaign involving {attack_types}.",
        observed_evidence=[
            f"Correlated Alert Count: {_get_attr(incident, 'alert_count', len(alerts))}",
            f"Attack Types: {attack_types}",
            f"Deterministic Risk Score: {_get_attr(incident, 'risk_score', 'N/A')}",
        ],
        threat_context=[],
        investigation_priorities=[
            "Verify packet captures and firewall logs for the affected host IPs.",
            "Confirm whether destination ports were listening and accessible.",
        ],
        recommended_actions=[
            "Review session logs for involved source IPs during the event timeframe.",
        ],
        mitigations=[
            "Ensure network perimeter filtering rules restrict unnecessary exposure.",
        ],
        mitre_context=[],
        limitations=[
            "Response was formatted as plain text; parsed using heuristic fallback.",
            "Analysis is advisory decision-support based on available alert data.",
        ],
    )


def investigate_incident(
    incident: Any,
    alerts: list[Any] | None = None,
    top_k: int = DEFAULT_RAG_TOP_K,
    score_threshold: float | None = DEFAULT_RAG_SCORE_THRESHOLD,
    max_context_chars: int = DEFAULT_RAG_MAX_CONTEXT_CHARS,
    llm_client: LLMProvider | None = None,
    vector_store_path: Path = DEFAULT_VECTOR_STORE_DIRECTORY,
    collection_name: str = DEFAULT_COLLECTION_NAME,
    embedding_model_name: str = DEFAULT_EMBEDDING_MODEL,
) -> tuple[IncidentInvestigation, list[RAGSource]]:
    """Generate a grounded AI SOC investigation report for a correlated incident campaign."""
    if alerts is None:
        alerts = _get_attr(incident, "alerts", [])

    query = build_incident_retrieval_query(incident, alerts)
    if not query:
        raise ValueError("Cannot formulate a retrieval query for this incident.")

    # Step 1: Semantic retrieval
    retrieved_chunks = search_chunks(
        query=query,
        top_k=top_k,
        score_threshold=score_threshold,
        vector_store_path=vector_store_path,
        collection_name=collection_name,
        model_name=embedding_model_name,
    )

    # Step 2: Empty retrieval guard - do not call LLM
    if not retrieved_chunks:
        logger.info("No knowledge base chunks retrieved for incident; returning fallback investigation.")
        attack_types = ", ".join(list(_get_attr(incident, "attack_types", []))) or ", ".join(list(_get_attr(incident, "distinct_attack_types", []))) or "Unknown"
        fallback_report = IncidentInvestigation(
            executive_summary=FALLBACK_INVESTIGATION_SUMMARY,
            observed_evidence=[
                f"Correlated Alert Count: {_get_attr(incident, 'alert_count', len(alerts))}",
                f"Attack Types: {attack_types}",
                f"Deterministic Risk Score: {_get_attr(incident, 'risk_score', 'N/A')}",
            ],
            threat_context=[],
            investigation_priorities=[
                "Review perimeter firewall and netflow logs for involved IPs.",
                "Verify service availability and connection status on destination IPs.",
            ],
            recommended_actions=[
                "Perform manual log inspection for event timeframe.",
            ],
            mitigations=[
                "Apply standard port filtering policies.",
            ],
            mitre_context=[],
            limitations=[
                "No matching knowledge base sources were retrieved for this query.",
                "Investigation relies exclusively on observed alert facts.",
            ],
        )
        return fallback_report, []

    # Step 3: Context construction
    context_str, used_chunks = construct_context(retrieved_chunks, max_chars=max_context_chars)
    if not context_str or not used_chunks:
        logger.info("Constructed context is empty; returning fallback investigation.")
        fallback_report = IncidentInvestigation(
            executive_summary=FALLBACK_INVESTIGATION_SUMMARY,
            observed_evidence=[
                f"Correlated Alert Count: {_get_attr(incident, 'alert_count', len(alerts))}",
            ],
            threat_context=[],
            investigation_priorities=["Inspect network flow logs."],
            recommended_actions=["Verify target service status."],
            mitigations=["Maintain firewall filtering."],
            mitre_context=[],
            limitations=["Context character budget exceeded or empty."],
        )
        return fallback_report, []

    # Step 4: Prompt construction
    prompt = build_incident_investigation_prompt(incident, context_str, alerts=alerts)
    sources = build_sources_list(used_chunks)

    # Step 5: LLM generation
    provider = llm_client or GeminiProvider()
    raw_response = provider.generate(prompt=prompt, system_instruction=INCIDENT_INVESTIGATOR_SYSTEM_PROMPT)

    # Step 6: Parse response into structured Investigation object
    investigation = parse_investigation_response(raw_response, incident, alerts=alerts)

    return investigation, sources
