"""Online Python prototype. Deploy this entrypoint on Streamlit Community Cloud."""
import copy
import json
import os
import tempfile
import time
from pathlib import Path

import streamlit as st

from metacog.cloud import bundle_bytes, new_run, restore_bundle, run_case, saved_flow, save_followup
from metacog.core import ROOT, Workflow, case_paths, load_case, model_input, now, read_json, source_catalog, write_json
from metacog.evaluation import freeze, inventory, prepare_review, summarize, verify_manifest
from metacog.provider import GenerationError, comparison_error_message, generate, settings

st.set_page_config(page_title="Pause & Compare · Student Travel", page_icon="🧭", layout="wide")


def api_key():
    try:
        return st.secrets.get("GEMINI_API_KEY", "") or os.getenv("GEMINI_API_KEY", "")
    except (FileNotFoundError, st.errors.StreamlitSecretNotFoundError):
        return os.getenv("GEMINI_API_KEY", "")


def safe_text(value):
    # Use plain text for model/user strings. Never render arbitrary HTML or external images.
    st.text(value)


def lines(value):
    return [line.strip() for line in value.splitlines() if line.strip()]


def judgment_view(value, names):
    st.write("**Preference:**", names.get(value["choice"], "Decision deferred"))
    st.write("**Confidence:**", str(value["confidence"]) + "/100 (self-report)")
    st.write("**Flexible priorities**")
    for item in value["priorities"]:
        safe_text("• " + item)
    st.write("**Firm requirements**")
    for item in value["constraints"] or ["None stated"]:
        safe_text("• " + item)
    st.write("**Reasons**")
    safe_text(value["reasons"])


def evidence_view(payload, source_ids):
    """Present source content in reader language; keep internal IDs in exports only."""
    catalog = source_catalog(payload)
    names = {option["id"]: option["name"] for option in payload["options"]}
    labels = {
        "initial.choice": "Your initial destination",
        "initial.confidence": "Your initial confidence",
        "initial.priorities": "Your initial priorities",
        "initial.constraints": "Your initial requirements",
        "initial.reasons": "Your initial reasons",
        "advice": "AI advice shown in this demo",
    }
    for option in payload["options"]:
        for index, fact in enumerate(option["facts"], 1):
            labels[fact["id"]] = option["name"] + " · detail " + str(index)
    for source_id in source_ids:
        st.caption(labels.get(source_id, "Supporting information"))
        value = catalog[source_id]
        if source_id == "initial.choice":
            safe_text(names.get(value, value))
        elif source_id == "initial.confidence":
            safe_text(str(value) + "/100 (self-report)")
        elif isinstance(value, list):
            for item in value or ["None stated"]:
                safe_text("• " + item)
        else:
            safe_text(value)


def comparison_view(comparison, payload):
    safe_text(comparison["summary"])
    with st.expander("How the model interpreted the original reasoning", expanded=True):
        st.write("**Priorities**")
        safe_text(comparison["priorities_interpretation"])
        st.write("**Reasons**")
        safe_text(comparison["reasoning_interpretation"])
    labels = {"support": "Evidence supporting this finding", "constraint_conflict": "Firm requirement conflict",
              "tradeoff": "Flexible tradeoff", "unsupported_claim": "Unsupported claim", "uncertainty": "Unresolved information"}
    names = {option["id"]: option["name"] for option in payload["options"]}
    st.caption("Each finding concerns the named destinations and the specific claim below; it is not an overall endorsement of a choice.")
    for item in comparison["findings"]:
        with st.container(border=True):
            for option_id in dict.fromkeys(item["option_ids"]):
                is_initial = option_id == payload["initial"]["choice"]
                is_advice = option_id == payload["advice"]["choice"]
                if is_initial and is_advice:
                    role = "Your initial choice and AI recommendation"
                elif is_initial:
                    role = "Your initial choice"
                elif is_advice:
                    role = "AI-recommended option"
                else:
                    role = "Other option"
                st.caption(names[option_id] + " · " + role)
            st.write("**" + labels[item["kind"]] + "**")
            safe_text(item["text"])
            with st.expander("Inspect cited evidence"):
                evidence_view(payload, item["source_ids"])
    st.write("**A question to consider**")
    safe_text(comparison["reflection_question"]["text"])
    with st.expander("Question sources and limits"):
        evidence_view(payload, comparison["reflection_question"]["source_ids"])
        st.caption("Limits of this comparison")
        for limitation in comparison["limitations"]:
            safe_text(limitation)


def workspace(key, split="development", run_path=None):
    locked = split == "holdout"
    scope = split + ":" + (str(run_path) if run_path else "demo")
    st.subheader("Explore a fictional travel decision")
    st.caption("Three destinations. Your reasoning first. Advice second. Then a chance to reflect.")
    options = {p.stem: load_case(p.stem, split) for p in case_paths(split)}
    selected = st.selectbox("Scenario", list(options), key="scenario_" + scope,
                            format_func=lambda i: i + " · " + options[i]["title"])

    def open_case(case_id):
        st.session_state.flow = saved_flow(run_path, case_id) if run_path else Workflow(options[case_id])
        st.session_state.flow_scope = scope
        st.session_state.workspace_generation_errors = []
        st.session_state.workspace_version = None
        st.session_state.decision_serial = st.session_state.get("decision_serial", 0) + 1

    if "flow" not in st.session_state or st.session_state.get("flow_scope") != scope:
        open_case(selected)
    label = "Open selected case" if run_path else "Start a new decision"
    if st.button(label, help="Download an exploratory decision before replacing it. Collected cases reopen their saved result without another request."):
        open_case(selected)
        st.rerun()
    flow = st.session_state.flow
    case, record = flow.case, flow.record
    widget_scope = scope + ":" + case["id"] + ":" + str(st.session_state.get("decision_serial", 0))
    attempt_path = Path(run_path) / (case["id"] + ".json") if run_path else None
    attempt = read_json(attempt_path) if attempt_path and attempt_path.exists() else None
    fixed_input = record["initial"] is None or record["initial"] == case["initial"]
    formal = bool(run_path and fixed_input)
    live_comparison = bool(record["comparison"] and (record.get("generation") or {}).get("backend") == "live")
    names = {o["id"]: o["name"] for o in case["options"]}
    st.caption("Current decision: " + case["id"] + " · " + case["title"])
    if locked:
        st.info("Final evaluation: initial inputs are fixed. Your optional follow-up is saved separately and is not a measure of human improvement.")
    elif run_path:
        st.info("Development collection: unchanged initial inputs enter the review run. Edited inputs are exploratory demonstrations and stay outside that run.")
    st.text_area("Default travel prompt", value=case["context"], disabled=True,
                 height=140, key="context_" + widget_scope)
    st.caption("This fixed budget-conscious student context accompanies your stated priorities and firm requirements.")
    for col, option in zip(st.columns(3), case["options"]):
        with col, st.container(border=True):
            st.subheader(option["name"])
            for fact in option["facts"]:
                safe_text(fact["text"])
                st.caption("Source " + fact["id"])
    if record["stage"] == "initial":
        st.subheader("1 · Record initial reasoning")
        st.caption("The fictional starting values are locked for final evaluation." if locked else
                   "Edit these fictional starting values to try the app. Advice stays scripted, so it may not match your edits.")
        initial = case["initial"]
        with st.form("initial_" + widget_scope):
            choice = st.selectbox("Initial destination", list(names), index=list(names).index(initial["choice"]), format_func=names.get, disabled=locked)
            confidence = st.slider("Initial confidence", 0, 100, int(initial["confidence"]), disabled=locked)
            priorities = st.text_area("Flexible priorities (one per line)", "\n".join(initial["priorities"]), disabled=locked)
            constraints = st.text_area("Firm requirements (one per line; may be empty)", "\n".join(initial["constraints"]), disabled=locked)
            reasons = st.text_area("Initial reasons", initial["reasons"], disabled=locked)
            submitted = st.form_submit_button("Preserve initial reasoning", type="primary")
        if submitted:
            try:
                # Use the fixed record on the server as well as disabling the controls.
                value = copy.deepcopy(initial) if locked else dict(choice=choice, confidence=confidence, priorities=lines(priorities), constraints=lines(constraints), reasons=reasons)
                flow.commit_initial(value)
                st.rerun()
            except ValueError as exc:
                st.error(str(exc))
        st.caption("Advice remains hidden until the initial record is saved.")
        return
    left, right = st.columns([1, 1.3])
    with left:
        st.subheader("Your preserved starting point")
        judgment_view(record["initial"], names)
    with right:
        st.subheader("2 · Examine advice and evidence")
        st.caption("Demo note: scripted advice is used in this prototype. It represents AI advice and is not generated live.")
        if record["stage"] == "committed":
            if st.button("Reveal AI advice", type="primary"):
                flow.reveal()
                st.rerun()
        if record["advice"]:
            st.write("**AI advice**")
            safe_text(record["advice"]["text"])
        if record["stage"] == "advice":
            if not key:
                st.info("The LLM is not connected. You can view the demo advice, but a comparison and reflection question will be available only after the LLM is configured.")
            if attempt and formal:
                st.error("This case already has a recorded attempt. It will not be retried or overwritten. Preserve its error in the run bundle.")
                st.caption(comparison_error_message(GenerationError(attempt.get("error", ""), attempt.get("generation", {}))))
            if run_path and not fixed_input:
                st.caption("Edited development inputs: this comparison is exploratory and will not enter the fixed-case review run.")
            if st.button("Generate comparison and question", disabled=not key or bool(attempt and formal), type="primary"):
                try:
                    with st.spinner("Comparing the stated reasoning with the evidence…"):
                        if formal:
                            collected = run_case(run_path, case["id"], key)
                            st.session_state.flow = saved_flow(run_path, case["id"])
                            if collected["status"] != "success":
                                st.session_state.workspace_generation_errors.append({"at": now(), "error": collected["error"], "generation": collected.get("generation", {})})
                        else:
                            if locked:
                                raise ValueError("Final evaluation requires a fixed-case run.")
                            st.session_state.workspace_version = inventory()
                            output, generation = generate(model_input(case, record["initial"]), "live", api_key=key)
                            flow.attach_comparison(output, generation)
                    st.rerun()
                except (ValueError, GenerationError, OSError) as exc:
                    st.session_state.workspace_generation_errors.append({"at": now(), "error": str(exc), "generation": getattr(exc, "artifact", {})})
                    st.error(comparison_error_message(exc))
                    st.caption("No comparison was generated. Your original reasoning is preserved.")
        if live_comparison:
            st.write("**AI comparison of your reasoning and the advice**")
            comparison_view(record["comparison"], model_input(case, record["initial"]))
        elif record["comparison"]:
            st.info("This decision contains an earlier software preview, not an LLM comparison. Download the record if needed, then start a new decision to request a real comparison.")
    if live_comparison:
        st.subheader("3 · Record reflection and next decision")
        st.caption("The comparison refers to your preserved initial reasoning. New responses are saved separately; they do not rewrite the original or trigger another model call. These responses are not evidence of improved human decision-making.")
        previous = record["followups"][-1] if record["followups"] else record["initial"]
        index = len(record["followups"])
        with st.form("followup_" + widget_scope + "_" + str(index)):
            action = st.selectbox("Decision action", ["retain", "revise", "defer"])
            choice = st.selectbox("Destination (ignored if you defer)", list(names),
                                  index=list(names).index(previous["choice"]) if previous["choice"] else 0, format_func=names.get)
            confidence = st.slider("Confidence now", 0, 100, int(previous["confidence"]))
            priorities = st.text_area("Current flexible priorities (one per line)", "\n".join(previous["priorities"]))
            constraints = st.text_area("Current firm requirements (one per line)", "\n".join(previous["constraints"]))
            reflection = st.text_area("Response to the reflection question")
            reasons = st.text_area("Reason for retaining, revising, or deferring")
            submitted = st.form_submit_button("Save follow-up", type="primary")
        if submitted:
            try:
                response = dict(action=action, choice=None if action == "defer" else choice, confidence=confidence,
                                priorities=lines(priorities), constraints=lines(constraints), reflection=reflection, reasons=reasons)
                if formal and attempt and attempt["status"] == "success":
                    st.session_state.flow = save_followup(run_path, case["id"], response)
                else:
                    flow.followup(response)
                st.rerun()
            except (ValueError, OSError) as exc:
                st.error(str(exc))
        for i, followup in enumerate(record["followups"], 1):
            with st.expander("Saved response %d · %s" % (i, followup["action"]), expanded=i == len(record["followups"])):
                judgment_view(followup, names)
                safe_text("Reflection: " + followup["reflection"])
    version = read_json(Path(run_path) / "run.json")["release_files"] if formal else st.session_state.get("workspace_version")
    export = {**flow.public(), "purpose": "fixed_case_evaluation" if formal else "exploratory_demonstration",
              "split": split, "release_files": version, "followups_used_for_effectiveness": False,
              "generation_errors": st.session_state.workspace_generation_errors}
    if formal and attempt and attempt["status"] == "error":
        export["saved_failure"] = {"error": attempt["error"], "generation": attempt.get("generation", {})}
    st.download_button("Download this decision record", json.dumps(export, indent=2, ensure_ascii=False),
                       file_name=case["id"] + "_decision_record.json", mime="application/json")
    st.caption("Download before closing or refreshing the browser. Use the run-bundle download to preserve all evaluation cases and reviews.")

def review_editor(path):
    review_path = path / "review.json"
    if not review_path.exists():
        if st.button("Prepare review packet"):
            prepare_review(path)
            st.rerun()
        return
    review = read_json(review_path)
    rubric = read_json(ROOT / "evaluation/rubric.json")
    st.subheader("Review the outputs")
    st.caption("These are researcher judgments of artifacts, not a participant survey or automatic model grading.")
    case_id = st.selectbox("Case to review", [c["case_id"] for c in review["cases"]])
    entry = next(c for c in review["cases"] if c["case_id"] == case_id)
    attempt = read_json(path / (case_id + ".json"))
    split = read_json(path / "run.json")["split"]
    gold = read_json(ROOT / "evaluation/gold" / split / (case_id + ".json"))
    with st.expander("Case evidence and generated output", expanded=True):
        if attempt["status"] == "success":
            comparison_view(attempt["comparison"], attempt["input"])
        else:
            st.error(attempt.get("error", "Technical failure"))
        st.json(attempt["input"], expanded=False)
    with st.form("review_" + str(path) + case_id):
        reviewer = st.text_input("Reviewer name", review["reviewer"])
        scores, observations, audits = {}, {}, []
        if entry["status"] == "success":
            for criterion, anchor in rubric["criteria"].items():
                values = [None, 0, 1, 2] + (["NA"] if criterion == "tradeoff_coverage" else [])
                scores[criterion] = st.selectbox(criterion.replace("_", " ").title(), values,
                                               index=values.index(entry["scores"][criterion]), help=anchor,
                                               format_func=lambda x: "Choose a rating" if x is None else str(x))
            st.write("**Case-specific expected observations**")
            for observation in gold["expected_observations"]:
                values = [None] + rubric["observation_codes"]
                observations[observation["id"]] = st.selectbox(observation["description"], values,
                    index=values.index(entry["observations"][observation["id"]]), key=observation["id"],
                    format_func=lambda x: "Choose coverage" if x is None else x)
            st.write("**Audit every generated finding, including extra claims**")
            for item in entry["finding_audit"]:
                finding = attempt["comparison"]["findings"][item["index"]]
                safe_text(finding["text"])
                values = [None] + rubric["finding_verdicts"]
                verdict = st.selectbox("Evidence verdict for finding %d" % (item["index"] + 1), values,
                    index=values.index(item["verdict"]), format_func=lambda x: "Choose a verdict" if x is None else x)
                notes = st.text_input("Evidence note for finding %d" % (item["index"] + 1), item["notes"])
                audits.append({"index": item["index"], "verdict": verdict, "notes": notes})
        rationale = st.text_area("Rationale for ratings, omissions, and any NA score", entry["rationale"])
        additional = st.text_area("Other errors (one per line; inspect summary and interpretations too)", "\n".join(entry["additional_errors"]))
        overall = st.text_area("Development findings or overall review notes", review["overall_notes"])
        ready = st.checkbox("I have reviewed all development cases and the current version is ready to freeze", value=review["ready_to_freeze"], disabled=split != "development")
        saved = st.form_submit_button("Save this review")
    if saved:
        if entry["status"] == "success":
            entry.update(scores=scores, observations=observations, finding_audit=audits)
        entry.update(rationale=rationale, additional_errors=lines(additional))
        review.update(reviewer=reviewer, reviewed_at=now(), overall_notes=overall, ready_to_freeze=ready)
        write_json(review_path, review)
        st.success("Review saved. Download the run bundle to preserve it.")
    if split == "development" and not (path / "frozen.json").exists():
        if st.button("Freeze reviewed development version"):
            try:
                freeze(path / "frozen.json", path, review_path)
                st.success("Version frozen. Download this bundle before starting holdout.")
            except (ValueError, KeyError) as exc:
                st.error(str(exc))
    if not (path / "summary").exists():
        if st.button("Create descriptive summaries from completed ratings"):
            try:
                summarize(path, review_path, path / "summary")
                st.success("Summary added to the download bundle.")
            except ValueError as exc:
                st.error(str(exc))



def study_tools(key, split):
    if "research_temp" not in st.session_state:
        st.session_state.research_temp = tempfile.TemporaryDirectory(prefix="metacog_")
    base = Path(st.session_state.research_temp.name)
    slot = "study_" + split
    current = st.session_state.get(slot)
    with st.expander("Evaluation records, review, and downloads", expanded=False):
        st.caption("For the video or exploratory edits, use Development normally. Start a development run here to collect unchanged cases for review and freeze. Download bundles before leaving or rebooting.")
        if split == "development":
            if not current:
                if st.button("Start development run", disabled=not key):
                    try:
                        path = base / ("development_" + str(time.time_ns()))
                        new_run(path, "development")
                        st.session_state[slot] = str(path)
                        st.session_state.collect_development = True
                        st.rerun()
                    except (ValueError, OSError) as exc:
                        st.error("Could not start the research run. " + str(exc))
                        st.caption("No model request was made.")
            else:
                st.checkbox("Use saved development run", value=True, key="collect_development")
                st.caption("Turn this off to make a separate editable demonstration; the saved run remains available.")
        elif not current:
            development = st.session_state.get("study_development")
            frozen = Path(development) / "frozen.json" if development else None
            if frozen and frozen.exists():
                try:
                    verify_manifest(frozen)
                    acknowledged = st.checkbox("I downloaded the frozen development bundle")
                    if st.button("Start final evaluation", disabled=not acknowledged or not key):
                        path = base / ("holdout_" + str(time.time_ns()))
                        new_run(path, "holdout", frozen)
                        st.session_state[slot] = str(path)
                        st.rerun()
                except (ValueError, OSError) as exc:
                    st.error(str(exc))
            else:
                st.info("Final evaluation is locked. Collect and review all 12 fixed development cases, then freeze the version. You can also restore its downloaded frozen bundle here.")
        if current:
            path = Path(current)
            run = read_json(path / "run.json")
            count = run["succeeded"] + run["failed"]
            st.write("Saved attempts: %d / %d · Successful: %d · Failed: %d" % (count, len(run["case_ids"]), run["succeeded"], run["failed"]))
            st.progress(count / len(run["case_ids"]))
            st.download_button("Download run bundle", bundle_bytes(path), file_name=split + "_run_bundle.zip", mime="application/zip")
            if split == "development":
                keep = st.checkbox("I downloaded this run and want a new development run")
                if st.button("Start fresh development run", disabled=not keep or not key):
                    try:
                        path = base / ("development_" + str(time.time_ns()))
                        new_run(path, "development")
                        st.session_state[slot] = str(path)
                        st.rerun()
                    except (ValueError, OSError) as exc:
                        st.error(str(exc))
        upload = st.file_uploader("Restore a downloaded run bundle", type=["zip"])
        replace_ok = st.checkbox("I downloaded any current run before restoring another bundle")
        if upload and st.button("Restore run", disabled=not replace_ok):
            try:
                path = base / ("restored_" + str(time.time_ns()))
                restore_bundle(upload.getvalue(), path)
                restored = read_json(path / "run.json")
                st.session_state["study_" + restored["split"]] = str(path)
                st.session_state.restored_notice = "Bundle restored. Select Development or Final evaluation to access the corresponding saved run."
                st.rerun()
            except (ValueError, KeyError, OSError) as exc:
                st.error(str(exc))
        if st.session_state.get("restored_notice"):
            st.info(st.session_state.restored_notice)
    if split == "development" and not st.session_state.get("collect_development", True):
        return None
    if current:
        path = Path(current)
        run = read_json(path / "run.json")
        if run["release_files"] != inventory():
            st.error("The saved run belongs to a different project version. Download it and start a new development run; do not mix results.")
            return False
        if split == "holdout" and (run.get("frozen_manifest", {}).get("status") != "frozen" or run["frozen_manifest"]["files"] != inventory()):
            st.error("Final evaluation requires a matching frozen version.")
            return False
        return path
    return None


def main():
    st.title("Pause & Compare")
    st.caption("Supporting metacognitive monitoring in AI-assisted decision-making · CS 6795")
    key = api_key()
    with st.sidebar:
        st.subheader("LLM status")
        if key:
            st.success("LLM configured")
        else:
            st.info("LLM not connected")
    mode = st.selectbox("Data set", ["Development", "Final evaluation"], key="dataset_mode")
    split = "development" if mode == "Development" else "holdout"
    try:
        path = study_tools(key, split)
        if path is not False:
            if split == "holdout" and path is None:
                st.info("Final-evaluation scenarios become available after a reviewed freeze. Use Development for editable demonstrations.")
            else:
                workspace(key, split, path)
        if path and read_json(path / "run.json")["status"] == "complete":
            if st.checkbox("Show evaluation review and freeze tools", key="review_open_" + str(path)):
                review_editor(path)
    except (ValueError, OSError, KeyError) as exc:
        st.error("Could not open the selected records. " + str(exc))
    with st.expander("Model setup and study scope", expanded=False):
        st.write("Configured model: " + settings()["model"])
        st.caption("LLM configured means a key is present. A successful comparison confirms access for that request.")
        st.write("In Streamlit Settings → Secrets, set GEMINI_API_KEY. Keep the API project on the free tier if you want free-only usage. Quotas and model access depend on your account.")
        st.write("Destination facts and advice are scripted. Only the comparison and reflection question use the LLM. Edited development demonstrations are excluded from fixed-case runs. Initial final-evaluation inputs are locked; optional follow-ups are saved separately and are not evidence of human improvement.")
        st.write("Review the tool's fidelity, evidence handling, tradeoffs, and question quality. Do not use holdout outputs to tune the app and then report the same cases as untouched tests.")


if __name__ == "__main__":
    main()
