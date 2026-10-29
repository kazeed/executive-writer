"""Mechanical document checks, never factual verification or Markdown rendering."""

import re

from executive_writer.workflow.models import DocumentBrief, DocumentDraft, EvidenceSet


def _headings(body: str) -> set[str]:
    headings: set[str] = set()
    fence_character: str | None = None
    fence_length = 0
    for line in body.splitlines():
        fence = re.match(r"^ {0,3}(`{3,}|~{3,})(.*)$", line)
        if fence:
            marker, suffix = fence.groups()
            if fence_character is None:
                fence_character, fence_length = marker[0], len(marker)
            elif (
                marker[0] == fence_character and len(marker) >= fence_length and not suffix.strip()
            ):
                fence_character = None
            continue
        if fence_character is not None:
            continue
        match = re.match(r"^ {0,3}#{1,6}[ \t]+(.+?)[ \t]*$", line)
        if match:
            title = re.sub(r"[ \t]+#+$", "", match.group(1)).strip().casefold()
            headings.add(title)
    return headings


def check_draft(
    brief: DocumentBrief, draft: DocumentDraft, evidence: EvidenceSet | None
) -> tuple[str, ...]:
    limitations: list[str] = []
    if not draft.body.strip():
        limitations.append("Draft body is blank.")
    if brief.constraints.max_words is not None and (
        len(draft.body.split()) > brief.constraints.max_words
    ):
        limitations.append("Draft exceeds its word limit.")
    # Deliberately narrow: ATX headings outside fenced blocks. This is not a
    # Markdown renderer and does not validate document meaning or factual truth.
    headings = _headings(draft.body)
    if any(section.casefold() not in headings for section in brief.constraints.required_sections):
        limitations.append("Draft is missing required section headings.")
    available: set[str] = {item.evidence_id for item in evidence.evidence} if evidence else set()
    if any(citation.evidence_id not in available for citation in draft.citations):
        limitations.append("Draft cites unavailable evidence; support is not verified.")
    return tuple(limitations)
