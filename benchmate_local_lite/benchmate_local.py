import argparse, os, glob, time, csv, json, re
from datetime import datetime
import yaml

from adapters.ollama_adapter import OllamaClient
from validators.json_schema import validate_json_against_schema
from validators.grounded import grounded_validator
from validators.hangman import RuleState, hangman_step
from validators.svg_art import extract_svg, validate_svg_art, insert_metadata_comment

RESULT_FIELDS = [
    "run_id","timestamp","model","task_id","type","language","pass","reason","latency_ms","output_chars"
]

def build_prompt_json(task: dict) -> str:
    tpl = task["prompt_template"]
    doc = task["inputs"]["document"]
    return tpl.replace("{{document}}", doc)

def build_prompt_grounded(task: dict) -> str:
    ctx = task["context"]
    q = task["question"]
    return f"""Lies den folgenden Kontext sorgfältig und beantworte die Frage knapp.
Wenn die Antwort NICHT im Kontext steht, sage ausdrücklich: "nicht im Text".
Kontext:
{ctx}

Frage: {q}
Antwort:"""

def build_initial_prompt_hangman(task: dict) -> str:
    return task["rules_prompt"].strip() + "\n\nErster Buchstabe:"

def load_tasks(packs_dir: str):
    tasks = []
    for path in glob.glob(os.path.join(packs_dir, "*.yaml")):
        with open(path, "r", encoding="utf-8") as f:
            t = yaml.safe_load(f)
            t["_path"] = path
            tasks.append(t)
    return tasks

def summarize(results_rows, out_md_path):
    import collections
    by_model = collections.defaultdict(list)
    for r in results_rows:
        by_model[r["model"]].append(r)

    lines = []
    lines.append(f"# BenchMate Local · Lite — Summary ({datetime.now().strftime('%Y-%m-%d %H:%M:%S')})\n")
    for model, rows in by_model.items():
        total = len(rows)
        passed = sum(1 for r in rows if r["pass"] == "1")
        lines.append(f"## {model}\n")
        lines.append(f"- Passed: **{passed}/{total}**\n")
       
        types = {}
        for r in rows:
            types.setdefault(r["type"], []).append(r)
        for t, trs in types.items():
            tp = sum(1 for r in trs if r["pass"] == "1")
            lines.append(f"  - {t}: {tp}/{len(trs)}")
        lines.append("")
    with open(out_md_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

def build_prompt_svg(task: dict) -> str:
    return task["prompt_template"]

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", required=True, help="Comma-separated model names (as in `ollama list`).")
    ap.add_argument("--packs", required=True, help="Directory with YAML test packs (e.g., packs/core).")
    ap.add_argument("--outdir", default="results", help="Output directory for CSV and summary.")
    ap.add_argument("--max_tokens", type=int, default=4096)
    ap.add_argument("--timeout", type=int, default=180)
    ap.add_argument("--save-outputs", action="store_true",
                help="Save prompts and raw model outputs to JSONL and per-task .txt files.")

    args = ap.parse_args()

    os.makedirs(args.outdir, exist_ok=True)
    tasks = load_tasks(args.packs)
    models = [m.strip() for m in args.models.split(",") if m.strip()]

    client = OllamaClient()
    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    csv_path = os.path.join(args.outdir, f"run_{run_id}.csv")
    md_path = os.path.join(args.outdir, f"summary_{run_id}.md")
    jsonl_file = None
    
    txt_base = None
    if args.save_outputs:
        raw_jsonl_path = os.path.join(args.outdir, f"raw_{run_id}.jsonl")
        jsonl_file = open(raw_jsonl_path, "w", encoding="utf-8")
        txt_base = os.path.join(args.outdir, "outputs", run_id)
        os.makedirs(txt_base, exist_ok=True)


    rows = []

    temperature = 0.0
    timestamp = datetime.now().isoformat(timespec="seconds")

    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=RESULT_FIELDS)
        w.writeheader()
        for task in tasks:
            ttype = task["type"]
            for model in models:
                if ttype == "json":
                    prompt = build_prompt_json(task)
                    text, latency = client.generate(model=model, prompt=prompt, temperature=temperature, max_tokens=args.max_tokens, timeout=args.timeout)
                    ok, reason = validate_json_against_schema(text, task["schema"])
                elif ttype == "grounded":
                    prompt = build_prompt_grounded(task)
                    text, latency = client.generate(model=model, prompt=prompt, temperature=temperature, max_tokens=args.max_tokens, timeout=args.timeout)
                    kw = task.get("expected_keywords") or []
                    mink = int(task.get("min_keywords", 1) or 1)
                    unknown_ok = bool(task.get("unknown_ok", False))
                    ok, reason = grounded_validator(text, task["context"], kw, mink, unknown_ok)
                elif ttype == "hangman":
                    state = RuleState()
                    initial_prompt = build_initial_prompt_hangman(task)
                    prompt = initial_prompt
                    ok_all = True
                    reason = "OK"
                    total_latency = 0
                    turns = int(task.get("turns", 5))
                    turns_log = []  # <-- collect raw outputs

                    for i in range(turns):
                        text, lat = client.generate(model=model, prompt=prompt, temperature=0.0, max_tokens=8, timeout=args.timeout)
                        total_latency += lat
                        ok_step, r = hangman_step(text, state)
                        turns_log.append({"turn": i+1, "output": text, "ok": ok_step, "reason": r, "latency_ms": lat})
                        if not ok_step:
                            ok_all = False
                            reason = f"Turn {i+1}: {r} (model said: {text!r})"
                            break
                        
                        prompt = "Genial. Nächster Buchstabe:"
                    text = f"(hangman {turns} turns)"
                    latency = total_latency
                    ok = ok_all
                elif ttype == "svg":
                    prompt = build_prompt_svg(task)
                    text, latency = client.generate(model=model, prompt=prompt, temperature=temperature, max_tokens=args.max_tokens, timeout=args.timeout)
                    svg = extract_svg(text or "")
                    if not svg:
                        ok = False; reason = "No <svg> block in output."
                    else:
                        ok, reason = validate_svg_art(svg)
                        # Save to results/svgs/<runid>/<model>/<taskid>.svg
                        meta = {
                            "model": model,
                            "temperature": temperature, 
                            "max_tokens": args.max_tokens, 
                            "latency": latency, 
                            "run_id": run_id, 
                            "timestamp": timestamp, 
                            "task_id": task["id"]
                        }
                        svg_with_meta = insert_metadata_comment(svg, meta)
                        
                else:
                    text = "__ERROR__: Unknown task type"
                    latency = 0
                    ok = False
                    reason = "Unknown task type"

                # --- Save raw outputs/prompts (JSONL + .txt) ---
                if args.save_outputs:
                    # JSONL record
                    raw_record = {
                        "run_id": run_id,
                        "timestamp": datetime.now().isoformat(timespec="seconds"),
                        "model": model,
                        "task_id": task["id"],
                        "type": ttype,
                        "language": task.get("language", ""),
                        "latency_ms": latency,
                    }

                    # Per-type fields
                    if ttype == "hangman":
                        raw_record["initial_prompt"] = build_initial_prompt_hangman(task)
                        raw_record["turns"] = turns_log  # filled in the hangman branch below
                    else:
                        raw_record["prompt"] = prompt
                        raw_record["output"] = text

                    jsonl_file.write(json.dumps(raw_record, ensure_ascii=False) + "\n")

                    # Human-readable .txt
                    model_dir = os.path.join(txt_base, model)
                    os.makedirs(model_dir, exist_ok=True)
                    safe_task = re.sub(r'[^a-zA-Z0-9_.-]+', '_', task["id"])
                    txt_path = os.path.join(model_dir, f"{safe_task}.txt")
                    if ttype == "hangman":
                        content = ["RULES PROMPT:", build_initial_prompt_hangman(task), "", "TRANSCRIPT:"]
                        for t in turns_log:
                            content.append(f"Turn {t['turn']}: {t['output']}  -> {'PASS' if t['ok'] else 'FAIL'} ({t['reason']})")
                        content.append("")
                        content.append(f"Final result: {'PASS' if ok else 'FAIL'} ({reason})")
                        txt_body = "\n".join(content)
                    if ttype == "svg":
                        txt_body = f"PROMPT:\n{prompt}\n\nOUTPUT:\n{text or ''}\n"
                        svg_path = os.path.join(model_dir, f"{safe_task}.svg")
                        if ok:
                            with open(svg_path, "w", encoding="utf-8") as svg_file:
                                svg_file.write(svg_with_meta)

                    else:
                        txt_body = f"PROMPT:\n{prompt}\n\nOUTPUT:\n{text or ''}\n"
                    
                    with open(txt_path, "w", encoding="utf-8") as ftxt:
                        ftxt.write(txt_body)
                # --- end raw output save ---
                    row = {
                        "run_id": run_id,
                        "timestamp": datetime.now().isoformat(timespec="seconds"),
                        "model": model,
                        "task_id": task["id"],
                        "type": task["type"],
                        "language": task.get("language", ""),
                        "pass": "1" if ok else "0",
                        "reason": reason,
                        "latency_ms": str(latency),
                        "output_chars": str(len(text or "")),
                    }
                    rows.append(row)
                    w.writerow(row)
                    f.flush()
                    print(f"[{model}] {task['id']} -> {'PASS' if ok else 'FAIL'} ({reason})")

    summarize(rows, md_path)
    if jsonl_file:
        jsonl_file.close()
        print(f"Wrote raw outputs: {os.path.join(args.outdir, f'raw_{run_id}.jsonl')}")
    
    print(f"Saved per-task .txt files under: {os.path.join(args.outdir, 'outputs', run_id)}")
    print(f"\nWrote CSV: {csv_path}\nWrote summary: {md_path}")

if __name__ == "__main__":
    main()
