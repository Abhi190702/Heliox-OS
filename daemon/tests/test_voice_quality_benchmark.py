from __future__ import annotations

import json

import pytest

from benchmarks.voice_quality import benchmark_manifest, score_transcript


def test_score_transcript_normalizes_case_and_punctuation():
    assert score_transcript("Open GitHub!", "open github") == {
        "wer": 0.0,
        "cer": 0.0,
        "word_errors": 0,
        "word_count": 2,
        "char_errors": 0,
        "char_count": 11,
    }


def test_score_transcript_reports_word_and_character_errors():
    scores = score_transcript("open github", "open gitlab")
    assert scores["wer"] == 0.5
    assert scores["word_errors"] == 1
    assert scores["word_count"] == 2
    assert 0.0 < scores["cer"] < 1.0


@pytest.mark.asyncio
async def test_manifest_benchmark_reports_quality_latency_and_slices(tmp_path):
    first_audio = tmp_path / "first.wav"
    second_audio = tmp_path / "second.wav"
    first_audio.write_bytes(b"RIFF")
    second_audio.write_bytes(b"RIFF")
    manifest = tmp_path / "manifest.jsonl"
    manifest.write_text(
        "\n".join(
            (
                json.dumps(
                    {
                        "audio": first_audio.name,
                        "text": "Open GitHub",
                        "language": "en",
                        "accent": "indian",
                        "condition": "clean",
                    }
                ),
                json.dumps(
                    {
                        "audio": second_audio.name,
                        "text": "Close Chrome",
                        "language": "en",
                        "accent": "indian",
                        "condition": "musan-noise-10db",
                    }
                ),
            )
        ),
        encoding="utf-8",
    )

    async def transcribe(audio_path: str, language: str, model: str, engine: str):
        assert language == "en"
        assert model == "small"
        assert engine == "auto"
        return {
            "text": "Open GitHub" if audio_path.endswith("first.wav") else "Close browser",
            "language": "en",
        }

    report = await benchmark_manifest(manifest, transcriber=transcribe)

    assert report["overall"]["samples"] == 2
    assert report["overall"]["wer"] == 0.25
    assert report["provenance"] == "recorded_or_synthetic_audio_manifest"
    assert set(report["slices"]) == {
        "en|indian|clean",
        "en|indian|musan-noise-10db",
    }


@pytest.mark.asyncio
async def test_manifest_uses_corpus_weighted_error_rates_and_nearest_rank_p95(tmp_path):
    samples = []
    hypotheses = {}
    for index, (reference, hypothesis) in enumerate(
        (
            ("one", "wrong"),
            ("one two three four five six seven eight nine", "one two three four five six seven eight nine"),
        )
    ):
        audio = tmp_path / f"sample-{index}.wav"
        audio.write_bytes(b"RIFF")
        samples.append(json.dumps({"audio": audio.name, "text": reference}))
        hypotheses[str(audio)] = hypothesis
    manifest = tmp_path / "manifest.jsonl"
    manifest.write_text("\n".join(samples), encoding="utf-8")

    async def transcribe(audio_path: str, _language: str, _model: str, _engine: str):
        return {"text": hypotheses[audio_path], "language": "en"}

    report = await benchmark_manifest(manifest, transcriber=transcribe)

    assert report["overall"]["wer"] == 0.1
    assert report["overall"]["word_errors"] == 1
    assert report["overall"]["word_count"] == 10
    assert report["overall"]["latency_p95_ms"] == max(sample["latency_ms"] for sample in report["samples"])


@pytest.mark.asyncio
async def test_manifest_rejects_missing_audio(tmp_path):
    manifest = tmp_path / "manifest.jsonl"
    manifest.write_text('{"audio":"missing.wav","text":"hello"}\n', encoding="utf-8")

    with pytest.raises(FileNotFoundError):
        await benchmark_manifest(manifest)


@pytest.mark.asyncio
async def test_manifest_accepts_windows_utf8_bom(tmp_path):
    audio = tmp_path / "sample.wav"
    audio.write_bytes(b"RIFF")
    manifest = tmp_path / "manifest.jsonl"
    manifest.write_text('{"audio":"sample.wav","text":"hello"}\n', encoding="utf-8-sig")

    async def transcribe(_audio_path: str, _language: str, _model: str, _engine: str):
        return {"text": "hello", "language": "en"}

    report = await benchmark_manifest(manifest, transcriber=transcribe)

    assert report["overall"]["wer"] == 0.0
