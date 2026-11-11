"""Incremental online runs and portable downloads for an ephemeral cloud host."""
import io
import platform
import re
import sys
import zipfile
from pathlib import Path

from .core import Workflow, case_paths, digest, load_case, model_input, now, read_json, require, write_json
from .evaluation import inventory, verify_manifest
from .provider import GenerationError, generate, settings


def new_run(path, split, manifest_path=None):
    require(split in ("development", "holdout"), "Unknown split.")
    manifest = verify_manifest(manifest_path) if split == "holdout" and manifest_path else None
    require(split != "holdout" or manifest is not None, "Freeze and review development before holdout.")
    path = Path(path)
    path.mkdir(parents=True, exist_ok=False)
    run = {"started_at": now(), "split": split, "backend": "live", "case_ids": [p.stem for p in case_paths(split)],
           "status": "running", "succeeded": 0, "failed": 0, "release_files": inventory(),
           "model_settings": settings(), "frozen_manifest": manifest, "python": sys.version,
           "platform": platform.platform(), "purpose": "research_output_collection"}
    write_json(path / "run.json", run, exclusive=True)
    return run


def run_next(path, api_key):
    path = Path(path)
    run = read_json(path / "run.json")
    require(run["status"] == "running", "This run is already complete.")
    require(run["release_files"] == inventory(), "Code, data, or settings changed. Preserve this run; do not mix versions.")
    missing = [i for i in run["case_ids"] if not (path / (i + ".json")).exists()]
    require(missing, "No unattempted cases remain.")
    case_id = missing[0]
    case = load_case(case_id, run["split"])
    flow = Workflow(case)
    flow.commit_initial(case["initial"])
    flow.reveal()
    payload = model_input(case, case["initial"])
    attempt = {"case_id": case_id, "backend": "live", "input": payload,
               "case_hash": digest(case), "started_at": now(), "status": "started"}
    target = path / (case_id + ".json")
    write_json(target, attempt, exclusive=True)
    try:
        output, generation = generate(payload, "live", api_key=api_key)
        flow.attach_comparison(output, generation)
        for response in case["followups"]:
            flow.followup(response)
        attempt.update(status="success", comparison=output, generation=generation,
                       workflow=flow.record, scripted_followup=True)
    except (GenerationError, ValueError) as exc:
        attempt.update(status="error", error=str(exc), generation=getattr(exc, "artifact", {}), workflow=flow.record)
    attempt["finished_at"] = now()
    write_json(target, attempt)
    reconcile(path)
    return attempt


def reconcile(path):
    """Recover counters from saved attempts; interrupted calls stay failures, never silently retried."""
    path = Path(path)
    run = read_json(path / "run.json")
    succeeded = failed = 0
    for case_id in run["case_ids"]:
        target = path / (case_id + ".json")
        if not target.exists():
            continue
        attempt = read_json(target)
        if attempt["status"] == "started":
            attempt.update(status="error", error="Interrupted attempt; no usable response saved. Do not silently rerun.", finished_at=now())
            write_json(target, attempt)
        if attempt["status"] == "success":
            succeeded += 1
        else:
            failed += 1
    run.update(succeeded=succeeded, failed=failed)
    if succeeded + failed == len(run["case_ids"]):
        run["status"] = "complete"
        run.setdefault("finished_at", now())
    write_json(path / "run.json", run)
    return run


def bundle_bytes(path):
    result = io.BytesIO()
    with zipfile.ZipFile(result, "w", zipfile.ZIP_DEFLATED) as archive:
        for file in sorted(Path(path).rglob("*")):
            if file.is_file() and file.suffix in (".json", ".html", ".csv"):
                archive.writestr(str(file.relative_to(path)), file.read_bytes())
    return result.getvalue()


def restore_bundle(data, path):
    """Read an exported run only; never execute uploaded files or extract arbitrary paths."""
    path = Path(path)
    require(not path.exists(), "Restore destination must be new.")
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        infos = archive.infolist()
        require(len(infos) <= 100 and sum(i.file_size for i in infos) <= 20_000_000, "Archive is too large.")
        names = [i.filename for i in infos]
        require(len(set(names)) == len(names) and "run.json" in names, "Archive must contain a unique run.json.")
        allowed = re.compile(r"(?:run|review|frozen|[DH][0-9]{2})\.json|review\.html|summary/(?:summary\.json|case_scores\.csv)")
        require(all(allowed.fullmatch(n) for n in names), "Unexpected archive filenames.")
        import json
        run = json.loads(archive.read("run.json"))
        require(run["release_files"] == inventory(), "Archive does not match current project files.")
        require(run["backend"] == "live" and run["split"] in ("development", "holdout"), "Invalid run type.")
        require(run["case_ids"] == [p.stem for p in case_paths(run["split"])], "Unexpected case inventory.")
        if run["split"] == "holdout":
            require(run.get("frozen_manifest", {}).get("status") == "frozen" and
                    run["frozen_manifest"]["files"] == inventory(), "Missing matching frozen release.")
        path.mkdir(parents=True)
        for item in infos:
            target = path / item.filename
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(archive.read(item))
    reconcile(path)
    return path
