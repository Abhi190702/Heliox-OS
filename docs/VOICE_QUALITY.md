# Voice quality and reproducible evaluation

Heliox performs speech recognition and synthesis locally. “Perfect” voice recognition is not a defensible universal
claim: microphones, rooms, accents, languages, and speakers vary. The release gate is therefore a measured matrix of
word error rate (WER), character error rate (CER), and latency, plus a real-device check on each supported platform.

## Recommended open evaluation data

| Dataset | What it tests | License / practical note |
| --- | --- | --- |
| Mozilla Common Voice | Diverse speakers, accents, microphones, and languages | CC0; use validated clips and preserve accent metadata |
| Google FLEURS | Cross-language ASR and language identification | 102 languages, roughly 12 hours per language; use its published dataset terms |
| Google Speech Commands | Short command and keyword robustness | Useful for short words such as yes/no and directions; not a substitute for natural desktop sentences |
| MUSAN | Music, speech, and noise overlays | CC BY 4.0; large (about 11 GB), so it is an opt-in robustness corpus |

Do not commit third-party audio to this repository. Recordings of Heliox users require explicit consent and should stay
local. Synthetic TTS round trips may catch regressions, but must be labelled synthetic and never presented as evidence
of human microphone or accent accuracy.

## Manifest and command

Create a JSONL manifest whose audio paths are relative to the manifest:

```json
{"audio":"clips/open-github.wav","text":"Open GitHub","language":"en","accent":"indian","condition":"clean"}
{"audio":"clips/open-github-noisy.wav","text":"Open GitHub","language":"en","accent":"indian","condition":"musan-noise-10db"}
```

Run the local recognizer and write a machine-readable report:

```powershell
cd daemon
python -m benchmarks.voice_quality .\voice-eval\manifest.jsonl --engine auto --model small --output .\voice-report.json
```

Reports include aggregate and per-language/accent/condition WER, CER, p50 latency, p95 latency, and every hypothesis.
Compare the same frozen manifest before and after a recognition change. Do not tune on the final held-out slice.

## Hardware release gate

For Windows, macOS, and Linux, test at least the built-in microphone and one headset in a quiet room and with ordinary
background noise. Verify first-syllable capture, short commands, names such as “Heliox” and “GitHub,” interruption while
TTS is speaking, multilingual selection, visible approval boundaries, and that spoken output cannot approve a
destructive action. Record the model, engine, device, language, WER, and p50/p95 end-to-end latency.
