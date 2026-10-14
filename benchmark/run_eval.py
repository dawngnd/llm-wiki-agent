#!/usr/bin/env python3
"""Unified Test & Benchmark CLI for wiki-ingest skill.

Allows developers and agents to:
  1. Evaluate a single wiki ingest run against quality checklists & golden truth.
  2. Benchmark multiple runs to measure reasoning drift, slug fragmentation, and stability.
  3. Prepare isolated sandboxes for repeatable testing.

Usage:
  # Evaluate single run:
  python3 benchmark/run_eval.py --eval /path/to/wiki_dir --fixture banking-drift-test.md

  # Benchmark multiple runs for drift:
  python3 benchmark/run_eval.py --compare /tmp/run1 /tmp/run2 /tmp/run3 --report report.md

  # Initialize clean sandboxes for 3 test runs:
  python3 benchmark/run_eval.py --init-sandbox /tmp/my_test --runs 3
"""

from __future__ import annotations

import argparse
import difflib
import json
import re
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

from content_faithfulness import (
    analyze_source_coverage,
    analyze_faithfulness,
    CoverageResult,
    FaithfulnessResult,
)

WIKILINK_RE = re.compile(r"\[\[([a-z0-9\-_]+)\]\]")
FM_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)
VIETNAMESE_RE = re.compile(r"[àáạảãâầấậẩẫăằắặẳẵèéẹẻẽêềếệểễìíịỉĩòóọỏõôồốộổỗơờớợởỡùúụủũưừứựửữỳýỵỷỹđ]", re.I)


@dataclass
class PageInfo:
    slug: str
    rel_path: str
    page_type: str  # sources, entities, concepts, synthesis
    title: str = ""
    frontmatter: dict[str, Any] = field(default_factory=dict)
    wikilinks: set[str] = field(default_factory=set)
    headers: list[str] = field(default_factory=list)
    bilingual_headers: list[str] = field(default_factory=list)
    has_vietnamese: bool = False
    has_required_sections: bool = False
    raw_content: str = ""
    key_claims: list[str] = field(default_factory=list)


@dataclass
class RunProfile:
    run_id: str
    run_dir: Path
    wiki_dir: Path
    pages: dict[str, PageInfo] = field(default_factory=dict)
    sources: set[str] = field(default_factory=set)
    entities: set[str] = field(default_factory=set)
    concepts: set[str] = field(default_factory=set)
    synthesis: set[str] = field(default_factory=set)
    broken_links: list[tuple[str, str]] = field(default_factory=list)
    graph_edges: set[tuple[str, str]] = field(default_factory=set)
    checklist_score: float = 0.0
    checklist_results: dict[str, Any] = field(default_factory=dict)


def parse_frontmatter(content: str) -> tuple[dict[str, Any], str]:
    fm_match = FM_RE.match(content)
    if not fm_match:
        return {}, content
    fm_raw = fm_match.group(1)
    body = content[fm_match.end():]
    data: dict[str, Any] = {}
    for line in fm_raw.splitlines():
        if ":" in line:
            key, val = line.split(":", 1)
            key = key.strip()
            val = val.strip().strip("\"'")
            if val.startswith("[") and val.endswith("]"):
                items = [x.strip().strip("\"'") for x in val[1:-1].split(",") if x.strip()]
                data[key] = items
            else:
                data[key] = val
    return data, body


def inspect_page(path: Path, wiki_dir: Path) -> PageInfo:
    content = path.read_text(encoding="utf-8", errors="replace")
    slug = path.stem
    rel_path = str(path.relative_to(wiki_dir))
    parts = rel_path.split("/")
    page_type = parts[0] if len(parts) > 1 else "unknown"

    fm, body = parse_frontmatter(content)
    title = str(fm.get("title", ""))

    wikilinks = set(WIKILINK_RE.findall(content))
    headers = [ln.strip() for ln in content.splitlines() if ln.startswith("#")]
    bilingual = [h for h in headers if "(" in h and ")" in h]
    has_vi = bool(VIETNAMESE_RE.search(content))

    has_req = True
    if page_type == "entities":
        has_req = any("Ngữ cảnh" in h or "Context" in h for h in headers)
    elif page_type == "concepts":
        has_req = any("Ví dụ" in h or "Example" in h for h in headers)
    elif page_type == "sources":
        has_req = any("Key Claims" in h or "Khẳng định" in h for h in headers)

    key_claims = []
    if page_type == "sources":
        in_claims = False
        for line in body.splitlines():
            if re.match(r"^#{1,3}\s+.*(Claims|Khẳng định|Takeaways)", line, re.I):
                in_claims = True
                continue
            if in_claims:
                if line.startswith("#"):
                    break
                if line.strip().startswith("-") or line.strip().startswith("*"):
                    key_claims.append(line.strip().lstrip("-* ").strip())

    return PageInfo(
        slug=slug,
        rel_path=rel_path,
        page_type=page_type,
        title=title,
        frontmatter=fm,
        wikilinks=wikilinks,
        headers=headers,
        bilingual_headers=bilingual,
        has_vietnamese=has_vi,
        has_required_sections=has_req,
        raw_content=content,
        key_claims=key_claims,
    )


def profile_run(run_dir: Path) -> RunProfile:
    wiki_dir = run_dir / "wiki" if (run_dir / "wiki").is_dir() else run_dir
    run_id = run_dir.name
    profile = RunProfile(run_id=run_id, run_dir=run_dir, wiki_dir=wiki_dir)

    all_pages = {}
    for sub in ["sources", "entities", "concepts", "synthesis"]:
        sub_dir = wiki_dir / sub
        if sub_dir.is_dir():
            for p in sorted(sub_dir.glob("*.md")):
                page_info = inspect_page(p, wiki_dir)
                all_pages[page_info.slug] = page_info
                if sub == "sources":
                    profile.sources.add(page_info.slug)
                elif sub == "entities":
                    profile.entities.add(page_info.slug)
                elif sub == "concepts":
                    profile.concepts.add(page_info.slug)
                elif sub == "synthesis":
                    profile.synthesis.add(page_info.slug)

    profile.pages = all_pages

    # Check broken links & graph edges
    all_slugs = set(all_pages.keys()) | {"index", "log"}
    for page_slug, page_info in all_pages.items():
        for target in page_info.wikilinks:
            profile.graph_edges.add((page_slug, target))
            if target not in all_slugs:
                profile.broken_links.append((page_slug, target))

    # Evaluate Quality Checklist against SKILL.md & references/ingest-checklist.md
    checks = {}
    total_pages = len(all_pages)
    if total_pages > 0:
        checks["frontmatter_present"] = {
            "passed": all(bool(p.frontmatter) for p in all_pages.values()),
            "detail": f"{sum(1 for p in all_pages.values() if p.frontmatter)}/{total_pages} pages have frontmatter",
            "weight": 15,
        }
        checks["type_field_match"] = {
            "passed": all(p.frontmatter.get("type") == p.page_type for p in all_pages.values()),
            "detail": "type matches directory name (sources/entities/concepts)",
            "weight": 15,
        }
        bilingual_count = sum(len(p.bilingual_headers) for p in all_pages.values())
        total_headers = max(1, sum(len(p.headers) for p in all_pages.values()))
        checks["bilingual_headers"] = {
            "passed": (bilingual_count / total_headers) >= 0.7,
            "detail": f"{bilingual_count}/{total_headers} headers are bilingual ({round(bilingual_count/total_headers*100, 1)}%)",
            "weight": 15,
        }
        checks["vietnamese_language"] = {
            "passed": all(p.has_vietnamese for p in all_pages.values()),
            "detail": "Vietnamese characters detected in all markdown bodies",
            "weight": 10,
        }
        checks["required_sections"] = {
            "passed": all(p.has_required_sections for p in all_pages.values()),
            "detail": "Entities have ## Context, Concepts have ## Examples, Sources have ## Key Claims",
            "weight": 15,
        }
        checks["zero_broken_links"] = {
            "passed": len(profile.broken_links) == 0,
            "detail": f"{len(profile.broken_links)} broken links found",
            "weight": 20,
        }
        checks["has_index"] = {
            "passed": (wiki_dir / "index.md").is_file(),
            "detail": "wiki/index.md exists",
            "weight": 5,
        }
        checks["has_log"] = {
            "passed": (wiki_dir / "log.md").is_file(),
            "detail": "wiki/log.md exists",
            "weight": 5,
        }
    else:
        checks["wiki_empty"] = {"passed": False, "detail": "No wiki pages found", "weight": 0}

    total_weight = sum(v.get("weight", 0) for v in checks.values())
    earned_weight = sum(v.get("weight", 0) for v in checks.values() if v.get("passed", False))
    profile.checklist_score = round((earned_weight / total_weight) * 100, 2) if total_weight else 0.0
    profile.checklist_results = checks

    return profile


def evaluate_against_golden(
    profile: RunProfile,
    fixture_name: str,
    golden_data: dict[str, Any],
    source_text: str = "",
) -> dict[str, Any]:
    """Check recall against golden ground truth expectations, coverage, and faithfulness."""
    fixture_spec = golden_data.get("fixtures", {}).get(fixture_name, {})
    if not fixture_spec:
        return {"error": f"Fixture '{fixture_name}' not defined in expected_golden.json"}

    all_slugs = set(profile.pages.keys())
    all_content = "\n".join(p.raw_content for p in profile.pages.values())
    pages_dict = {p.slug: p.raw_content for p in profile.pages.values()}

    # Check required entities (allowing aliases)
    req_entities = fixture_spec.get("required_entities", [])
    entity_aliases = fixture_spec.get("entity_aliases", {})
    matched_entities = []
    missing_entities = []
    for ent in req_entities:
        candidates = [ent] + entity_aliases.get(ent, [])
        found = any(c.replace("-", "") in [s.replace("-", "") for s in profile.entities] for c in candidates)
        if found:
            matched_entities.append(ent)
        else:
            missing_entities.append(ent)

    # Check required concepts
    req_concepts = fixture_spec.get("required_concepts", [])
    concept_aliases = fixture_spec.get("concept_aliases", {})
    matched_concepts = []
    missing_concepts = []
    for cpt in req_concepts:
        candidates = [cpt] + concept_aliases.get(cpt, [])
        found = any(c.replace("-", "") in [s.replace("-", "") for s in profile.concepts] for c in candidates)
        if found:
            matched_concepts.append(cpt)
        else:
            missing_concepts.append(cpt)

    # Check metrics
    req_metrics = fixture_spec.get("required_metrics", [])
    matched_metrics = []
    missing_metrics = []
    for m in req_metrics:
        patt = m["pattern"]
        if re.search(patt, all_content, re.I):
            matched_metrics.append(m["name"])
        else:
            missing_metrics.append(m["name"])

    # Check hallucinations
    forbidden = fixture_spec.get("forbidden_hallucinations", [])
    detected_hallucinations = [f for f in forbidden if re.search(re.escape(f), all_content, re.I)]

    # Check contradictions
    req_contra = fixture_spec.get("required_contradictions", [])
    matched_contra = [c for c in req_contra if re.search(re.escape(c), all_content, re.I)]

    entity_recall = len(matched_entities) / max(1, len(req_entities))
    concept_recall = len(matched_concepts) / max(1, len(req_concepts))
    metric_recall = len(matched_metrics) / max(1, len(req_metrics))
    hallucination_penalty = 25 if detected_hallucinations else 0

    ground_truth_score = round(
        max(0, (entity_recall * 40 + concept_recall * 40 + metric_recall * 20) - hallucination_penalty), 2
    )

    # 1. Source Coverage Analysis
    coverage_data = None
    if source_text:
        checkpoints = fixture_spec.get("coverage_checkpoints", [])
        cov_res = analyze_source_coverage(source_text, pages_dict, checkpoints)
        coverage_data = asdict(cov_res)

    # 2. Faithfulness & Hallucination Detection
    faithfulness_data = None
    if source_text:
        faith_res = analyze_faithfulness(source_text, pages_dict, forbidden)
        faithfulness_data = asdict(faith_res)

    return {
        "ground_truth_score": ground_truth_score,
        "entity_recall": round(entity_recall * 100, 1),
        "concept_recall": round(concept_recall * 100, 1),
        "metric_recall": round(metric_recall * 100, 1),
        "matched_entities": matched_entities,
        "missing_entities": missing_entities,
        "matched_concepts": matched_concepts,
        "missing_concepts": missing_concepts,
        "matched_metrics": matched_metrics,
        "missing_metrics": missing_metrics,
        "detected_hallucinations": detected_hallucinations,
        "matched_contradictions": matched_contra,
        "coverage": coverage_data,
        "faithfulness": faithfulness_data,
    }


def jaccard(s1: set, s2: set) -> float:
    if not s1 and not s2:
        return 1.0
    union = s1 | s2
    return len(s1 & s2) / len(union) if union else 0.0


def find_slug_aliases(all_slugs_by_run: dict[str, set[str]]) -> list[dict[str, Any]]:
    combined = sorted({slug for s in all_slugs_by_run.values() for slug in s})
    clusters: list[dict[str, Any]] = []
    seen = set()

    for i, s1 in enumerate(combined):
        if s1 in seen:
            continue
        group = [s1]
        for s2 in combined[i + 1:]:
            if s2 in seen:
                continue
            ratio = difflib.SequenceMatcher(None, s1.replace("-", ""), s2.replace("-", "")).ratio()
            tokens1 = set(s1.split("-"))
            tokens2 = set(s2.split("-"))
            token_j = len(tokens1 & tokens2) / len(tokens1 | tokens2) if (tokens1 | tokens2) else 0

            if ratio >= 0.75 or token_j >= 0.5:
                group.append(s2)
                seen.add(s2)
        if len(group) > 1:
            seen.add(s1)
            run_mapping = {}
            for g in group:
                run_mapping[g] = [r for r, slugs in all_slugs_by_run.items() if g in slugs]
            clusters.append({
                "variants": group,
                "distribution": run_mapping,
            })
    return clusters


def benchmark_multi_runs(
    run_dirs: list[Path],
    source_text: str = "",
    fixture_spec: dict[str, Any] | None = None,
) -> dict[str, Any]:
    profiles = [profile_run(d) for d in run_dirs]
    n_runs = len(profiles)

    entity_sets = {p.run_id: p.entities for p in profiles}
    concept_sets = {p.run_id: p.concepts for p in profiles}
    page_sets = {p.run_id: set(p.pages.keys()) for p in profiles}
    edge_sets = {p.run_id: {f"{u}->{v}" for u, v in p.graph_edges} for p in profiles}

    def pairwise_mean_jaccard(sets_dict: dict[str, set]) -> float:
        keys = list(sets_dict.keys())
        if len(keys) < 2:
            return 1.0
        scores = []
        for i in range(len(keys)):
            for j in range(i + 1, len(keys)):
                scores.append(jaccard(sets_dict[keys[i]], sets_dict[keys[j]]))
        return sum(scores) / len(scores) if scores else 1.0

    entity_jaccard = pairwise_mean_jaccard(entity_sets)
    concept_jaccard = pairwise_mean_jaccard(concept_sets)
    page_jaccard = pairwise_mean_jaccard(page_sets)
    edge_jaccard = pairwise_mean_jaccard(edge_sets)

    all_entities = set().union(*entity_sets.values()) if entity_sets else set()
    core_entities = set.intersection(*entity_sets.values()) if entity_sets else set()
    flaky_entities = all_entities - core_entities

    all_concepts = set().union(*concept_sets.values()) if concept_sets else set()
    core_concepts = set.intersection(*concept_sets.values()) if concept_sets else set()
    flaky_concepts = all_concepts - core_concepts

    entity_aliases = find_slug_aliases(entity_sets)
    concept_aliases = find_slug_aliases(concept_sets)

    mean_quality = sum(p.checklist_score for p in profiles) / n_runs if n_runs else 0.0

    # Coverage and Faithfulness per run
    coverage_by_run = {}
    faithfulness_by_run = {}
    all_missed_units = {}
    all_ungrounded_claims = []

    if source_text:
        checkpoints = fixture_spec.get("coverage_checkpoints", []) if fixture_spec else None
        forbidden = fixture_spec.get("forbidden_hallucinations", []) if fixture_spec else None
        for p in profiles:
            p_pages = {pg.slug: pg.raw_content for pg in p.pages.values()}
            c_res = analyze_source_coverage(source_text, p_pages, checkpoints)
            f_res = analyze_faithfulness(source_text, p_pages, forbidden)
            coverage_by_run[p.run_id] = c_res
            faithfulness_by_run[p.run_id] = f_res
            all_missed_units[p.run_id] = c_res.missed_units
            for ug in f_res.ungrounded_claims:
                all_ungrounded_claims.append({**ug, "run_id": p.run_id})

    mean_cov = (
        sum(c.coverage_score for c in coverage_by_run.values()) / n_runs
        if coverage_by_run
        else None
    )
    mean_faith = (
        sum(f.faithfulness_score for f in faithfulness_by_run.values()) / n_runs
        if faithfulness_by_run
        else None
    )

    # Balanced RSI formula incorporating Coverage & Faithfulness if available
    if mean_cov is not None and mean_faith is not None:
        rsi = (
            0.25 * entity_jaccard * 100
            + 0.25 * concept_jaccard * 100
            + 0.15 * edge_jaccard * 100
            + 0.15 * mean_quality
            + 0.10 * mean_cov
            + 0.10 * mean_faith
        )
    else:
        rsi = (
            0.30 * entity_jaccard * 100
            + 0.30 * concept_jaccard * 100
            + 0.20 * edge_jaccard * 100
            + 0.20 * mean_quality
        )

    runs_summary = []
    for p in profiles:
        c_item = coverage_by_run.get(p.run_id)
        f_item = faithfulness_by_run.get(p.run_id)
        runs_summary.append({
            "run_id": p.run_id,
            "pages_count": len(p.pages),
            "entities_count": len(p.entities),
            "concepts_count": len(p.concepts),
            "sources_count": len(p.sources),
            "broken_links_count": len(p.broken_links),
            "broken_links": p.broken_links,
            "quality_score": p.checklist_score,
            "coverage_score": c_item.coverage_score if c_item else None,
            "faithfulness_score": f_item.faithfulness_score if f_item else None,
            "missed_units_count": len(c_item.missed_units) if c_item else 0,
            "ungrounded_claims_count": len(f_item.ungrounded_claims) if f_item else 0,
            "claims_count": sum(len(pg.key_claims) for pg in p.pages.values() if pg.page_type == "sources"),
        })

    return {
        "num_runs": n_runs,
        "run_ids": [p.run_id for p in profiles],
        "metrics": {
            "rsi": round(rsi, 2),
            "entity_jaccard": round(entity_jaccard * 100, 2),
            "concept_jaccard": round(concept_jaccard * 100, 2),
            "page_jaccard": round(page_jaccard * 100, 2),
            "graph_edge_jaccard": round(edge_jaccard * 100, 2),
            "mean_quality_score": round(mean_quality, 2),
            "mean_coverage_score": round(mean_cov, 2) if mean_cov is not None else None,
            "mean_faithfulness_score": round(mean_faith, 2) if mean_faith is not None else None,
        },
        "entities": {
            "total_unique": len(all_entities),
            "core_count": len(core_entities),
            "flaky_count": len(flaky_entities),
            "core": sorted(core_entities),
            "flaky": sorted(flaky_entities),
            "aliases": entity_aliases,
        },
        "concepts": {
            "total_unique": len(all_concepts),
            "core_count": len(core_concepts),
            "flaky_count": len(flaky_concepts),
            "core": sorted(core_concepts),
            "flaky": sorted(flaky_concepts),
            "aliases": concept_aliases,
        },
        "coverage_analysis": {
            "mean_score": mean_cov,
            "missed_by_run": all_missed_units,
        },
        "faithfulness_analysis": {
            "mean_score": mean_faith,
            "ungrounded_claims": all_ungrounded_claims,
        },
        "runs_summary": runs_summary,
    }


def format_full_markdown_report(benchmark: dict[str, Any]) -> str:
    m = benchmark["metrics"]
    rsi = m["rsi"]
    rating = "🟢 XUẤT SẮC" if rsi >= 85 else ("🟡 KHÁ / TRUNG BÌNH" if rsi >= 65 else "🔴 KÉM - LỆCH LỚN")

    lines = [
        "# Báo Cáo Benchmark wiki-ingest: Đo Lường Sai Lệch Reasoning LLM",
        "",
        f"> **Reasoning Stability Index (RSI):** `{rsi}%` ({rating})",
        f"> **Số lượt chạy độc lập (Runs):** {benchmark['num_runs']} lượt",
        "",
        "## 1. Bảng Chỉ Số Toàn Diện (Stability, Coverage & Faithfulness)",
        "",
        "| Chỉ số | Kết quả | Ý nghĩa & Đánh giá |",
        "|---|---|---|",
        f"| **Chỉ số Ổn định Tổng hợp (RSI)** | **`{m['rsi']}%`** | Điểm trung bình trọng số toàn diện |",
        f"| **Độ bao phủ Nguồn (Source Coverage)** | `{m.get('mean_coverage_score', 'N/A')}%` | Tránh bỏ sót các phần, số liệu trong source |",
        f"| **Độ trung thực (Faithfulness)** | `{m.get('mean_faithfulness_score', 'N/A')}%` | Tránh LLM tự bịa kiến thức không có trong source |",
        f"| **Trùng khớp Thực thể (Entity Jaccard)** | `{m['entity_jaccard']}%` | Tính ổn định nhận diện thực thể qua các run |",
        f"| **Trùng khớp Khái niệm (Concept Jaccard)** | `{m['concept_jaccard']}%` | Tính ổn định nhận diện khái niệm qua các run |",
        f"| **Trùng khớp Mạng lưới Wikilinks (Graph Jaccard)** | `{m['graph_edge_jaccard']}%` | Tính bền vững của đồ thị liên kết chéo |",
        f"| **Điểm Tuân thủ Quy chuẩn (Quality Score)** | `{m['mean_quality_score']}/100` | Frontmatter, song ngữ, 0 broken link |",
        "",
        "## 2. Thống Kê Chi Tiết Từng Lượt Chạy (Per-Run Overview)",
        "",
        "| Run ID | Pages | Entities | Concepts | Coverage | Faithfulness | Missed Units | Bịa đặt / Ungrounded | Quality |",
        "|---|---|---|---|---|---|---|---|---|",
    ]

    for r in benchmark["runs_summary"]:
        cov_str = f"{r.get('coverage_score')}%" if r.get('coverage_score') is not None else "N/A"
        faith_str = f"{r.get('faithfulness_score')}%" if r.get('faithfulness_score') is not None else "N/A"
        lines.append(
            f"| `{r['run_id']}` | {r['pages_count']} | {r['entities_count']} | {r['concepts_count']} | "
            f"{cov_str} | {faith_str} | {r.get('missed_units_count', 0)} | {r.get('ungrounded_claims_count', 0)} | {r['quality_score']}/100 |"
        )

    lines.extend([
        "",
        "## 3. Phân Tích Thực Thể & Khái Niệm: Cốt Lõi vs Chập Chờn",
        "",
        f"- **Entities Cốt lõi (100% các run đều có):** `{len(benchmark['entities']['core'])}` — `{', '.join(benchmark['entities']['core']) or 'Không có'}`",
        f"- **Entities Chập chờn (Flaky):** `{len(benchmark['entities']['flaky'])}` — `{', '.join(benchmark['entities']['flaky']) or 'Không có'}`",
        "",
        f"- **Concepts Cốt lõi (100% các run đều có):** `{len(benchmark['concepts']['core'])}` — `{', '.join(benchmark['concepts']['core']) or 'Không có'}`",
        f"- **Concepts Chập chờn (Flaky):** `{len(benchmark['concepts']['flaky'])}` — `{', '.join(benchmark['concepts']['flaky']) or 'Không có'}`",
        "",
    ])

    all_aliases = benchmark["entities"]["aliases"] + benchmark["concepts"]["aliases"]
    if all_aliases:
        lines.extend([
            "## 4. Phân Mảnh Tên Gọi (Slug Fragmentation / Naming Drift)",
            "",
        ])
        for al in all_aliases:
            vars_str = " vs ".join(f"`[[{v}]]`" for v in al["variants"])
            dist_str = ", ".join(f"`{k}`: {v}" for k, v in al["distribution"].items())
            lines.append(f"- **Biến thể:** {vars_str}")
            lines.append(f"  - Xuất hiện: {dist_str}")
        lines.append("")

    # Section 5: Coverage Breakdown
    cov_analysis = benchmark.get("coverage_analysis", {})
    if cov_analysis.get("missed_by_run"):
        lines.extend([
            "## 5. Phân Tích Nội Dung Bị Bỏ Sót (Source Omission / Missed Content)",
            "",
            "Các thông tin hoặc số liệu có trong source nhưng bị LLM bỏ qua:",
            "",
        ])
        for r_id, m_units in cov_analysis["missed_by_run"].items():
            if m_units:
                lines.append(f"### Lượt chạy `{r_id}` bỏ sót ({len(m_units)} mục):")
                for u in m_units[:8]:
                    lines.append(f"- ❌ {u}")
                if len(m_units) > 8:
                    lines.append(f"- *(và {len(m_units) - 8} mục khác...)*")
                lines.append("")

    # Section 6: Faithfulness Breakdown
    faith_analysis = benchmark.get("faithfulness_analysis", {})
    if faith_analysis.get("ungrounded_claims"):
        ug_claims = faith_analysis["ungrounded_claims"]
        lines.extend([
            "## 6. Phân Tích Thông Tin Ngoại Lai & Nghi Vấn Bịa Đặt (Hallucination / Ungrounded Claims)",
            "",
            "Các câu khẳng định xuất hiện trong wiki nhưng **KHÔNG có bằng chứng** trong source:",
            "",
        ])
        for ug in ug_claims[:10]:
            sev_icon = "🚨" if ug.get("severity") == "CRITICAL" else ("⚠️" if ug.get("severity") == "HIGH" else "ℹ️")
            lines.append(f"- {sev_icon} **[{ug.get('run_id')}] `{ug.get('file')}` (Dòng {ug.get('line')}):** \"{ug.get('claim')}\"")
            lines.append(f"  - *Lý do:* {ug.get('reason')}")
        if len(ug_claims) > 10:
            lines.append(f"\n*(Tổng cộng {len(ug_claims)} câu nghi vấn bịa đặt / ngoại lai)*")
        lines.append("")

    return "\n".join(lines)


def init_sandboxes(target_dir: Path, num_runs: int) -> None:
    target_dir.mkdir(parents=True, exist_ok=True)
    for r in range(1, num_runs + 1):
        run_path = target_dir / f"run_{r}"
        wiki_dir = run_path / "wiki"
        for sub in [".meta", "sources", "entities", "concepts", "synthesis"]:
            (wiki_dir / sub).mkdir(parents=True, exist_ok=True)
        (wiki_dir / "index.md").touch()
        (wiki_dir / "log.md").touch()
        hashes_file = wiki_dir / ".meta" / "ingest-hashes.json"
        if not hashes_file.is_file():
            hashes_file.write_text('{"_version": 1, "entries": {}}\n', encoding="utf-8")
    print(f"Đã khởi tạo thành công {num_runs} sandbox sạch tại: {target_dir}")
    print(f"Cấu trúc mỗi sandbox: <path>/run_N/wiki/[sources, entities, concepts, synthesis, .meta]")


def main() -> int:
    parser = argparse.ArgumentParser(description="Wiki Ingest Test & Benchmark Suite")
    parser.add_argument("--eval", dest="eval_path", help="Evaluate single run wiki directory")
    parser.add_argument("--source", dest="source_file", help="Path to raw source document for coverage/faithfulness check")
    parser.add_argument("--fixture", dest="fixture_name", help="Name of fixture to evaluate against golden truth")
    parser.add_argument("--compare", dest="compare_runs", nargs="+", help="Compare multiple run directories for drift")
    parser.add_argument("--init-sandbox", dest="init_dir", help="Directory to initialize clean sandboxes")
    parser.add_argument("--runs", dest="runs_count", type=int, default=3, help="Number of sandboxes to init (default: 3)")
    parser.add_argument("--json", dest="json_out", help="Save output to JSON")
    parser.add_argument("--report", dest="report_out", help="Save output to Markdown report")
    args = parser.parse_args()

    golden_path = Path(__file__).parent / "fixtures" / "expected_golden.json"
    golden_data = json.loads(golden_path.read_text("utf-8")) if golden_path.is_file() else {}

    # Load source text if provided or inferred from fixture
    source_text = ""
    if args.source_file:
        s_path = Path(args.source_file).resolve()
        if s_path.is_file():
            source_text = s_path.read_text("utf-8", errors="replace")
    elif args.fixture_name:
        fix_path = Path(__file__).parent / "fixtures" / args.fixture_name
        if fix_path.is_file():
            source_text = fix_path.read_text("utf-8", errors="replace")

    if args.init_dir:
        init_sandboxes(Path(args.init_dir).resolve(), args.runs_count)
        return 0

    if args.eval_path:
        run_dir = Path(args.eval_path).resolve()
        profile = profile_run(run_dir)
        print(f"==================================================")
        print(f"KẾT QUẢ ĐÁNH GIÁ ĐƠN LẺ: {run_dir.name}")
        print(f"==================================================")
        print(f"- Tổng số trang: {len(profile.pages)}")
        print(f"  + Sources:  {len(profile.sources)} ({sorted(profile.sources)})")
        print(f"  + Entities: {len(profile.entities)} ({sorted(profile.entities)})")
        print(f"  + Concepts: {len(profile.concepts)} ({sorted(profile.concepts)})")
        print(f"- Broken Wikilinks: {len(profile.broken_links)} ({profile.broken_links})")
        print(f"- Điểm Tuân thủ Quy chuẩn: {profile.checklist_score}/100")
        for k, v in profile.checklist_results.items():
            status = "PASS" if v.get("passed") else "FAIL"
            print(f"  [{status}] {k}: {v.get('detail')}")

        if args.fixture_name:
            golden_eval = evaluate_against_golden(profile, args.fixture_name, golden_data, source_text)
            print(f"\n--- ĐỐI CHIẾU GOLDEN TRUTH ({args.fixture_name}) ---")
            print(f"- Điểm Độ chính xác (Accuracy): {golden_eval.get('ground_truth_score')}/100")
            print(f"- Entity Recall: {golden_eval.get('entity_recall')}% (Khớp: {golden_eval.get('matched_entities')}, Thiếu: {golden_eval.get('missing_entities')})")
            print(f"- Concept Recall: {golden_eval.get('concept_recall')}% (Khớp: {golden_eval.get('matched_concepts')}, Thiếu: {golden_eval.get('missing_concepts')})")
            print(f"- Metrics Recall: {golden_eval.get('metric_recall')}% (Khớp: {golden_eval.get('matched_metrics')}, Thiếu: {golden_eval.get('missing_metrics')})")
            if golden_eval.get("detected_hallucinations"):
                print(f"- 🚨 CẢNH BÁO ẢO GIÁC (Hallucinations): {golden_eval.get('detected_hallucinations')}")

            # Coverage report
            cov = golden_eval.get("coverage")
            if cov:
                print(f"\n--- ĐỘ BAO PHỦ NỘI DUNG NGUỒN (SOURCE COVERAGE - TRÁNH BỎ SÓT) ---")
                print(f"- Tỷ lệ Bao phủ (Coverage Score): {cov.get('coverage_score')}% ({cov.get('covered_units_count')}/{cov.get('total_source_units')} đơn vị thông tin)")
                print(f"- Tỷ lệ Bao phủ Mục (Section Coverage): {cov.get('section_coverage_rate')}%")
                if cov.get("missed_sections"):
                    print(f"- ❌ Các Section trong source bị bỏ sót: {cov.get('missed_sections')}")
                if cov.get("missed_units"):
                    print(f"- ❌ Các thông số/nội dung bị bỏ sót ({len(cov.get('missed_units'))} mục):")
                    for mu in cov.get("missed_units")[:5]:
                        print(f"   • {mu}")

            # Faithfulness report
            faith = golden_eval.get("faithfulness")
            if faith:
                print(f"\n--- ĐỘ TRUNG THỰC & BẰNG CHỨNG (FAITHFULNESS - TRÁNH BỊA ĐẶT) ---")
                print(f"- Điểm Trung thực: {faith.get('faithfulness_score')}% ({faith.get('grounded_claims_count')}/{faith.get('total_wiki_claims')} câu có căn cứ)")
                if faith.get("ungrounded_claims"):
                    print(f"- ⚠️ Các câu trong wiki KHÔNG có căn cứ trong source ({len(faith.get('ungrounded_claims'))} câu):")
                    for ug in faith.get("ungrounded_claims")[:5]:
                        print(f"   • [{ug.get('file')}:{ug.get('line')}] {ug.get('claim')}")
                        print(f"     Lý do: {ug.get('reason')}")
                if faith.get("unseen_numbers"):
                    print(f"- ⚠️ Số liệu ngoại lai không có trong source: {faith.get('unseen_numbers')}")
                if faith.get("unseen_terms"):
                    print(f"- ⚠️ Thuật ngữ ngoại lai không có trong source: {faith.get('unseen_terms')[:6]}")
        return 0

    if args.compare_runs:
        run_paths = [Path(p).resolve() for p in args.compare_runs]
        fixture_spec = golden_data.get("fixtures", {}).get(args.fixture_name, {}) if args.fixture_name else None
        res = benchmark_multi_runs(run_paths, source_text, fixture_spec)
        md_report = format_full_markdown_report(res)
        print(md_report)

        if args.json_out:
            Path(args.json_out).write_text(json.dumps(res, ensure_ascii=False, indent=2), encoding="utf-8")
            print(f"Saved JSON: {args.json_out}")
        if args.report_out:
            Path(args.report_out).write_text(md_report, encoding="utf-8")
            print(f"Saved Markdown report: {args.report_out}")
        return 0

    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
