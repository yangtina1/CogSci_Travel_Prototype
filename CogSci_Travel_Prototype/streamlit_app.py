"""Online Python prototype. Deploy this entrypoint on Streamlit Community Cloud."""
import json
import copy
import os
import hashlib

import streamlit as st

from metacog.core import ROOT, Workflow, case_paths, digest, export_experiences, load_case, model_input, now, source_catalog
from metacog.provider import GenerationError, comparison_error_message, generate

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
    with st.container(border=True):
        st.subheader("Comparison at a glance")
        safe_text(comparison["summary"])
    with st.expander("How the model interpreted the original reasoning", expanded=False):
        st.write("**Priorities**")
        safe_text(comparison["priorities_interpretation"])
        st.write("**Reasons**")
        safe_text(comparison["reasoning_interpretation"])
    labels = {"support": "Supported by supplied evidence", "constraint_conflict": "Firm requirement conflict",
              "tradeoff": "Flexible tradeoff", "unsupported_claim": "Not supported by supplied evidence",
              "uncertainty": "Unresolved information"}
    targets = {"initial_reasoning": "Original choice / reasoning", "ai_advice": "AI advice",
               "both": "Original choice and AI advice", "options": "Options compared"}
    names = {option["id"]: option["name"] for option in payload["options"]}
    st.subheader("Check the evidence")
    st.caption("Green: supported claim. Red: unsupported claim or firm requirement conflict. Amber: unresolved information. Blue: flexible tradeoff. These are the model's assessments of specific statements, not overall destination endorsements; inspect the cited evidence.")
    for item in comparison["findings"]:
        # The target is separate from option IDs: mentioning an option does not assign it blame.
        target = item.get("target")
        heading = targets.get(target, "Specific finding") + " · " + labels[item["kind"]]
        render_label = {"support": st.success, "constraint_conflict": st.error,
                        "unsupported_claim": st.error, "uncertainty": st.warning,
                        "tradeoff": st.info}[item["kind"]]
        render_label(heading)
        for option_id in dict.fromkeys(item["option_ids"]):
            is_initial = option_id == payload["initial"]["choice"]
            is_advice = option_id == payload["advice"]["choice"]
            if is_initial and is_advice:
                role = "Your choice and the AI recommendation"
            elif is_initial:
                role = "Your initial choice"
            elif is_advice:
                role = "AI-recommended option"
            else:
                role = "Other option"
            st.caption(names[option_id] + " · " + role)
        safe_text(item["text"])
        with st.expander("Evidence for this specific finding"):
            evidence_view(payload, item["source_ids"])
    st.write("**A question to consider**")
    safe_text(comparison["reflection_question"]["text"])
    with st.expander("Question sources and limits"):
        evidence_view(payload, comparison["reflection_question"]["source_ids"])
        st.caption("Limits of this comparison")
        for limitation in comparison["limitations"]:
            safe_text(limitation)


def decision_version(case):
    # Record the runtime version without depending on batch-review files.
    names = ("streamlit_app.py", "metacog/core.py", "metacog/provider.py", "prompts/comparison.txt",
             "config/model.json", "schemas/comparison.json", "requirements.txt")
    return {"files": {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in names},
            "case_hash": digest(case)}


def current_experience():
    flow = st.session_state.flow
    split = st.session_state.flow_scope
    return {**flow.public(), "purpose": "development_session" if split == "development" else "test_session",
            "split": split, "input_matches_predefined_case": flow.record["initial"] == flow.case["initial"],
            "version": copy.deepcopy(st.session_state.get("workspace_version")), "followups_used_for_effectiveness": False,
            "generation_errors": copy.deepcopy(st.session_state.workspace_generation_errors)}


def remember_experience():
    if "flow" not in st.session_state:
        return
    record = st.session_state.flow.record
    has_output = record["comparison"] and (record.get("generation") or {}).get("backend") == "live"
    if has_output or st.session_state.get("workspace_generation_errors"):
        if "saved_experiences" not in st.session_state:
            st.session_state.saved_experiences = {}
        identity = st.session_state.flow_scope + ":" + record["case_id"] + ":" + record["created_at"]
        st.session_state.saved_experiences[identity] = current_experience()


def workspace(key, split="development"):
    scope = split
    st.subheader("Explore a fictional travel decision")
    st.caption("Three destinations. Your reasoning first. Advice second. Then a chance to reflect.")
    options = {p.stem: load_case(p.stem, split) for p in case_paths(split)}
    selected = st.selectbox("Scenario", list(options), key="scenario_" + scope,
                            format_func=lambda i: i + " · " + options[i]["title"])

    def open_case(case_id):
        st.session_state.flow = Workflow(options[case_id])
        st.session_state.flow_scope = scope
        st.session_state.workspace_generation_errors = []
        st.session_state.workspace_version = None
        st.session_state.decision_serial = st.session_state.get("decision_serial", 0) + 1

    if ("flow" not in st.session_state or st.session_state.get("flow_scope") != scope
            or st.session_state.flow.case["id"] != selected):
        open_case(selected)
    st.caption("Results are kept during this session. Download them below before refreshing or closing the page.")
    if st.button("Start a new decision", help="Reset this scenario to its prefilled starting values."):
        open_case(selected)
        st.rerun()
    flow = st.session_state.flow
    case, record = flow.case, flow.record
    widget_scope = scope + ":" + case["id"] + ":" + str(st.session_state.get("decision_serial", 0))
    live_comparison = bool(record["comparison"] and (record.get("generation") or {}).get("backend") == "live")
    names = {o["id"]: o["name"] for o in case["options"]}
    st.caption("Current decision: " + case["id"] + " · " + case["title"])
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
        st.caption("Edit these fictional starting values to use the app. Advice stays scripted, so it may not match your edits.")
        initial = case["initial"]
        initial_area = st.empty()
        with initial_area.container(), st.form("initial_" + widget_scope):
            choice = st.selectbox("Initial destination", list(names), index=list(names).index(initial["choice"]), format_func=names.get, key="initial_choice_" + widget_scope)
            confidence = st.slider("Initial confidence", 0, 100, int(initial["confidence"]), key="initial_confidence_" + widget_scope)
            priorities = st.text_area("Flexible priorities (one per line)", "\n".join(initial["priorities"]), key="initial_priorities_" + widget_scope)
            constraints = st.text_area("Firm requirements (one per line; may be empty)", "\n".join(initial["constraints"]), key="initial_constraints_" + widget_scope)
            reasons = st.text_area("Initial reasons", initial["reasons"], key="initial_reasons_" + widget_scope)
            submitted = st.form_submit_button("Preserve initial reasoning", type="primary")
        if submitted:
            try:
                value = dict(choice=choice, confidence=confidence, priorities=lines(priorities), constraints=lines(constraints), reasons=reasons)
                flow.commit_initial(value)
                initial_area.empty()
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
            st.header("AI advice")
            with st.container(border=True):
                safe_text(record["advice"]["text"])
        if record["stage"] == "advice":
            if not key:
                st.info("The LLM is not connected. You can view the demo advice, but a comparison and reflection question will be available only after the LLM is configured.")
            if st.button("Generate comparison and question", disabled=not key, type="primary"):
                try:
                    with st.spinner("Comparing the stated reasoning with the evidence…"):
                        st.session_state.workspace_version = decision_version(case)
                        output, generation = generate(model_input(case, record["initial"]), "live", api_key=key)
                        flow.attach_comparison(output, generation)
                    st.rerun()
                except (ValueError, GenerationError, OSError) as exc:
                    st.session_state.workspace_generation_errors.append({"at": now(), "error": str(exc), "generation": getattr(exc, "artifact", {})})
                    st.error(comparison_error_message(exc))
                    st.caption("No comparison was generated. Your original reasoning is preserved.")
        if live_comparison:
            st.header("AI comparison of your reasoning and the advice")
            comparison_view(record["comparison"], model_input(case, record["initial"]))
        elif record["comparison"]:
            st.info("This decision contains an earlier software preview, not an LLM comparison. Download the record if needed, then start a new decision to request a real comparison.")
    if live_comparison:
        st.subheader("3 · Record reflection and next decision")
        st.caption("The comparison refers to your preserved initial reasoning. New responses are saved separately; they do not rewrite the original or trigger another model call. These responses are not evidence of improved human decision-making.")
        previous = record["followups"][-1] if record["followups"] else record["initial"]
        index = len(record["followups"])
        followup_area = st.empty()
        with followup_area.container(), st.form("followup_" + widget_scope + "_" + str(index)):
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
                flow.followup(response)
                followup_area.empty()
                st.rerun()
            except (ValueError, OSError) as exc:
                st.error(str(exc))
        for i, followup in enumerate(record["followups"], 1):
            with st.expander("Saved response %d · %s" % (i, followup["action"]), expanded=i == len(record["followups"])):
                judgment_view(followup, names)
                safe_text("Reflection: " + followup["reflection"])
    if live_comparison or st.session_state.workspace_generation_errors:
        st.download_button("Download this decision record", json.dumps(current_experience(), indent=2, ensure_ascii=False),
                           file_name=case["id"] + "_decision_record.json", mime="application/json", key="download_decision_" + widget_scope)
        st.caption("Optional: save this experience, including your inputs, comparison, reflection, and any errors.")


def main():
    # Capture the preceding experience before a widget switches data sets or cases.
    remember_experience()
    st.title("Pause & Compare")
    st.caption("Supporting metacognitive monitoring in AI-assisted decision-making · CS 6795")
    key = api_key()
    with st.sidebar:
        st.subheader("LLM status")
        if key:
            st.success("LLM configured")
        else:
            st.info("LLM not connected")
        mode = st.selectbox("Data set", ["Development", "Test"], key="dataset_choice")
        st.caption("Development: D01–D12 · Test: H01–H12")
    try:
        workspace(key, "development" if mode == "Development" else "holdout")
    except (ValueError, OSError, KeyError) as exc:
        st.error("Could not open the selected scenario. " + str(exc))
    remember_experience()
    saved = st.session_state.get("saved_experiences", {})
    if saved:
        st.download_button("Download all saved results (ZIP)", export_experiences(list(saved.values())),
                           file_name="travel_comparison_results.zip", mime="application/zip", key="download_all_results")
        st.caption("%d experience(s) saved in this session, including failed attempts and any updated reflections. The ZIP includes an index for your report; it does not score effectiveness. Download before refreshing or closing." % len(saved))


if __name__ == "__main__":
    main()
