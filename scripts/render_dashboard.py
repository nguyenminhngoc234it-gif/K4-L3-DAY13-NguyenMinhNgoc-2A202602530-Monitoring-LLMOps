from __future__ import annotations

import argparse
import json
import math
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path
from xml.sax.saxutils import escape

import yaml


REPO_ROOT = Path(__file__).resolve().parents[1]


def parse_timestamp(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def percentile(values: list[float], percent: int) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, math.ceil(percent / 100 * len(ordered)) - 1))
    return ordered[index]


def load_window(log_path: Path, minutes: int) -> tuple[list[dict], datetime, datetime]:
    records = [
        json.loads(line)
        for line in log_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    stamped = [(record, parse_timestamp(record["ts"])) for record in records if record.get("ts")]
    if not stamped:
        raise ValueError(f"No timestamped records found in {log_path}")
    end = max(timestamp for _, timestamp in stamped)
    start = end - timedelta(minutes=minutes)
    return [record for record, timestamp in stamped if start <= timestamp <= end], start, end


def summarize(records: list[dict], minutes: int) -> list[dict[str, str]]:
    received = [record for record in records if record.get("event") == "request_received"]
    responses = [record for record in records if record.get("event") == "response_sent"]
    failures = [record for record in records if record.get("event") == "request_failed"]
    latency = [float(record["latency_ms"]) for record in responses if "latency_ms" in record]
    ttft = [float(record["ttft_ms"]) for record in responses if "ttft_ms" in record]
    tool_results = [record for record in records if record.get("tool_success") is not None]
    retrieval_success = (
        100 * sum(record.get("tool_success") is True for record in tool_results) / len(tool_results)
        if tool_results
        else 0.0
    )
    error_rate = 100 * len(failures) / len(received) if received else 0.0
    error_types = Counter(record.get("error_type", "unknown") for record in failures)
    error_breakdown = ", ".join(f"{name}: {count}" for name, count in error_types.items()) or "none"
    total_cost = sum(float(record.get("cost_usd", 0)) for record in responses)
    tokens_in = sum(int(record.get("tokens_in", 0)) for record in responses)
    tokens_out = sum(int(record.get("tokens_out", 0)) for record in responses)
    quality = [float(record["quality_score"]) for record in responses if "quality_score" in record]

    return [
        {
            "title": "Latency percentiles and TTFT",
            "value": f"P95 {percentile(latency, 95):.0f} ms",
            "detail": (
                f"P50 {percentile(latency, 50):.0f} | P99 {percentile(latency, 99):.0f} | "
                f"TTFT P95 {percentile(ttft, 95):.0f} ms"
            ),
            "threshold": "Threshold: P95 <= 3000 ms",
        },
        {
            "title": "Request traffic",
            "value": f"{len(received)} requests",
            "detail": f"{len(received) / minutes:.2f} requests/minute",
            "threshold": "Threshold: rate >= 1 request/minute",
        },
        {
            "title": "Error rate and retrieval success",
            "value": f"{error_rate:.1f}% errors",
            "detail": f"Retrieval success {retrieval_success:.1f}% | Types: {error_breakdown}",
            "threshold": "Threshold: errors <= 2% | retrieval >= 90%",
        },
        {
            "title": "Cost over time",
            "value": f"${total_cost:.4f}",
            "detail": f"Total across {len(responses)} completed requests",
            "threshold": "Threshold: total <= $2.50",
        },
        {
            "title": "Input and output tokens",
            "value": f"{tokens_in + tokens_out:,} tokens",
            "detail": f"Input {tokens_in:,} | Output {tokens_out:,}",
            "threshold": "Threshold: total <= 50,000 tokens",
        },
        {
            "title": "Quality proxy",
            "value": f"{sum(quality) / len(quality):.2f}" if quality else "0.00",
            "detail": f"Mean across {len(quality)} responses | unit: score 0-1",
            "threshold": "Threshold: mean >= 0.75",
        },
    ]


def render_svg(panels: list[dict[str, str]], title: str, start: datetime, end: datetime) -> str:
    width, height = 1440, 900
    cards: list[str] = []
    for index, panel in enumerate(panels):
        column, row = index % 2, index // 2
        x, y = 60 + column * 680, 170 + row * 220
        cards.append(
            f'''<g transform="translate({x} {y})">
  <rect width="640" height="180" rx="18" fill="#172033" stroke="#334155"/>
  <text x="28" y="40" class="panel-title">{escape(panel["title"])}</text>
  <text x="28" y="88" class="value">{escape(panel["value"])}</text>
  <text x="28" y="124" class="detail">{escape(panel["detail"])}</text>
  <text x="28" y="154" class="threshold">{escape(panel["threshold"])}</text>
</g>'''
        )
    subtitle = (
        f"Last 60 minutes | {start.isoformat(timespec='seconds')} to "
        f"{end.isoformat(timespec='seconds')} | source: data/logs.jsonl"
    )
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-labelledby="title desc">
<title id="title">{escape(title)}</title>
<desc id="desc">Six-panel operations dashboard generated from structured JSON logs.</desc>
<style>
  .heading {{ font: 600 32px system-ui, sans-serif; fill: #f8fafc; }}
  .subtitle {{ font: 16px system-ui, sans-serif; fill: #94a3b8; }}
  .panel-title {{ font: 600 20px system-ui, sans-serif; fill: #e2e8f0; }}
  .value {{ font: 600 34px system-ui, sans-serif; fill: #60a5fa; }}
  .detail {{ font: 16px system-ui, sans-serif; fill: #cbd5e1; }}
  .threshold {{ font: 15px system-ui, sans-serif; fill: #86efac; }}
</style>
<rect width="1440" height="900" fill="#0f172a"/>
<text x="60" y="70" class="heading">{escape(title)}</text>
<text x="60" y="108" class="subtitle">{escape(subtitle)}</text>
<text x="60" y="136" class="subtitle">Refresh: 30 seconds | 6/6 panels</text>
{''.join(cards)}
</svg>
'''


def main() -> int:
    parser = argparse.ArgumentParser(description="Render the six-panel CP2 dashboard as SVG")
    parser.add_argument("--logs", type=Path, default=REPO_ROOT / "data" / "logs.jsonl")
    parser.add_argument("--config", type=Path, default=REPO_ROOT / "config" / "dashboard.yaml")
    parser.add_argument(
        "--output",
        type=Path,
        default=REPO_ROOT / "submission" / "evidence" / "11-dashboard-overview.svg",
    )
    args = parser.parse_args()

    config = yaml.safe_load(args.config.read_text(encoding="utf-8"))["dashboard"]
    records, start, end = load_window(args.logs, int(config["time_range_minutes"]))
    panels = summarize(records, int(config["time_range_minutes"]))
    if len(config["panels"]) != 6 or len(panels) != 6:
        raise ValueError("Dashboard must contain exactly six panels")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(render_svg(panels, config["title"], start, end), encoding="utf-8")
    print(f"Rendered 6/6 panels to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
