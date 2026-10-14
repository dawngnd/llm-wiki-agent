#!/usr/bin/env python3
"""Self-test for the benchmark harness and evaluation engine."""

import unittest
from pathlib import Path
import tempfile
import json
import shutil

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from run_eval import profile_run, evaluate_against_golden, benchmark_multi_runs, init_sandboxes


class TestBenchmarkEngine(unittest.TestCase):
    def setUp(self):
        self.test_dir = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: shutil.rmtree(self.test_dir, ignore_errors=True))

    def test_init_sandboxes(self):
        init_sandboxes(self.test_dir / "sb", 3)
        self.assertTrue((self.test_dir / "sb" / "run_1" / "wiki" / ".meta" / "ingest-hashes.json").is_file())
        self.assertTrue((self.test_dir / "sb" / "run_2" / "wiki" / "sources").is_dir())
        self.assertTrue((self.test_dir / "sb" / "run_3" / "wiki" / "index.md").is_file())

    def test_profile_empty_run(self):
        run_path = self.test_dir / "empty"
        init_sandboxes(self.test_dir / "empty_parent", 1)
        profile = profile_run(self.test_dir / "empty_parent" / "run_1")
        self.assertEqual(len(profile.pages), 0)
        self.assertEqual(profile.checklist_score, 0.0)

    def test_golden_eval(self):
        # Create a mock run
        wiki = self.test_dir / "run" / "wiki"
        (wiki / "entities").mkdir(parents=True, exist_ok=True)
        (wiki / "concepts").mkdir(parents=True, exist_ok=True)
        (wiki / "sources").mkdir(parents=True, exist_ok=True)

        ent_content = """---
title: "Payment Gateway"
type: entities
tags: [payment]
sources: [source.md]
created: 2026-10-13
updated: 2026-10-13
---
# Payment Gateway
## Context (Ngữ cảnh)
Cổng thanh toán kết nối CoreBanking và Client.
"""
        (wiki / "entities" / "payment-gateway.md").write_text(ent_content, encoding="utf-8")

        profile = profile_run(self.test_dir / "run")
        golden_data = {
            "fixtures": {
                "test.md": {
                    "required_entities": ["paymentgateway"],
                    "entity_aliases": {"paymentgateway": ["payment-gateway"]},
                    "required_concepts": [],
                    "required_metrics": [],
                    "forbidden_hallucinations": ["hallucinated-tool"]
                }
            }
        }
        res = evaluate_against_golden(profile, "test.md", golden_data)
        self.assertEqual(res["entity_recall"], 100.0)
        self.assertEqual(res["detected_hallucinations"], [])

    def test_coverage_and_faithfulness(self):
        from content_faithfulness import analyze_source_coverage, analyze_faithfulness

        source_doc = """# Tài liệu Hệ thống V2
Mục tiêu đạt 3000 TPS và latency 300ms.
Áp dụng Outbox Pattern và Idempotency Key.
"""
        # Wiki page covering only 3000 TPS, omitting latency 300ms, and hallucinating MongoDB
        wiki_pages = {
            "source-summary": """# Source
- Mục tiêu đạt 3000 TPS với Outbox Pattern.
- Tích hợp MongoDB để lưu trữ dữ liệu (ngoại lai).
"""
        }

        cov = analyze_source_coverage(source_doc, wiki_pages)
        self.assertTrue(cov.coverage_score > 0)
        self.assertTrue(any("300ms" in m for m in cov.missed_units))

        faith = analyze_faithfulness(source_doc, wiki_pages, forbidden_hallucinations=["mongodb"])
        self.assertTrue(any(u["severity"] == "CRITICAL" for u in faith.ungrounded_claims))


if __name__ == "__main__":
    unittest.main()
