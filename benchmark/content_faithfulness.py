#!/usr/bin/env python3
"""Source Coverage & Hallucination / Faithfulness Analyzer for wiki-ingest.

Solves two core problems of LLM reasoning:
  1. Coverage (Tránh bỏ sót): Measures how thoroughly the generated wiki pages
     cover the contents, sections, facts, and metrics of the source document.
  2. Faithfulness / Hallucination Detection (Tránh bịa đặt): Flags statements,
     entities, metrics, or claims in the wiki that have NO grounding in the source.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# Regex utilities
SECTION_RE = re.compile(r"^(#{1,4})\s+(.+)$", re.M)
NUM_METRIC_RE = re.compile(r"\b(\d+(?:\.\d+)?(?:\s*(?:ms|tps|s|giây|lần|%|token|px|mb|gb|kb))?)\b", re.I)
TECH_TERM_RE = re.compile(r"`([^`]+)`|\b([A-Z][a-zA-Z0-9]+(?:[A-Z][a-z0-9]+)+)\b|\b([A-Z]{2,})\b")
CLAIM_LINE_RE = re.compile(r"^\s*[-*]\s+(.+)$", re.M)
SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?\n])\s+")


@dataclass
class CoverageResult:
    coverage_score: float  # 0.0 - 100.0%
    total_source_units: int
    covered_units_count: int
    covered_units: list[str] = field(default_factory=list)
    missed_units: list[str] = field(default_factory=list)
    missed_sections: list[str] = field(default_factory=list)
    section_coverage_rate: float = 100.0


@dataclass
class FaithfulnessResult:
    faithfulness_score: float  # 0.0 - 100.0%
    total_wiki_claims: int
    grounded_claims_count: int
    ungrounded_claims: list[dict[str, Any]] = field(default_factory=list)  # {claim, file, reason, severity}
    unseen_terms: list[str] = field(default_factory=list)  # terms in wiki but never in source
    unseen_numbers: list[str] = field(default_factory=list)  # metrics in wiki but never in source
    hallucination_penalties: int = 0


def normalize_token(s: str) -> str:
    return re.sub(r"[^a-zA-Z0-9àáạảãâầấậẩẫăằắặẳẵèéẹẻẽêềếệểễìíịỉĩòóọỏõôồốộổỗơờớợởỡùúụủũưừứựửữỳýỵỷỹđ]", "", s.lower())


def extract_source_information_units(source_text: str) -> dict[str, Any]:
    """Decompose source document into verifiable information units."""
    sections = []
    for m in SECTION_RE.finditer(source_text):
        level = len(m.group(1))
        title = m.group(2).strip()
        sections.append({"level": level, "title": title})

    # Numbers and metrics
    numbers = set()
    for m in NUM_METRIC_RE.finditer(source_text):
        token = m.group(1).strip()
        if len(token) > 1 or token.isdigit():
            numbers.add(token.lower())

    # Technical terms and identifiers
    terms = set()
    for m in TECH_TERM_RE.finditer(source_text):
        for g in m.groups():
            if g and len(g.strip()) > 2:
                terms.add(g.strip().lower())

    # Significant paragraphs / key sentences
    paragraphs = [p.strip() for p in source_text.split("\n\n") if p.strip() and not p.strip().startswith("#")]

    return {
        "sections": sections,
        "numbers": sorted(numbers),
        "terms": sorted(terms),
        "paragraphs": paragraphs,
    }


def analyze_source_coverage(
    source_text: str,
    wiki_pages_content: dict[str, str],
    checkpoint_rules: list[dict[str, Any]] | None = None,
) -> CoverageResult:
    """Measure how thoroughly wiki pages cover the source document."""
    units = extract_source_information_units(source_text)
    combined_wiki_text = "\n".join(wiki_pages_content.values()).lower()

    covered_units = []
    missed_units = []

    # 1. Check section coverage
    missed_sections = []
    for sec in units["sections"]:
        sec_title = sec["title"]
        # Skip top-level document title
        if sec["level"] == 1:
            continue
        # Extract keywords from section title
        kw_list = [w for w in re.findall(r"\w+", sec_title) if len(w) > 3]
        if not kw_list:
            continue
        matches = sum(1 for kw in kw_list if kw.lower() in combined_wiki_text)
        if matches / len(kw_list) < 0.4:
            missed_sections.append(sec_title)

    # 2. Check metrics and numbers coverage
    for num in units["numbers"]:
        # Clean unit
        num_clean = num.replace(" ", "")
        if num_clean in combined_wiki_text.replace(" ", ""):
            covered_units.append(f"Metric: {num}")
        else:
            missed_units.append(f"Metric: {num}")

    # 3. Check technical terms coverage
    for term in units["terms"]:
        if term in combined_wiki_text:
            covered_units.append(f"Tech Term: {term}")
        else:
            missed_units.append(f"Tech Term: {term}")

    # 4. Check explicit golden checkpoints if provided
    if checkpoint_rules:
        for cp in checkpoint_rules:
            pattern = cp.get("pattern", "")
            desc = cp.get("description", pattern)
            if re.search(pattern, combined_wiki_text, re.I):
                covered_units.append(f"Checkpoint: {desc}")
            else:
                missed_units.append(f"Checkpoint: {desc}")

    total = len(covered_units) + len(missed_units)
    coverage_score = round((len(covered_units) / max(1, total)) * 100, 2)
    sec_rate = round(
        ((len(units["sections"]) - len(missed_sections)) / max(1, len(units["sections"]))) * 100, 2
    )

    return CoverageResult(
        coverage_score=coverage_score,
        total_source_units=total,
        covered_units_count=len(covered_units),
        covered_units=covered_units,
        missed_units=missed_units,
        missed_sections=missed_sections,
        section_coverage_rate=sec_rate,
    )


def analyze_faithfulness(
    source_text: str,
    wiki_pages_content: dict[str, str],
    forbidden_hallucinations: list[str] | None = None,
) -> FaithfulnessResult:
    """Detect ungrounded content, extraneous knowledge, or fabricated claims in wiki."""
    source_lower = source_text.lower()
    source_units = extract_source_information_units(source_text)
    source_numbers = set(source_units["numbers"])
    source_terms = set(source_units["terms"])

    total_claims = 0
    grounded_count = 0
    ungrounded_claims = []
    unseen_terms = set()
    unseen_numbers = set()

    for page_slug, content in wiki_pages_content.items():
        # Extract claims (bullet points in Summary, Key Facts, Key Claims, Overview, Context, Examples)
        lines = content.splitlines()
        for idx, line in enumerate(lines):
            line_str = line.strip()
            if not line_str.startswith("-") and not line_str.startswith("*"):
                continue

            claim_text = line_str.lstrip("-* ").strip()
            # Skip structural or empty items
            if len(claim_text) < 15 or claim_text.startswith("[[") and len(claim_text.split()) < 3:
                continue

            total_claims += 1

            # Check 1: Forbidden Hallucinations
            if forbidden_hallucinations:
                for fh in forbidden_hallucinations:
                    if re.search(re.escape(fh), claim_text, re.I):
                        ungrounded_claims.append({
                            "claim": claim_text,
                            "file": page_slug,
                            "line": idx + 1,
                            "reason": f"Chứa thuật ngữ ảo giác cấm: '{fh}'",
                            "severity": "CRITICAL",
                        })
                        break

            # Check 2: Numbers in claim that never appear in source
            claim_nums = {
                m.group(1).lower().replace(" ", "")
                for m in NUM_METRIC_RE.finditer(claim_text)
                if len(m.group(1)) > 1 or m.group(1).isdigit()
            }
            fabricated_nums = [
                n for n in claim_nums if not any(n in sn.replace(" ", "") for sn in source_numbers)
            ]
            if fabricated_nums:
                for fn in fabricated_nums:
                    unseen_numbers.add(fn)
                ungrounded_claims.append({
                    "claim": claim_text,
                    "file": page_slug,
                    "line": idx + 1,
                    "reason": f"Chứa số liệu ngoại lai không có trong source: {fabricated_nums}",
                    "severity": "HIGH",
                })
                continue

            # Check 3: Technical identifiers not present in source
            claim_terms = {
                m.group(0).strip().lower()
                for m in TECH_TERM_RE.finditer(claim_text)
                if len(m.group(0).strip()) > 2
            }
            foreign_terms = [
                t for t in claim_terms if t not in source_lower and not any(t in st for st in source_terms)
            ]
            if foreign_terms:
                for ft in foreign_terms:
                    unseen_terms.add(ft)
                ungrounded_claims.append({
                    "claim": claim_text,
                    "file": page_slug,
                    "line": idx + 1,
                    "reason": f"Chứa thuật ngữ kỹ thuật không có trong source: {foreign_terms}",
                    "severity": "MEDIUM",
                })
                continue

            # Check 4: Lexical n-gram overlap check against source
            # Extract content words (ignoring stopwords and punctuation)
            words = [w.lower() for w in re.findall(r"\w+", claim_text) if len(w) > 3]
            if len(words) >= 4:
                # Find maximum word overlap in any paragraph of source
                max_overlap = 0.0
                for p in source_units["paragraphs"]:
                    p_lower = p.lower()
                    overlap = sum(1 for w in words if w in p_lower) / len(words)
                    if overlap > max_overlap:
                        max_overlap = overlap
                if max_overlap < 0.25:
                    ungrounded_claims.append({
                        "claim": claim_text,
                        "file": page_slug,
                        "line": idx + 1,
                        "reason": f"Độ tương đồng ngữ nghĩa với source quá thấp ({round(max_overlap*100, 1)}%) - nghi vấn kiến thức ngoại lai",
                        "severity": "LOW",
                    })
                    continue

            grounded_count += 1

    total_valid = max(1, total_claims)
    penalties = len([c for c in ungrounded_claims if c["severity"] == "CRITICAL"]) * 30 + \
                len([c for c in ungrounded_claims if c["severity"] == "HIGH"]) * 15 + \
                len([c for c in ungrounded_claims if c["severity"] == "MEDIUM"]) * 5

    faithfulness_score = max(0.0, round(((grounded_count / total_valid) * 100) - (penalties * 0.5), 2))

    return FaithfulnessResult(
        faithfulness_score=faithfulness_score,
        total_wiki_claims=total_claims,
        grounded_claims_count=grounded_count,
        ungrounded_claims=ungrounded_claims,
        unseen_terms=sorted(unseen_terms),
        unseen_numbers=sorted(unseen_numbers),
        hallucination_penalties=penalties,
    )
