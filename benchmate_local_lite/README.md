# BenchMate Local · Lite

A tiny, **local-only** evaluation harness that runs task-shaped tests against Ollama models
and logs pass/fail, latency, and reasons. No cloud APIs required.

## Quick start

1) **Install Ollama**: https://ollama.com
2) **Pull two small models** (examples):
   ```bash
   ollama pull llama3.1:8b-instruct
   ollama pull qwen2:7b-instruct
   ```
3) **Create a Python env and install deps**:
   ```bash
   python -m venv .venv
   source .venv/bin/activate   # Windows: .venv\Scripts\activate
   pip install -r requirements.txt
   ```
4) **Run**:
   ```bash
   python benchmate_local.py --models mistral-nemo:12b --packs packs/core
   python benchmate_local.py --models llama3.1:8b-instruct,qwen2:7b-instruct --packs packs/core
   ```
5) **See results**:
   - CSV: `results/run_YYYYMMDD_HHMMSS.csv`
   - Summary: `results/summary_YYYYMMDD_HHMMSS.md`

## What’s included (MVP)
- **Packs** (sample):
  - `type: json` → Strict JSON extraction with JSON Schema check and "no extra prose".
  - `type: grounded` → Answer from given context or say “I don’t know / nicht im Text”.
  - `type: hangman` → Multi-turn rule-following: respond with exactly **one lowercase letter** per turn, never repeating.
- **Validators**: minimal, readable, single-purpose.

## Notes
- Determinism: The runner sets temperature=0 where supported by Ollama to reduce randomness.
- Safety: Sample inputs are synthetic/public. No customer data.
- Extending: Add YAML files in `packs/` and new validators in `validators/`.

