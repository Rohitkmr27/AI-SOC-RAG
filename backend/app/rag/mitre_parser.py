"""Deterministically convert selected MITRE ATT&CK STIX objects to Markdown."""

import json
import re
from pathlib import Path
from typing import Any


MITRE_OBJECT_TYPES = {
    "attack-pattern": "techniques",
    "x-mitre-tactic": "tactics",
    "intrusion-set": "groups",
    "malware": "software",
    "tool": "software",
    "course-of-action": "mitigations",
}


def _safe_name(value: str) -> str:
    return re.sub(r"[^a-zA-Z0-9._-]+", "_", value).strip("._") or "object"


def _clean_text(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    return value.replace("\r\n", "\n").strip()


def _markdown_for_object(obj: dict[str, Any]) -> str:
    object_type = obj.get("type", "unknown")
    name = _clean_text(obj.get("name")) or obj.get("id", "Unnamed object")
    lines = [f"# {name}", "", f"- STIX type: `{object_type}`", f"- STIX ID: `{obj.get('id', '')}`"]
    for field in ("external_references", "kill_chain_phases", "aliases", "x_mitre_platforms"):
        value = obj.get(field)
        if value:
            lines.extend([f"", f"## {field.replace('_', ' ').title()}", "", "```json", json.dumps(value, ensure_ascii=True, sort_keys=True, indent=2), "```"])
    for heading, field in (("Description", "description"), ("Detection", "x_mitre_detection")):
        value = _clean_text(obj.get(field))
        if value:
            lines.extend(["", f"## {heading}", "", value])
    return "\n".join(lines).strip() + "\n"


def parse_enterprise_attack(source_path: Path, output_directory: Path) -> int:
    """Write one stable Markdown document per useful ATT&CK object."""
    with source_path.open(encoding="utf-8") as stream:
        bundle = json.load(stream)
    objects = bundle.get("objects")
    if not isinstance(objects, list):
        raise ValueError("MITRE STIX dataset does not contain an objects list.")

    output_directory.mkdir(parents=True, exist_ok=True)
    for existing in output_directory.glob("*.md"):
        existing.unlink()
    selected = [
        obj for obj in objects
        if isinstance(obj, dict) and obj.get("type") in MITRE_OBJECT_TYPES and obj.get("id")
    ]
    selected.sort(key=lambda obj: (str(obj["type"]), str(obj["id"])))
    for obj in selected:
        category = MITRE_OBJECT_TYPES[obj["type"]]
        target = output_directory / f"{category}-{_safe_name(str(obj['id']))}.md"
        target.write_text(_markdown_for_object(obj), encoding="utf-8", newline="\n")
    return len(selected)