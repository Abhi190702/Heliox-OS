"""Short-lived process boundary for optional local TTS model inference."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path


async def _synthesize(engine: str, text: str, voice: str, output_file: str) -> None:
    if engine == "kokoro_tts":
        from pilot.system.kokoro_tts import synthesize_to_file
    elif engine == "pocket_tts":
        from pilot.system.pocket_tts import synthesize_to_file
    else:  # pragma: no cover - argparse enforces the choices
        raise ValueError(f"Unsupported local TTS engine: {engine}")
    await synthesize_to_file(text, voice, output_file)


def _serve(engine: str) -> int:
    for line in sys.stdin:
        try:
            request = json.loads(line)
            text = Path(request["text_file"]).read_text(encoding="utf-8")
            if not text or len(text) > 20_000:
                raise ValueError("Speech text must contain between 1 and 20,000 characters")
            asyncio.run(_synthesize(engine, text, str(request["voice"]), str(request["output_file"])))
            response = {"status": "ok"}
        except Exception as exc:
            response = {"status": "error", "error": f"{type(exc).__name__}: {exc}"}
        print(json.dumps(response), flush=True)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Serve bounded Heliox local-TTS synthesis")
    parser.add_argument("--engine", choices=("kokoro_tts", "pocket_tts"), required=True)
    parser.add_argument("--serve", action="store_true", required=True)
    args = parser.parse_args(argv)
    return _serve(args.engine)


if __name__ == "__main__":  # pragma: no cover - exercised through the parent process
    raise SystemExit(main())
