"""Reproducible local ASR quality benchmark for consented/open audio manifests."""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import statistics
import time
from collections import defaultdict
from collections.abc import Awaitable, Callable, Sequence
from pathlib import Path
from typing import Any

from pilot.system.voice import _transcribe_speech

Transcriber = Callable[[str, str, str, str], Awaitable[dict[str, str]]]


def normalize_transcript(text: str) -> str:
    return " ".join(re.findall(r"[\w']+", text.casefold(), flags=re.UNICODE))


def edit_distance(reference: Sequence[Any], hypothesis: Sequence[Any]) -> int:
    previous = list(range(len(hypothesis) + 1))
    for row, reference_item in enumerate(reference, start=1):
        current = [row]
        for column, hypothesis_item in enumerate(hypothesis, start=1):
            current.append(
                min(
                    current[-1] + 1,
                    previous[column] + 1,
                    previous[column - 1] + (reference_item != hypothesis_item),
                )
            )
        previous = current
    return previous[-1]


def error_rate(reference: Sequence[Any], hypothesis: Sequence[Any]) -> float:
    if not reference:
        return 0.0 if not hypothesis else 1.0
    return edit_distance(reference, hypothesis) / len(reference)


def score_transcript(reference: str, hypothesis: str) -> dict[str, float]:
    normalized_reference = normalize_transcript(reference)
    normalized_hypothesis = normalize_transcript(hypothesis)
    return {
        "wer": error_rate(normalized_reference.split(), normalized_hypothesis.split()),
        "cer": error_rate(list(normalized_reference), list(normalized_hypothesis)),
    }


def _summarize(rows: list[dict[str, Any]]) -> dict[str, float | int]:
    latencies = sorted(float(row["latency_ms"]) for row in rows)
    p95_index = max(0, min(len(latencies) - 1, int(len(latencies) * 0.95) - 1))
    return {
        "samples": len(rows),
        "wer": round(statistics.fmean(float(row["wer"]) for row in rows), 4),
        "cer": round(statistics.fmean(float(row["cer"]) for row in rows), 4),
        "latency_p50_ms": round(statistics.median(latencies), 1),
        "latency_p95_ms": round(latencies[p95_index], 1),
    }


async def benchmark_manifest(
    manifest_path: Path,
    *,
    engine: str = "auto",
    model: str = "small",
    limit: int | None = None,
    transcriber: Transcriber = _transcribe_speech,
) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    base_dir = manifest_path.resolve().parent

    for line_number, raw_line in enumerate(manifest_path.read_text(encoding="utf-8").splitlines(), start=1):
        if not raw_line.strip():
            continue
        sample = json.loads(raw_line)
        if not isinstance(sample.get("audio"), str) or not isinstance(sample.get("text"), str):
            raise ValueError(f"Manifest line {line_number} requires string audio and text fields")
        audio_path = Path(sample["audio"])
        if not audio_path.is_absolute():
            audio_path = base_dir / audio_path
        if not audio_path.is_file():
            raise FileNotFoundError(f"Manifest line {line_number} audio not found: {audio_path}")

        language = str(sample.get("language", "auto"))
        started = time.perf_counter()
        result = await transcriber(str(audio_path), language, model, engine)
        latency_ms = (time.perf_counter() - started) * 1000
        scores = score_transcript(sample["text"], result["text"])
        rows.append(
            {
                "audio": str(audio_path),
                "reference": sample["text"],
                "hypothesis": result["text"],
                "language": language,
                "accent": str(sample.get("accent", "unspecified")),
                "condition": str(sample.get("condition", "clean")),
                "latency_ms": round(latency_ms, 1),
                **scores,
            }
        )
        if limit is not None and len(rows) >= limit:
            break

    if not rows:
        raise ValueError("Voice benchmark manifest contains no samples")

    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[f"{row['language']}|{row['accent']}|{row['condition']}"].append(row)

    return {
        "schema_version": 1,
        "provenance": "recorded_or_synthetic_audio_manifest",
        "engine": engine,
        "model": model,
        "overall": _summarize(rows),
        "slices": {key: _summarize(group_rows) for key, group_rows in sorted(grouped.items())},
        "samples": rows,
    }


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path, help="JSONL with audio, text, and optional language/accent/condition")
    parser.add_argument("--engine", choices=("auto", "faster_whisper", "openai_whisper"), default="auto")
    parser.add_argument("--model", default="small")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--output", type=Path)
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    report = asyncio.run(benchmark_manifest(args.manifest, engine=args.engine, model=args.model, limit=args.limit))
    payload = json.dumps(report, indent=2, ensure_ascii=False)
    if args.output:
        args.output.write_text(f"{payload}\n", encoding="utf-8")
    print(payload)


if __name__ == "__main__":
    main()
