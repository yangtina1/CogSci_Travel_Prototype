"""Online Python prototype. Deploy this entrypoint on Streamlit Community Cloud."""
import copy
import json
import os
import tempfile
import time
from pathlib import Path

import streamlit as st

from metacog.cloud import bundle_bytes, new_run, restore_bundle, run_next
from metacog.core import ROOT, Workflow, case_paths, load_case, model_input, now, read_json, source_catalog, write_json
from metacog.evaluation import freeze, prepare_review, summarize, verify_manifest
from metacog.provider import GenerationError, generate, settings

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


def comparison_view(comparison, payload):
    safe_text(comparison["summary"])
    with st.expander("How the model interpreted the original reasoning", expanded=True):
        st.write("**Priorities**")
        safe_text(comparison["priorities_interpretation"])
        st.write("**Reasons**")
        safe_text(comparison["reasoning_interpretation"])
    catalog = source_catalog(payload)
    labels = {"support": "Supporting evidence", "constraint_conflict": "Firm requirement conflict",
              "tradeoff": "Flexible tradeoff", "unsupported_claim": "Unsupported claim", "uncertainty": "Unresolved information"}
    for item in comparison["findings"]:
        with st.container(border=True):
            st.write("**" + labels[item["kind"]] + "**")
            safe_text(item["text"])
            with st.expander("Inspect cited evidence"):
                for source_id in item["source_ids"]:
                    st.caption(source_id)
                    safe_text(json.dumps(catalog[source_id], ensure_ascii=False) if not isinstance(catalog[source_id], str) else catalog[source_id])
    st.write("**A question to consider**")
    safe_text(comparison["reflection_question"]["text"])
    with st.expander("Question sources and limits"):
        for source in comparison["reflection_question"]["source_ids"]:
            safe_text(source + ": " + str(catalog[source]))
        for limitation in comparison["limitations"]:
            safe_text(limitation)


def workspace(key):
    st.subheader("Explore a fictional travel decision")
    st.caption("Three destinations. Your reasoning first. Advice second. Then a chance to reflect.")
    cases = [load_case(p.stem) for p in case_paths("development")]
    options = {c["id"]: c for c in cases}
    selected = st.selectbox("Development scenario", list(options),
                            format_func=lambda i: i + " · " + options[i]["title"])
    if "flow" not in st.session_state:
        st.session_state.flow = Workflow(options[selected])
        st.session_state.workspace_generation_errors = []
    flow = st.session_state.flow
    if st.button("Start a new decision", help="Download any existing record first; this starts a separate record."):
        st.session_state.flow = Workflow(options[selected])
        st.session_state.workspace_generation_errors = []
        st.rerun()
    case, record = flow.case, flow.record
    names = {o["id"]: o["name"] for o in case["options"]}
    st.caption("Current decision: " + case["id"] + " · " + case["title"])
    st.info(case["context"])
    for col, option in zip(st.columns(3), case["options"]):
        with col, st.container(border=True):
            st.subheader(option["name"])
            for fact in option["facts"]:
                safe_text(fact["text"])
                st.caption("Source " + fact["id"])
    if record["stage"] == "initial":
        st.subheader("1 · Record initial reasoning")
        st.caption("The fields below contain a fictional traveler script. You can edit them for a demonstration; formal runs use the fixed scripts.")
        initial = case["initial"]
        with st.form("initial_form"):
            choice = st.selectbox("Initial destination", list(names), index=list(names).index(initial["choice"]), format_func=names.get)
            confidence = st.slider("Initial confidence", 0, 100, int(initial["confidence"]))
            priorities = st.text_area("Flexible priorities (one per line)", "\n".join(initial["priorities"]))
            constraints = st.text_area("Firm requirements (one per line; may be empty)", "\n".join(initial["constraints"]))
            reasons = st.text_area("Initial reasons", initial["reasons"])
            submitted = st.form_submit_button("Preserve initial reasoning", type="primary")
        if submitted:
            try:
                flow.commit_initial(dict(choice=choice, confidence=confidence, priorities=lines(priorities), constraints=lines(constraints), reasons=reasons))
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
        if record["stage"] == "committed":
            if st.button("Reveal scripted advice", type="primary"):
                flow.reveal()
                st.rerun()
        if record["advice"]:
            st.caption("PREWRITTEN RECOMMENDATION · This is the advice being examined, not a new model response.")
            safe_text(record["advice"]["text"])
        if record["stage"] == "advice":
            mode = st.radio("Comparison mode", ["Live Gemini", "Software preview (no LLM)"], index=0 if key else 1)
            if mode.startswith("Software"):
                st.warning("Preview checks the workflow only. It does not analyze this case or count as a study result.")
            if not key and mode == "Live Gemini":
                st.info("Add GEMINI_API_KEY in the cloud app's Settings → Secrets, then reboot the app.")
            if st.button("Generate comparison and question", disabled=mode == "Live Gemini" and not key, type="primary"):
                try:
                    with st.spinner("Comparing the stated reasoning with the evidence…"):
                        output, generation = generate(model_input(case, record["initial"]),
                                                      "live" if mode == "Live Gemini" else "fixture", api_key=key)
                    flow.attach_comparison(output, generation)
                    st.rerun()
                except (ValueError, GenerationError) as exc:
                    st.session_state.workspace_generation_errors.append({"at": now(), "error": str(exc), "generation": getattr(exc, "artifact", {})})
                    st.error(str(exc))
                    st.caption("No response was substituted. A new click makes a new attempt; failed attempts remain in the export.")
        if record["comparison"]:
            st.caption("LLM-GENERATED COMPARISON" if record["generation"]["backend"] == "live" else "SOFTWARE FIXTURE · NOT LLM-GENERATED")
            comparison_view(record["comparison"], model_input(case, record["initial"]))
    if record["comparison"]:
        st.subheader("3 · Record reflection and next decision")
        st.caption("The comparison refers to your preserved initial reasoning. New responses are saved separately; they do not rewrite the original or trigger another model call.")
        previous = record["followups"][-1] if record["followups"] else record["initial"]
        index = len(record["followups"])
        with st.form("followup_" + str(index)):
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
                flow.followup(dict(action=action, choice=None if action == "defer" else choice, confidence=confidence,
                                   priorities=lines(priorities), constraints=lines(constraints), reflection=reflection, reasons=reasons))
                st.rerun()
            except ValueError as exc:
                st.error(str(exc))
        for i, followup in enumerate(record["followups"], 1):
            with st.expander("Saved response %d · %s" % (i, followup["action"]), expanded=i == len(record["followups"])):
                judgment_view(followup, names)
                safe_text("Reflection: " + followup["reflection"])
    st.download_button("Download this decision record", json.dumps({**flow.public(), "generation_errors": st.session_state.workspace_generation_errors}, indent=2, ensure_ascii=False),
                       file_name=case["id"] + "_decision_record.json", mime="application/json")
    st.caption("Download before closing or refreshing the browser. This free cloud prototype does not promise permanent session storage.")


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


def research_console(key):
    st.subheader("Research runs · no participants")
    st.write("Run the fixed fictional scripts, review the generated artifacts, then freeze before holdout. One click processes one case. Nothing runs automatically.")
    st.warning("Download the run bundle after each case or review session. Cloud files can disappear on restart. Upload the bundle to resume.")
    if "research_temp" not in st.session_state:
        st.session_state.research_temp = tempfile.TemporaryDirectory(prefix="metacog_")
    base = Path(st.session_state.research_temp.name)
    current = st.session_state.get("research_path")
    if not current:
        if st.button("Start development run", disabled=not key):
            path = base / ("development_" + str(time.time_ns()))
            new_run(path, "development")
            st.session_state.research_path = str(path)
            st.rerun()
        upload = st.file_uploader("Restore a downloaded run bundle", type=["zip"])
        if upload and st.button("Restore run"):
            try:
                path = base / ("restored_" + str(time.time_ns()))
                restore_bundle(upload.getvalue(), path)
                st.session_state.research_path = str(path)
                st.rerun()
            except (ValueError, KeyError, OSError) as exc:
                st.error(str(exc))
        if not key:
            st.info("Set GEMINI_API_KEY in cloud Secrets to enable real model runs. Research runs never use software fixtures.")
        return
    path = Path(current)
    run = read_json(path / "run.json")
    total = len(run["case_ids"])
    count = run["succeeded"] + run["failed"]
    st.write("**Split:**", run["split"], "· **Completed attempts:**", count, "/", total)
    st.progress(count / total)
    st.caption("Successful outputs: %d · Technical failures: %d" % (run["succeeded"], run["failed"]))
    if run["status"] == "running":
        if st.button("Run next case with Gemini", disabled=not key):
            if time.time() - st.session_state.get("last_call", 0) < 10:
                st.info("Allow 10 seconds between requests to reduce free-tier rate-limit errors.")
            else:
                try:
                    st.session_state.last_call = time.time()
                    with st.spinner("Collecting one comparison and one reflection question…"):
                        run_next(path, key)
                    st.rerun()
                except (ValueError, GenerationError) as exc:
                    st.error(str(exc))
    else:
        review_editor(path)
    for case_id in run["case_ids"]:
        target = path / (case_id + ".json")
        if target.exists():
            attempt = read_json(target)
            if attempt["status"] == "error":
                st.error(case_id + ": " + attempt["error"])
    st.download_button("Download run bundle (outputs, reviews, and freeze if present)", bundle_bytes(path),
                       file_name=run["split"] + "_run_bundle.zip", mime="application/zip")
    if (path / "frozen.json").exists() and run["split"] == "development":
        acknowledged = st.checkbox("I downloaded the frozen development bundle and am ready to begin holdout testing")
        if st.button("Start holdout run", disabled=not acknowledged or not key):
            try:
                verify_manifest(path / "frozen.json")
                holdout = base / ("holdout_" + str(time.time_ns()))
                new_run(holdout, "holdout", path / "frozen.json")
                st.session_state.research_path = str(holdout)
                st.rerun()
            except ValueError as exc:
                st.error(str(exc))
    with st.expander("Switch to another saved run"):
        preserve = st.checkbox("I downloaded the current run bundle")
        if st.button("Close this run view", disabled=not preserve):
            del st.session_state.research_path
            st.rerun()


def main():
    st.title("Pause & Compare")
    st.caption("Supporting metacognitive monitoring in AI-assisted decision-making · CS 6795")
    key = api_key()
    with st.sidebar:
        st.subheader("Student travel workspace")
        st.write("Examine how advice fits your stated priorities, firm requirements, and evidence.")
        st.caption("All research scenarios and traveler responses are fictional.")
        st.divider()
        st.write("Model: " + settings()["model"])
        st.caption("One call per comparison · 1,800 output tokens maximum · No automatic retries")
        st.success("Cloud API key is configured") if key else st.info("Cloud API key not configured")
        page = st.radio("Open", ["Decision workspace", "Research console", "Setup and study boundaries"])
    if page == "Decision workspace":
        workspace(key)
    elif page == "Research console":
        research_console(key)
    else:
        st.subheader("What is scripted and what uses the LLM?")
        st.table({"Component": ["Destination descriptions", "Initial traveler profile and later responses", "Recommendation being examined", "Comparison and reflection question", "Review scores"],
                  "Source": ["Fixed fictional scripts", "Fixed fictional scripts during research; editable in demos", "Prewritten advice", "One real Gemini API call", "Researcher using predefined criteria"]})
        st.write("Deploy streamlit_app.py from a private GitHub repository on Streamlit Community Cloud. In Settings → Secrets add GEMINI_API_KEY. Keep your Gemini project on the free tier; the app does not enable billing or switch to paid models.")
        st.write("Free-tier quota depends on your account. An unavailable or limited model produces a recorded error. It is never replaced with a scripted answer.")
        st.write("The evaluation concerns tool outputs. It cannot show improved human reflection, reduced bias, increased trust, or better real decisions. Confidence values are fictional and are not metacognitive accuracy measurements.")
        st.info("No live development or holdout research outputs ship with this project. Complete development review and freeze the version before holdout.")


if __name__ == "__main__":
    main()
