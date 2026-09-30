from __future__ import annotations

import json
import math
import os
import sys
from datetime import datetime
from pathlib import Path
from xml.sax.saxutils import escape

from dotenv import load_dotenv


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.challenge import load_challenge
from langfuse import get_client


OUTPUT_DIR = REPO_ROOT / "submission" / "evidence"
PROJECT_NAME = "day13-k4-l3b-2A202602530"


def parse_ts(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def svg_page(title: str, subtitle: str, body: str) -> str:
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="1440" height="900" viewBox="0 0 1440 900">
<style>
  .title {{ font: 700 34px system-ui, sans-serif; fill: #f8fafc; }}
  .subtitle {{ font: 17px system-ui, sans-serif; fill: #94a3b8; }}
  .h2 {{ font: 650 21px system-ui, sans-serif; fill: #e2e8f0; }}
  .big {{ font: 700 38px system-ui, sans-serif; fill: #60a5fa; }}
  .text {{ font: 17px system-ui, sans-serif; fill: #cbd5e1; }}
  .mono {{ font: 16px Consolas, monospace; fill: #dbeafe; }}
  .small {{ font: 14px system-ui, sans-serif; fill: #94a3b8; }}
  .ok {{ fill: #86efac; }} .warn {{ fill: #fca5a5; }}
</style>
<rect width="1440" height="900" fill="#0f172a"/>
<text x="60" y="68" class="title">{escape(title)}</text>
<text x="60" y="104" class="subtitle">{escape(subtitle)}</text>
{body}
</svg>'''


def box(x: int, y: int, width: int, height: int) -> str:
    return f'<rect x="{x}" y="{y}" width="{width}" height="{height}" rx="18" fill="#172033" stroke="#334155"/>'


def load_run() -> tuple[object, list[dict], dict, int]:
    challenge = load_challenge(REPO_ROOT / "config" / "challenge.json")
    lines = (REPO_ROOT / "data" / "logs.jsonl").read_text(encoding="utf-8").splitlines()
    records = [json.loads(line) for line in lines if line.strip()]
    enabled_indexes = [
        index
        for index, record in enumerate(records)
        if record.get("event") == "incident_enabled"
        and record.get("payload", {}).get("name") == challenge.incident
    ]
    if not enabled_indexes:
        raise RuntimeError("No challenge incident window found in logs")
    following = records[enabled_indexes[-1] + 1 :]
    disabled_index = next(
        (
            index
            for index, record in enumerate(following)
            if record.get("event") == "incident_disabled"
            and record.get("payload", {}).get("name") == challenge.incident
        ),
        len(following),
    )
    run_records = following[:disabled_index]
    responses = [
        record
        for record in run_records
        if record.get("event") == "response_sent"
        and str(record.get("session_id", "")).startswith("k4-l3b-challenge-")
    ]
    if not responses:
        raise RuntimeError("No challenge responses found after the latest incident enable")
    selected = max(responses, key=lambda record: float(record["latency_ms"]))
    line_number = next(
        index
        for index, line in enumerate(lines, start=1)
        if selected["correlation_id"] in line and '"event": "response_sent"' in line
    )
    return challenge, responses, selected, line_number


def render_metric(challenge: object, responses: list[dict]) -> None:
    ordered = sorted(float(record["latency_ms"]) for record in responses)
    p50 = ordered[math.ceil(0.50 * len(ordered)) - 1]
    p95 = ordered[math.ceil(0.95 * len(ordered)) - 1]
    average = sum(ordered) / len(ordered)
    threshold = float(challenge.latency_threshold_ms)
    start = min(parse_ts(record["ts"]) for record in responses)
    end = max(parse_ts(record["ts"]) for record in responses)
    max_value = max(max(ordered), threshold) * 1.15
    bars = []
    for index, value in enumerate(ordered):
        x = 145 + index * 185
        height = 420 * value / max_value
        color = "#ef4444" if value > threshold else "#60a5fa"
        bars.append(f'<rect x="{x}" y="{690-height:.1f}" width="105" height="{height:.1f}" rx="8" fill="{color}"/>')
        bars.append(f'<text x="{x+52}" y="{715}" text-anchor="middle" class="mono">{value:.0f}</text>')
    threshold_y = 690 - 420 * threshold / max_value
    body = f'''
{box(60, 140, 1320, 680)}
<text x="95" y="190" class="h2">Challenge latency (server-side logs)</text>
<text x="95" y="242" class="big">P95 {p95:.0f} ms</text>
<text x="400" y="239" class="text">P50 {p50:.0f} ms · Average {average:.1f} ms · Requests {len(ordered)}</text>
<line x1="110" y1="{threshold_y:.1f}" x2="1130" y2="{threshold_y:.1f}" stroke="#fca5a5" stroke-width="3" stroke-dasharray="10 8"/>
<text x="1145" y="{threshold_y+5:.1f}" class="text warn">SLO {threshold:.0f} ms</text>
{''.join(bars)}
<text x="95" y="770" class="text">Window: {escape(start.isoformat())} → {escape(end.isoformat())}</text>
<text x="95" y="800" class="text warn">Symptom: latency P95 exceeded the configured threshold.</text>
'''
    output = OUTPUT_DIR / "12-incident-metric.svg"
    output.write_text(svg_page("CP3 Incident Metric", f"Challenge {challenge.challenge_id}", body), encoding="utf-8")


def render_log(challenge: object, selected: dict, line_number: int) -> None:
    fields = [
        ("event", selected.get("event")),
        ("timestamp", selected.get("ts")),
        ("correlation_id", selected.get("correlation_id")),
        ("session_id", selected.get("session_id")),
        ("feature", selected.get("feature")),
        ("latency_ms", selected.get("latency_ms")),
        ("ttft_ms", selected.get("ttft_ms")),
        ("tool_name", selected.get("tool_name")),
        ("tool_success", selected.get("tool_success")),
    ]
    rows = []
    for index, (name, value) in enumerate(fields):
        y = 260 + index * 48
        rows.append(f'<text x="120" y="{y}" class="mono">{escape(name):20} {escape(str(value))}</text>')
    body = f'''
{box(60, 140, 1320, 680)}
<text x="95" y="190" class="h2">Selected structured log record</text>
<text x="95" y="222" class="small">Source: data/logs.jsonl:{line_number}</text>
{''.join(rows)}
<text x="95" y="735" class="text warn">Why selected: highest server-side latency in this challenge run.</text>
<text x="95" y="778" class="text">Use correlation_id to open the matching Langfuse trace.</text>
'''
    output = OUTPUT_DIR / "13-incident-log.svg"
    output.write_text(svg_page("CP3 Incident Log", f"Challenge {challenge.challenge_id}", body), encoding="utf-8")


def render_trace(challenge: object, selected: dict) -> None:
    load_dotenv(REPO_ROOT / ".env")
    response = get_client().api.observations.get_many(
        session_id=selected["session_id"],
        limit=100,
        fields="core,basic,metadata,metrics",
        expand_metadata="correlation_id",
    )
    observations = [item.model_dump() for item in response.data]
    if not observations:
        raise RuntimeError("Langfuse returned no observations for the selected session")
    root = next(
        item
        for item in observations
        if item.get("is_root_observation")
        and item.get("metadata", {}).get("correlation_id") == selected["correlation_id"]
    )
    trace_id = str(root["trace_id"])
    children = sorted(
        [
            item
            for item in observations
            if not item.get("is_root_observation") and str(item["trace_id"]) == trace_id
        ],
        key=lambda item: item["start_time"],
    )
    root_start = root["start_time"]
    root_latency = float(root["latency"])
    scale = 800 / root_latency
    bars = [
        f'<rect x="300" y="330" width="800" height="56" rx="10" fill="#2563eb"/>',
        f'<text x="120" y="365" class="mono">{escape(root["name"])}</text>',
        f'<text x="1120" y="365" class="mono">{root_latency:.3f}s</text>',
    ]
    for index, item in enumerate(children):
        y = 430 + index * 105
        offset = (item["start_time"] - root_start).total_seconds() * scale
        width = max(8, float(item["latency"]) * scale)
        color = "#ef4444" if item["name"] == "retrieval" else "#22c55e"
        bars.append(f'<text x="120" y="{y+35}" class="mono">{escape(item["name"])}</text>')
        bars.append(f'<rect x="{300+offset:.1f}" y="{y}" width="{width:.1f}" height="56" rx="10" fill="{color}"/>')
        bars.append(f'<text x="1120" y="{y+35}" class="mono">{float(item["latency"]):.3f}s</text>')
    body = f'''
{box(60, 140, 1320, 680)}
<text x="95" y="190" class="h2">Langfuse Observations API v2 · Project: {PROJECT_NAME}</text>
<text x="95" y="225" class="mono">trace_id: {escape(trace_id)}</text>
<text x="95" y="258" class="mono">correlation_id: {escape(selected['correlation_id'])}</text>
<text x="95" y="292" class="small">Trace and log are joined through the same request metadata/session.</text>
{''.join(bars)}
<text x="95" y="755" class="text warn">Root cause signal: retrieval dominates the trace; generation remains fast.</text>
<text x="95" y="790" class="small">Source fetched from the configured personal Langfuse project; no secret values included.</text>
'''
    output = OUTPUT_DIR / "14-incident-trace.svg"
    output.write_text(svg_page("CP3 Incident Trace", f"Challenge {challenge.challenge_id}", body), encoding="utf-8")
    print(json.dumps({
        "challenge_id": challenge.challenge_id,
        "window_start": min(record["ts"] for record in responses_global),
        "window_end": max(record["ts"] for record in responses_global),
        "correlation_id": selected["correlation_id"],
        "trace_id": trace_id,
        "root_latency_s": root_latency,
        "spans": {item["name"]: item["latency"] for item in children},
    }, ensure_ascii=False))


if __name__ == "__main__":
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    challenge_global, responses_global, selected_global, line_number_global = load_run()
    render_metric(challenge_global, responses_global)
    render_log(challenge_global, selected_global, line_number_global)
    render_trace(challenge_global, selected_global)
