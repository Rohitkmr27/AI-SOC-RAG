"""Stage 6: IDS Alert Intelligence and RAG Alert Enrichment."""

import json
import logging
import re
from pathlib import Path
from typing import Any

from app.alerts.schemas import AlertAnalysis
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

ALERT_ANALYST_SYSTEM_PROMPT = (
    "You are a cybersecurity SOC analyst assistant.\n"
    "Use only the supplied alert and retrieved cybersecurity knowledge.\n"
    "Do not invent facts, attack attribution, indicators, incidents, or sources.\n"
    "Explain what the alert represents based on the supplied information.\n"
    "Clearly distinguish:\n"
    "- observed alert facts\n"
    "- relevant security knowledge\n"
    "- recommended investigation steps\n"
    "If the retrieved context is insufficient, say so.\n"
    "Do not claim that the alert proves a successful attack.\n"
    "Do not invent MITRE technique IDs unless they are present in the retrieved context."
)

FALLBACK_ENRICHMENT_SUMMARY = (
    "I could not find sufficient information in the security knowledge base to enrich this alert."
)


def _get_alert_attr(alert: Any, key: str, default: Any = "") -> Any:
    """Safely extract an attribute from either an object or a dictionary."""
    if isinstance(alert, dict):
        return alert.get(key, default)
    return getattr(alert, key, default)


def build_alert_retrieval_query(alert: Any) -> str:
    """Construct a focused cybersecurity search query from alert attributes."""
    attack_type = str(_get_alert_attr(alert, "attack_type", "")).strip()
    protocol = str(_get_alert_attr(alert, "protocol", "")).strip()
    destination_port = str(_get_alert_attr(alert, "destination_port", "")).strip()
    source_port = str(_get_alert_attr(alert, "source_port", "")).strip()

    query_parts: list[str] = []
    if attack_type:
        query_parts.append(attack_type)
    if protocol:
        query_parts.append(protocol)
    if destination_port:
        query_parts.append(f"destination port {destination_port}")
    if source_port:
        query_parts.append(f"source port {source_port}")

    query_parts.append("detection investigation mitigation")

    query = " ".join(query_parts).strip()
    return re.sub(r"\s+", " ", query)


def build_alert_analyst_prompt(alert: Any, context: str) -> str:
    """Build user prompt containing structured alert facts and retrieved context."""
    timestamp = str(_get_alert_attr(alert, "timestamp", "N/A"))
    attack_type = str(_get_alert_attr(alert, "attack_type", "Unknown"))
    severity = str(_get_alert_attr(alert, "severity", "N/A"))
    confidence = str(_get_alert_attr(alert, "confidence", "N/A"))
    protocol = str(_get_alert_attr(alert, "protocol", "Unknown"))
    source_ip = str(_get_alert_attr(alert, "source_ip", "N/A"))
    destination_ip = str(_get_alert_attr(alert, "destination_ip", "N/A"))
    source_port = str(_get_alert_attr(alert, "source_port", "N/A"))
    destination_port = str(_get_alert_attr(alert, "destination_port", "N/A"))
    description = str(_get_alert_attr(alert, "description", "N/A"))

    return (
        "OBSERVED SECURITY ALERT:\n"
        "----------------------------------------\n"
        f"- Timestamp: {timestamp}\n"
        f"- Attack Type: {attack_type}\n"
        f"- Severity: {severity}\n"
        f"- Model Confidence: {confidence}\n"
        f"- Protocol: {protocol}\n"
        f"- Source IP: {source_ip}\n"
        f"- Destination IP: {destination_ip}\n"
        f"- Source Port: {source_port}\n"
        f"- Destination Port: {destination_port}\n"
        f"- Description: {description}\n"
        "----------------------------------------\n\n"
        "RETRIEVED CYBERSECURITY KNOWLEDGE:\n"
        "----------------------------------------\n"
        f"{context}\n"
        "----------------------------------------\n\n"
        "INSTRUCTIONS:\n"
        "As a SOC analyst assistant, analyze this alert using ONLY the supplied alert facts "
        "and retrieved cybersecurity knowledge. Do not invent facts, attribution, or unverified MITRE IDs.\n"
        "Format your entire response as a valid JSON object with the following keys:\n"
        '{\n'
        '  "summary": "Concise summary explaining what the alert represents based on supplied info",\n'
        '  "observed_indicators": ["List of observed indicators and facts from the alert"],\n'
        '  "security_context": ["List of relevant cybersecurity knowledge facts derived strictly from context"],\n'
        '  "investigation_steps": ["Concrete triage and verification steps for the analyst"],\n'
        '  "recommended_mitigations": ["Recommended containment or mitigation steps supported by context"]\n'
        '}\n'
        "Return ONLY the JSON object. Do not include markdown code block syntax or extra text outside the JSON."
    )


def _clean_json_text(text: str) -> str:
    """Strip markdown code block fences if the LLM wraps JSON in them."""
    cleaned = text.strip()
    if cleaned.startswith("```json"):
        cleaned = cleaned[7:]
    elif cleaned.startswith("```"):
        cleaned = cleaned[3:]
    if cleaned.endswith("```"):
        cleaned = cleaned[:-3]
    return cleaned.strip()


def parse_analyst_response(raw_text: str, alert: Any) -> AlertAnalysis:
    """Robustly parse the LLM's response into an AlertAnalysis model."""
    cleaned = _clean_json_text(raw_text)

    # Attempt 1: Direct JSON parsing
    try:
        data = json.loads(cleaned)
        if isinstance(data, dict):
            summary = str(data.get("summary", "")).strip() or "Alert analysis completed."
            observed_indicators = [
                str(item).strip() for item in data.get("observed_indicators", []) if str(item).strip()
            ]
            security_context = [
                str(item).strip() for item in data.get("security_context", []) if str(item).strip()
            ]
            investigation_steps = [
                str(item).strip() for item in data.get("investigation_steps", []) if str(item).strip()
            ]
            recommended_mitigations = [
                str(item).strip() for item in data.get("recommended_mitigations", []) if str(item).strip()
            ]

            return AlertAnalysis(
                summary=summary,
                observed_indicators=observed_indicators,
                security_context=security_context,
                investigation_steps=investigation_steps,
                recommended_mitigations=recommended_mitigations,
            )
    except (json.JSONDecodeError, TypeError) as exc:
        logger.warning("LLM response was not valid JSON; falling back to heuristic parsing: %s", exc)

    # Attempt 2: Heuristic section extraction for markdown/text formatting
    summary_match = re.search(r"(?:###?\s*Summary|Summary:?)\s*(.*?)(?=(?:###?\s*[A-Z]|Observed Indicators|Security Context|Investigation|Recommended|\Z))", raw_text, re.DOTALL | re.IGNORECASE)
    summary = summary_match.group(1).strip() if summary_match else raw_text.strip()[:500]

    attack_type = str(_get_alert_attr(alert, "attack_type", "Unknown"))
    protocol = str(_get_alert_attr(alert, "protocol", "Unknown"))
    destination_port = str(_get_alert_attr(alert, "destination_port", "Unknown"))

    default_indicators = [
        f"Attack Type: {attack_type}",
        f"Protocol: {protocol}",
        f"Destination Port: {destination_port}",
    ]

    return AlertAnalysis(
        summary=summary or "Alert analysis generated from retrieved context.",
        observed_indicators=default_indicators,
        security_context=[],
        investigation_steps=[
            "Review firewall and network session logs corresponding to the alert timestamp.",
            "Verify whether the destination service is actively listening on the target port.",
        ],
        recommended_mitigations=[
            "Ensure defense-in-depth perimeter rules restrict unexpected incoming traffic.",
        ],
    )


def enrich_alert(
    alert: Any,
    top_k: int = DEFAULT_RAG_TOP_K,
    score_threshold: float | None = DEFAULT_RAG_SCORE_THRESHOLD,
    max_context_chars: int = DEFAULT_RAG_MAX_CONTEXT_CHARS,
    llm_client: LLMProvider | None = None,
    vector_store_path: Path = DEFAULT_VECTOR_STORE_DIRECTORY,
    collection_name: str = DEFAULT_COLLECTION_NAME,
    embedding_model_name: str = DEFAULT_EMBEDDING_MODEL,
) -> tuple[AlertAnalysis, list[RAGSource]]:
    """Enrich an alert using RAG retrieval and grounded SOC analyst generation."""
    query = build_alert_retrieval_query(alert)
    if not query:
        raise ValueError("Cannot formulate a retrieval query from the supplied alert.")

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
        logger.info("No knowledge base chunks retrieved for alert; returning fallback analysis.")
        fallback_analysis = AlertAnalysis(
            summary=FALLBACK_ENRICHMENT_SUMMARY,
            observed_indicators=[
                f"Attack Type: {_get_alert_attr(alert, 'attack_type', 'Unknown')}",
                f"Protocol: {_get_alert_attr(alert, 'protocol', 'Unknown')}",
                f"Destination Port: {_get_alert_attr(alert, 'destination_port', 'Unknown')}",
                f"Severity: {_get_alert_attr(alert, 'severity', 'Unknown')}",
            ],
            security_context=[],
            investigation_steps=[
                "Verify packet captures and network flow logs for the reported traffic.",
                "Check whether the destination host was responsive during the event window.",
            ],
            recommended_mitigations=[
                "Enforce network perimeter filtering for unneeded ports.",
            ],
        )
        return fallback_analysis, []

    # Step 3: Context construction
    context_str, used_chunks = construct_context(retrieved_chunks, max_chars=max_context_chars)
    if not context_str or not used_chunks:
        logger.info("Constructed context is empty; returning fallback analysis.")
        fallback_analysis = AlertAnalysis(
            summary=FALLBACK_ENRICHMENT_SUMMARY,
            observed_indicators=[
                f"Attack Type: {_get_alert_attr(alert, 'attack_type', 'Unknown')}",
            ],
            security_context=[],
            investigation_steps=["Verify flow logs for anomalous activity."],
            recommended_mitigations=["Review firewall filtering policies."],
        )
        return fallback_analysis, []

    # Step 4: Prompt construction
    prompt = build_alert_analyst_prompt(alert, context_str)
    sources = build_sources_list(used_chunks)

    # Step 5: LLM generation
    provider = llm_client or GeminiProvider()
    raw_response = provider.generate(prompt=prompt, system_instruction=ALERT_ANALYST_SYSTEM_PROMPT)

    # Step 6: Parse structured response
    analysis = parse_analyst_response(raw_response, alert)

    return analysis, sources
