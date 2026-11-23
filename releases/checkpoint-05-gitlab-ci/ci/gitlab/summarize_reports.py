"""Write a concise Markdown summary of the GitLab pipeline reports.

Run from the repository root after the test and load-test jobs:
python ci/gitlab/summarize_reports.py
"""

from __future__ import annotations

import csv
import os
from pathlib import Path
from xml.etree import ElementTree

SUMMARY = Path("pipeline-summary.md")
COVERAGE = Path("coverage.xml")
LOCUST_STATS = Path(".artifacts/locust/results_stats.csv")


def unit_test_lines() -> list[str]:
    reports = sorted(Path().glob("junit-py*.xml"))
    if not reports:
        raise FileNotFoundError("No junit-py*.xml reports were found.")
    lines = []
    for report in reports:
        cases = list(ElementTree.parse(report).getroot().iter("testcase"))
        failed = sum(
            case.find("failure") is not None or case.find("error") is not None for case in cases
        )
        skipped = sum(case.find("skipped") is not None for case in cases)
        version = report.stem.removeprefix("junit-py")
        lines.append(
            f"- Python {version}: {len(cases) - failed - skipped}/{len(cases)} tests passed"
            f" ({failed} failed, {skipped} skipped)"
        )
    return lines


def coverage_line() -> str:
    root = ElementTree.parse(COVERAGE).getroot()
    covered = int(root.attrib["lines-covered"]) + int(root.attrib["branches-covered"])
    total = int(root.attrib["lines-valid"]) + int(root.attrib["branches-valid"])
    # Same total as `coverage report`: statements and branches combined.
    return f"- Statement and branch coverage: {100 * covered / total:.1f}% (minimum 85%)"


def load_test_line() -> str:
    with LOCUST_STATS.open(newline="", encoding="utf-8") as stats:
        row = next(item for item in csv.DictReader(stats) if item["Name"] == "Aggregated")
    return (
        f"- Locust: {row['Request Count']} requests, {row['Failure Count']} failures,"
        f" average {float(row['Average Response Time']):.0f} ms, p95 {row['95%']} ms"
    )


def main() -> None:
    commit = os.environ.get("CI_COMMIT_SHORT_SHA", "local")
    pipeline = os.environ.get("CI_PIPELINE_ID", "local")
    summary = "\n".join([
        "# Pipeline summary",
        "",
        f"Pipeline {pipeline} for commit {commit}.",
        "",
        "## Unit and integration tests",
        *unit_test_lines(),
        coverage_line(),
        "",
        "## Load test",
        load_test_line(),
        "",
    ])
    SUMMARY.write_text(summary, encoding="utf-8")
    print(summary)


if __name__ == "__main__":
    main()
