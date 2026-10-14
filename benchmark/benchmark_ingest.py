#!/usr/bin/env python3
"""Benchmark Harness for wiki-ingest Skill.

Evaluates quality, stability, and reasoning drift across multiple independent
ingest runs of the same document or corpus.

Metrics:
  - Entity Stability (Jaccard similarity, Core vs Flaky entities)
  - Concept Stability (Jaccard similarity, Core vs Flaky concepts)
  - Slug Fragmentation (detecting divergent slugs for the same concept/entity)
  - Wikilink Graph Consistency (Edge overlap & density)
  - Rule & Quality Compliance (Frontmatter, bilingual headers, broken links, language)
  - Overall Reasoning Stability Index (RSI, 0-100%)
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

WIKILINK_RE = re.compile(r"\[\[([a-z0-9\-_]+)\]\]")
FM_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)
BILINGUAL_HEADER_RE = re.compile(r"^#{1,4}\s+.*?\s*\(.*?\)", re.M)
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
    broken_links: list[tuple[str, str]] = field(default_factory=list)  # (page_slug, broken_target)
    graph_edges: set[tuple[str, str]] = field(default_factory=set)  # (from_slug, to_slug)
    quality_score: float = 0.0
    quality_checks: dict[str, bool] = field(default_factory=dict)


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

    # Check required sections by type
    has_req = True
    if page_type == "entities":
        has_req = any("Ngữ cảnh" in h or "Context" in h for h in headers)
    elif page_type == "concepts":
        has_req = any("Ví dụ" in h or "Example" in h for h in headers)
    elif page_type == "sources":
        has_req = any("Key Claims" in h or "Khẳng định" in h for h in headers)

    # Extract claims / takeaways if source page
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

    # Evaluate Quality Checklist
    checks = {}
    total_pages = len(all_pages)
    if total_pages > 0:
        checks["all_have_frontmatter"] = all(bool(p.frontmatter) for p in all_pages.values())
        checks["frontmatter_type_matches"] = all(p.frontmatter.get("type") == p.page_type for p in all_pages.values())
        checks["bilingual_headers_rate"] = (
            sum(len(p.bilingual_headers) for p in all_pages.values())
            / max(1, sum(len(p.headers) for p in all_pages.values()))
        ) >= 0.7
        checks["vietnamese_present"] = all(p.has_vietnamese for p in all_pages.values())
        checks["required_sections_present"] = all(p.has_required_sections for p in all_pages.values())
        checks["zero_broken_links"] = len(profile.broken_links) == 0
        checks["has_index"] = (wiki_dir / "index.md").is_file()
        checks["has_log"] = (wiki_dir / "log.md").is_file()
        checks["has_hashes"] = (wiki_dir / ".meta" / "ingest-hashes.json").is_file()
    else:
        checks["empty"] = True

    score_weights = {
        "all_have_frontmatter": 15,
        "frontmatter_type_matches": 15,
        "bilingual_headers_rate": 15,
        "vietnamese_present": 10,
        "required_sections_present": 15,
        "zero_broken_links": 20,
        "has_index": 5,
        "has_log": 5,
    }
    score = sum(w for k, w in score_weights.items() if checks.get(k, False))
    profile.quality_checks = checks
    profile.quality_score = score

    return profile


def jaccard(s1: set, s2: set) -> float:
    if not s1 and not s2:
        return 1.0
    union = s1 | s2
    if not union:
        return 0.0
    return len(s1 & s2) / len(union)


def find_slug_aliases(all_slugs_by_run: dict[str, set[str]]) -> list[dict[str, Any]]:
    """Detect slug fragmentation: similar slugs across runs that represent the same concept/entity."""
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
            # Also check token overlap
            tokens1 = set(s1.split("-"))
            tokens2 = set(s2.split("-"))
            token_jaccard = len(tokens1 & tokens2) / len(tokens1 | tokens2) if (tokens1 | tokens2) else 0

            if ratio >= 0.75 or token_jaccard >= 0.5:
                group.append(s2)
                seen.add(s2)
        if len(group) > 1:
            seen.add(s1)
            # Find which run generated which variant
            run_mapping = {}
            for g in group:
                run_mapping[g] = [r for r, slugs in all_slugs_by_run.items() if g in slugs]
            clusters.append({
                "variants": group,
                "distribution": run_mapping,
            })
    return clusters


def run_benchmark(run_dirs: list[Path]) -> dict[str, Any]:
    profiles = [profile_run(d) for d in run_dirs]
    n_runs = len(profiles)

    entity_sets = {p.run_id: p.entities for p in profiles}
    concept_sets = {p.run_id: p.concepts for p in profiles}
    page_sets = {p.run_id: set(p.pages.keys()) for p in profiles}
    edge_sets = {p.run_id: {f"{u}->{v}" for u, v in p.graph_edges} for p in profiles}

    # Pairwise Jaccards
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

    # Core items (present in 100% runs) vs Flaky items (present in < 100% runs)
    all_entities = set().union(*entity_sets.values()) if entity_sets else set()
    core_entities = set.intersection(*entity_sets.values()) if entity_sets else set()
    flaky_entities = all_entities - core_entities

    all_concepts = set().union(*concept_sets.values()) if concept_sets else set()
    core_concepts = set.intersection(*concept_sets.values()) if concept_sets else set()
    flaky_concepts = all_concepts - core_concepts

    # Slug fragmentation analysis
    entity_aliases = find_slug_aliases(entity_sets)
    concept_aliases = find_slug_aliases(concept_sets)

    # Quality scores
    mean_quality = sum(p.quality_score for p in profiles) / n_runs if n_runs else 0.0

    # Reasoning Stability Index (RSI): 0 - 100
    # Weights: Entity stability 30%, Concept stability 30%, Graph link stability 20%, Quality standard 20%
    rsi = (
        0.30 * entity_jaccard * 100
        + 0.30 * concept_jaccard * 100
        + 0.20 * edge_jaccard * 100
        + 0.20 * mean_quality
    )

    result = {
        "num_runs": n_runs,
        "run_ids": [p.run_id for p in profiles],
        "metrics": {
            "rsi": round(rsi, 2),
            "entity_jaccard": round(entity_jaccard * 100, 2),
            "concept_jaccard": round(concept_jaccard * 100, 2),
            "page_jaccard": round(page_jaccard * 100, 2),
            "graph_edge_jaccard": round(edge_jaccard * 100, 2),
            "mean_quality_score": round(mean_quality, 2),
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
        "runs_summary": [
            {
                "run_id": p.run_id,
                "pages_count": len(p.pages),
                "entities_count": len(p.entities),
                "concepts_count": len(p.concepts),
                "sources_count": len(p.sources),
                "broken_links_count": len(p.broken_links),
                "broken_links": p.broken_links,
                "quality_score": p.quality_score,
                "claims_count": sum(len(pg.key_claims) for pg in p.pages.values() if pg.page_type == "sources"),
            }
            for p in profiles
        ],
    }
    return result


def format_markdown_report(benchmark: dict[str, Any]) -> str:
    m = benchmark["metrics"]
    rsi = m["rsi"]
    rating = "🟢 XUẤT SẮC" if rsi >= 85 else ("🟡 KHÁ / TRUNG BÌNH" if rsi >= 65 else "🔴 KÉM - LỆCH LỚN")

    lines = [
        "# Báo Cáo Benchmark wiki-ingest: Đo Lường Sai Lệch Reasoning LLM",
        "",
        f"> **Reasoning Stability Index (RSI):** `{rsi}%` ({rating})",
        f"> **Số lượt chạy độc lập (Runs):** {benchmark['num_runs']} lượt",
        "",
        "## 1. Bảng Chỉ Số Ổn Định (Stability & Consistency Metrics)",
        "",
        "| Chỉ số | Kết quả | Ý nghĩa & Đánh giá |",
        "|---|---|---|",
        f"| **Chỉ số Ổn định Tổng hợp (RSI)** | **`{m['rsi']}%`** | Điểm trung bình trọng số toàn diện |",
        f"| **Độ trùng khớp Thực thể (Entity Jaccard)** | `{m['entity_jaccard']}%` | Tỷ lệ thực thể trích xuất đồng nhất giữa các lần chạy |",
        f"| **Độ trùng khớp Khái niệm (Concept Jaccard)** | `{m['concept_jaccard']}%` | Tỷ lệ khái niệm lý thuyết trích xuất đồng nhất |",
        f"| **Trùng khớp Mạng lưới Wikilinks (Graph Jaccard)** | `{m['graph_edge_jaccard']}%` | Tính liên kết chéo giữa các trang qua các lần chạy |",
        f"| **Điểm Tuân thủ Quy chuẩn (Quality Score)** | `{m['mean_quality_score']}/100` | Tuân thủ frontmatter, song ngữ, 0 broken link |",
        "",
        "## 2. Thống Kê Theo Từng Lượt Chạy (Per-Run Overview)",
        "",
        "| Run ID | Tổng Pages | Entities | Concepts | Sources | Broken Links | Quality Score | Số Key Claims |",
        "|---|---|---|---|---|---|---|---|",
    ]

    for r in benchmark["runs_summary"]:
        lines.append(
            f"| `{r['run_id']}` | {r['pages_count']} | {r['entities_count']} | {r['concepts_count']} | "
            f"{r['sources_count']} | {r['broken_links_count']} | {r['quality_score']}/100 | {r['claims_count']} |"
        )

    lines.extend([
        "",
        "## 3. Phân Tích Thực Thể & Khái Niệm: Cốt Lõi vs Chập Chờn (Core vs Flaky)",
        "",
        f"- **Entities Cốt lõi (100% các run đều nhận diện):** `{len(benchmark['entities']['core'])}` thực thể",
        f"  - `{', '.join(benchmark['entities']['core']) or 'Không có'}`",
        f"- **Entities Chập chờn (Flaky/Trôi dạt - chỉ xuất hiện ở một số run):** `{len(benchmark['entities']['flaky'])}` thực thể",
        f"  - `{', '.join(benchmark['entities']['flaky']) or 'Không có'}`",
        "",
        f"- **Concepts Cốt lõi (100% các run đều nhận diện):** `{len(benchmark['concepts']['core'])}` khái niệm",
        f"  - `{', '.join(benchmark['concepts']['core']) or 'Không có'}`",
        f"- **Concepts Chập chờn (Flaky/Trôi dạt):** `{len(benchmark['concepts']['flaky'])}` khái niệm",
        f"  - `{', '.join(benchmark['concepts']['flaky']) or 'Không có'}`",
        "",
    ])

    # Aliases
    all_aliases = benchmark["entities"]["aliases"] + benchmark["concepts"]["aliases"]
    if all_aliases:
        lines.extend([
            "## 4. Phân Mảnh Tên Gọi (Slug Fragmentation / Naming Drift)",
            "",
            "Các lần chạy nhận diện cùng một đối tượng/khái niệm nhưng đặt tên slug khác nhau:",
            "",
        ])
        for al in all_aliases:
            vars_str = " vs ".join(f"`[[{v}]]`" for v in al["variants"])
            dist_str = ", ".join(f"`{k}`: {v}" for k, v in al["distribution"].items())
            lines.append(f"- **Biến thể:** {vars_str}")
            lines.append(f"  - Xuất hiện: {dist_str}")
        lines.append("")

    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Benchmark wiki-ingest runs for reasoning drift.")
    parser.add_argument("runs", nargs="+", help="Paths to run directories containing wiki/ folders")
    parser.add_argument("--json", dest="json_out", help="Save benchmark result to JSON file")
    parser.add_argument("--report", dest="report_out", help="Save benchmark report to Markdown file")
    args = parser.parse_args()

    run_paths = [Path(p).resolve() for p in args.runs]
    for p in run_paths:
        if not p.is_dir():
            print(f"Lỗi: Thư mục run không tồn tại: {p}", file=sys.stderr)
            return 1

    benchmark = run_benchmark(run_paths)
    md_report = format_markdown_report(benchmark)

    print(md_report)

    if args.json_out:
        Path(args.json_out).write_text(json.dumps(benchmark, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\nĐã lưu JSON tại: {args.json_out}")

    if args.report_out:
        Path(args.report_out).write_text(md_report, encoding="utf-8")
        print(f"Đã lưu Markdown report tại: {args.report_out}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
