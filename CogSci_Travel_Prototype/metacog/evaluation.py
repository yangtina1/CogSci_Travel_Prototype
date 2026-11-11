"""Run logging, integrity checks, and manual review preparation; no automatic semantic judge."""
import csv
import html
import platform
import sys
from pathlib import Path

from .core import (ROOT, Workflow, case_paths, digest, load_case, model_input, now,
                   read_json, require, validate_case, write_json)
from .provider import GenerationError, generate, settings


def inventory():
    paths = []
    for directory in ("metacog", "web", "prompts", "schemas", "config", "data", "evaluation/gold", "tests", "scripts"):
        paths.extend(p for p in (ROOT / directory).rglob("*") if p.is_file()
                     and "__pycache__" not in p.parts and p.suffix != ".pyc")
    paths += [ROOT / name for name in ("evaluation/rubric.json", "docs/EVALUATION_PROTOCOL.md", "streamlit_app.py", "requirements.txt", ".streamlit/config.toml")]
    import hashlib
    return {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(paths)}


def validate_dataset():
    all_ids, option_names, counts = set(), set(), {}
    for split in ("development", "holdout"):
        counts[split] = 0
        for path in case_paths(split):
            case = validate_case(read_json(path))
            require(case["id"] == path.stem and case["id"] not in all_ids, "Duplicate or mismatched case ID.")
            all_ids.add(case["id"])
            for option in case["options"]:
                require(option["name"] not in option_names, "Destination name reused across cases.")
                option_names.add(option["name"])
            gold = read_json(ROOT / "evaluation/gold" / split / path.name)
            require(gold["case_id"] == case["id"], "Mismatched gold case ID.")
            from .core import source_catalog
            sources = source_catalog(model_input(case, case["initial"]))
            ids = set()
            for item in gold["expected_observations"]:
                require(item["id"] not in ids, "Duplicate gold observation.")
                ids.add(item["id"])
                require(set(item["source_ids"]) <= set(sources), "Invalid gold source reference.")
            require(gold["tags"] and ids, "Missing coverage tags or expected observations.")
            counts[split] += 1
    require(counts == {"development": 12, "holdout": 12}, "Expected 12 development and 12 holdout cases.")
    return counts


def snapshot(status="candidate", development_run=None, review=None):
    return {"status": status, "created_at": now(), "files": inventory(), "model_settings": settings(),
            "python": sys.version, "platform": platform.platform(),
            "development_run": str(development_run) if development_run else None,
            "development_review": review,
            "note": "Hashes detect changes, not semantic validity or deterministic API behavior."}


def verify_manifest(path, frozen=True):
    manifest = read_json(path)
    if frozen:
        require(manifest["status"] == "frozen", "Holdout requires a frozen release, not the candidate manifest.")
    current = inventory()
    changed = sorted(k for k in set(current) | set(manifest["files"])
                     if current.get(k) != manifest["files"].get(k))
    require(not changed, "Release changed: " + ", ".join(changed))
    return manifest


def freeze(path, development_run, review_path):
    run = read_json(Path(development_run) / "run.json")
    review = read_json(review_path)
    require(run["split"] == "development" and run["backend"] == "live", "Freeze needs a live development run.")
    require(run["status"] == "complete" and run["succeeded"] == len(run["case_ids"]) == 12,
            "Freeze requires all 12 development cases successfully collected with current settings.")
    require(run["release_files"] == inventory(), "Code/data/settings changed after development run; rerun development.")
    validate_review(Path(development_run), review)
    require(review["reviewer"].strip() and review["overall_notes"].strip(), "Name the reviewer and document development findings.")
    require(review["ready_to_freeze"] is True, "Set ready_to_freeze only after reviewing development outputs.")
    write_json(path, snapshot("frozen", development_run, review), exclusive=True)


def run_cases(split, backend, out, manifest_path=None):
    require(split in ("development", "holdout"), "Unknown split.")
    if split == "holdout":
        require(backend == "live", "Holdout cannot use offline fixtures.")
        require(manifest_path is not None, "Supply the frozen manifest for holdout.")
        manifest = verify_manifest(manifest_path)
    else:
        manifest = None
    validate_dataset()
    if backend == "live":
        import os
        require(not settings()["model"].startswith("SET_"), "Configure model.json first.")
        require(bool(os.environ.get("GEMINI_API_KEY")), "GEMINI_API_KEY is not configured.")
    out = Path(out)
    out.mkdir(parents=True, exist_ok=False)
    ids = [p.stem for p in case_paths(split)]
    run = {"started_at": now(), "split": split, "backend": backend, "case_ids": ids,
           "status": "running", "succeeded": 0, "failed": 0,
           "release_files": inventory(), "model_settings": settings(), "frozen_manifest": manifest,
           "python": sys.version, "platform": platform.platform(),
           "purpose": "research_output_collection" if backend == "live" else "software_smoke_only"}
    write_json(out / "run.json", run)
    for case_id in ids:
        if manifest_path and split == "holdout":
            verify_manifest(manifest_path)
        require(run["release_files"] == inventory(), "Files changed mid-run; stop and preserve partial artifacts.")
        case = load_case(case_id, split)
        workflow = Workflow(case)
        workflow.commit_initial(case["initial"])
        workflow.reveal()
        payload = model_input(case, workflow.record["initial"])
        attempt = {"case_id": case_id, "backend": backend, "input": payload,
                   "case_hash": digest(case), "started_at": now(), "status": "started"}
        path = out / (case_id + ".json")
        write_json(path, attempt, exclusive=True)
        try:
            comparison, artifact = generate(payload, backend)
            workflow.attach_comparison(comparison, artifact)
            # These are authored responses, NOT predictions or observed human reactions.
            for response in case["followups"]:
                workflow.followup(response)
            attempt.update(status="success", comparison=comparison, generation=artifact,
                           workflow=workflow.record, scripted_followup=True)
            run["succeeded"] += 1
        except (GenerationError, ValueError) as exc:
            attempt.update(status="error", error=str(exc), generation=getattr(exc, "artifact", {}),
                           workflow=workflow.record)
            run["failed"] += 1
        attempt["finished_at"] = now()
        write_json(path, attempt)
        write_json(out / "run.json", run)
        print(case_id + ": " + attempt["status"], flush=True)
    run["status"] = "complete"
    run["finished_at"] = now()
    write_json(out / "run.json", run)
    return run


def prepare_review(run_path):
    run_path = Path(run_path)
    run = read_json(run_path / "run.json")
    require(run["backend"] == "live", "Offline fixtures are not eligible for research review.")
    require(run["status"] == "complete", "Preserve and resolve an interrupted run before preparing review.")
    rubric = read_json(ROOT / "evaluation/rubric.json")
    review = {"run_hash": digest(run), "reviewer": "", "reviewed_at": "", "overall_notes": "",
              "ready_to_freeze": False, "cases": []}
    blocks = []
    for case_id in run["case_ids"]:
        attempt = read_json(run_path / (case_id + ".json"))
        gold = read_json(ROOT / "evaluation/gold" / run["split"] / (case_id + ".json"))
        entry = {"case_id": case_id, "attempt_hash": digest(attempt), "status": attempt["status"],
                 "scores": {name: None for name in rubric["criteria"]}, "rationale": "",
                 "observations": {v["id"]: None for v in gold["expected_observations"]},
                 "finding_audit": [{"index": i, "verdict": None, "notes": ""}
                                   for i, _ in enumerate(attempt.get("comparison", {}).get("findings", []))],
                 "additional_errors": []}
        review["cases"].append(entry)
        import json
        blocks.append("<section><h2>" + html.escape(case_id) + "</h2>" +
                      "<h3>Case input and output</h3><pre>" + html.escape(json.dumps(
                          {"input": attempt["input"], "comparison": attempt.get("comparison"),
                           "status": attempt["status"], "error": attempt.get("error")}, indent=2, ensure_ascii=False)) +
                      "</pre><h3>Author expectations (reviewer only)</h3><pre>" +
                      html.escape(json.dumps(gold, indent=2, ensure_ascii=False)) + "</pre></section>")
    write_json(run_path / "review.json", review, exclusive=True)
    report = "<!doctype html><meta charset='utf-8'><title>Output review packet</title><style>body{max-width:1000px;margin:40px auto;font:17px system-ui;padding:20px}pre{white-space:pre-wrap;background:#f3f5f7;padding:20px}section{break-before:page}h2{color:#135f61}</style><h1>Output review packet</h1><p>Fill review.json using evaluation/rubric.json. This packet does not score semantic quality automatically.</p>" + "".join(blocks)
    (run_path / "review.html").write_text(report, encoding="utf-8")
    return review


def validate_review(run_path, review):
    run_path = Path(run_path)
    run = read_json(run_path / "run.json")
    require(run["backend"] == "live", "Cannot score offline fixtures as research outputs.")
    require(review["run_hash"] == digest(run), "Review does not match this run.")
    require(review["reviewer"].strip() and review["reviewed_at"].strip(), "Record reviewer and review date.")
    entries = review["cases"]
    require(len(entries) == len(run["case_ids"]) and {e["case_id"] for e in entries} == set(run["case_ids"]),
            "Review must contain each attempted case exactly once.")
    rubric = read_json(ROOT / "evaluation/rubric.json")
    for entry in entries:
        attempt = read_json(run_path / (entry["case_id"] + ".json"))
        require(entry["attempt_hash"] == digest(attempt) and entry["status"] == attempt["status"],
                "Attempt was changed after review preparation.")
        require(entry["rationale"].strip(), "Explain each case rating or technical failure.")
        if entry["status"] != "success":
            require(all(v is None for v in entry["scores"].values()), "Failed outputs have no semantic scores.")
            continue
        require(set(entry["scores"]) == set(rubric["criteria"]), "Missing or unknown score dimensions.")
        for key, value in entry["scores"].items():
            require((type(value) is int and value in (0, 1, 2)) or
                    (key == "tradeoff_coverage" and value == "NA"), "Unfilled or invalid semantic rating.")
        gold = read_json(ROOT / "evaluation/gold" / run["split"] / (entry["case_id"] + ".json"))
        require(set(entry["observations"]) == {v["id"] for v in gold["expected_observations"]}, "Observation IDs changed.")
        require(all(v in rubric["observation_codes"] for v in entry["observations"].values()), "Unfilled observation rating.")
        findings = attempt["comparison"]["findings"]
        audit = entry["finding_audit"]
        require(len(audit) == len(findings) and {v["index"] for v in audit} == set(range(len(findings))),
                "Audit every generated finding exactly once, including claims outside the gold expectations.")
        require(all(v["verdict"] in rubric["finding_verdicts"] and v["notes"].strip() for v in audit),
                "Each finding needs an evidence verdict and note.")
    return run


def summarize(run_path, review_path, out):
    review = read_json(review_path)
    run = validate_review(run_path, review)
    out = Path(out)
    out.mkdir(parents=True, exist_ok=False)
    summary = {"total_attempted": len(run["case_ids"]), "successful_outputs": run["succeeded"],
               "technical_failures": run["failed"], "criteria": {}, "observations": {}, "finding_audit": {}}
    good = [c for c in review["cases"] if c["status"] == "success"]
    for criterion in read_json(ROOT / "evaluation/rubric.json")["criteria"]:
        values = [c["scores"][criterion] for c in good]
        summary["criteria"][criterion] = {str(v): values.count(v) for v in (0, 1, 2, "NA")}
    observations = [v for c in good for v in c["observations"].values()]
    summary["observations"] = {v: observations.count(v) for v in ("covered", "partial", "missed")}
    summary["observations"]["denominator"] = len(observations)
    verdicts = [v["verdict"] for c in good for v in c["finding_audit"]]
    summary["finding_audit"] = {v: verdicts.count(v) for v in ("supported", "partly_supported", "unsupported")}
    summary["finding_audit"]["denominator"] = len(verdicts)
    summary["interpretation"] = "Descriptive researcher-coded artifact results only. No participant effects or causal improvement estimates. Technical failures remain in the total attempted denominator."
    write_json(out / "summary.json", summary, exclusive=True)
    with (out / "case_scores.csv").open("x", newline="", encoding="utf-8") as stream:
        fields = ["case_id", "status"] + list(summary["criteria"])
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for entry in review["cases"]:
            writer.writerow({"case_id": entry["case_id"], "status": entry["status"], **entry["scores"]})
    return summary
