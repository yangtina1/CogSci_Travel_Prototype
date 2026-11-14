"""Shared contracts and workflow. No network calls and no evaluation labels here."""
import copy
import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def now():
    return datetime.now(timezone.utc).isoformat()


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_json(path, value, exclusive=False):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    if exclusive:
        with path.open("x", encoding="utf-8") as stream:
            stream.write(text)
    else:
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(text, encoding="utf-8")
        tmp.replace(path)


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                     allow_nan=False).encode()).hexdigest()


def export_experiences(experiences):
    """Portable session results for manual analysis, without implying automatic scores."""
    import io
    import zipfile
    stream = io.BytesIO()
    index = {"format": "pause_compare_sessions_v1", "exported_at": now(),
             "note": "Experiences are not independent participants or automatic effectiveness scores. Preserve edited inputs, failures, and repeated cases when reporting results.",
             "experiences": []}
    with zipfile.ZipFile(stream, "w", zipfile.ZIP_DEFLATED) as archive:
        for number, experience in enumerate(experiences, 1):
            record = experience["record"]
            case_id = experience["case"]["id"]
            name = "%03d_%s_decision_record.json" % (number, case_id)
            comparison_available = bool(record.get("comparison") and (record.get("generation") or {}).get("backend") == "live")
            errors = len(experience.get("generation_errors", []))
            index["experiences"].append({"file": name, "case_id": case_id, "split": experience["split"],
                "created_at": record["created_at"], "input_matches_predefined_case": experience["input_matches_predefined_case"],
                "comparison_available": comparison_available, "recorded_failures": errors,
                "recorded_generation_attempts": errors + int(comparison_available),
                "followup_count": len(record["followups"])})
            archive.writestr(name, json.dumps(experience, indent=2, ensure_ascii=False))
        archive.writestr("results_index.json", json.dumps(index, indent=2, ensure_ascii=False))
    return stream.getvalue()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def nonempty(value, name, limit=6000):
    require(isinstance(value, str) and 0 < len(value.strip()) <= limit,
            name + " must be nonempty text (maximum %d characters)." % limit)


def text_list(value, name, allow_empty=False):
    require(isinstance(value, list) and len(value) <= 20, name + " must be a list (at most 20).")
    require(allow_empty or len(value) > 0, name + " needs at least one item.")
    for item in value:
        nonempty(item, name, 1000)


def validate_judgment(judgment, options):
    require(isinstance(judgment, dict), "Judgment must be an object.")
    require(set(judgment) == {"choice", "confidence", "priorities", "constraints", "reasons"},
            "Judgment fields must be choice, confidence, priorities, constraints, reasons.")
    require(judgment["choice"] in options, "Choose one of the three destinations.")
    confidence = judgment["confidence"]
    require(type(confidence) in (int, float) and math.isfinite(confidence)
            and 0 <= confidence <= 100, "Confidence must be a number from 0 to 100.")
    text_list(judgment["priorities"], "Priorities")
    text_list(judgment["constraints"], "Constraints", allow_empty=True)
    nonempty(judgment["reasons"], "Reasons")


def validate_case(case):
    require(set(case) == {"id", "title", "context", "options", "initial", "advice", "followups"},
            "Unexpected scenario fields; labels belong in evaluation/gold.")
    for field in ("id", "title", "context"):
        nonempty(case[field], field)
    require(len(case["options"]) == 3, "Each case needs exactly three options.")
    ids, facts = set(), set()
    for option in case["options"]:
        require(set(option) == {"id", "name", "facts"}, "Invalid option fields.")
        require(option["id"] not in ids, "Duplicate option ID.")
        ids.add(option["id"])
        nonempty(option["name"], "Destination name")
        require(len(option["facts"]) > 0, "Destination needs evidence.")
        for fact in option["facts"]:
            require(set(fact) == {"id", "text"}, "Invalid fact fields.")
            require(fact["id"] not in facts and fact["id"].startswith(option["id"] + "."),
                    "Fact IDs must be unique and start with the option ID.")
            facts.add(fact["id"])
            nonempty(fact["text"], "Fact")
    validate_judgment(case["initial"], ids)
    require(set(case["advice"]) == {"choice", "text"}, "Invalid advice fields.")
    require(case["advice"]["choice"] in ids, "Unknown advice option.")
    nonempty(case["advice"]["text"], "Advice")
    require(isinstance(case["followups"], list) and case["followups"], "Scripted follow-up required.")
    previous = case["initial"]["choice"]
    for followup in case["followups"]:
        validate_followup(followup, ids, previous)
        previous = followup["choice"]
    return case


def validate_followup(value, options, previous):
    require(set(value) == {"action", "choice", "confidence", "priorities", "constraints", "reasons", "reflection"},
            "Unexpected follow-up fields.")
    require(value["action"] in ("retain", "revise", "defer"), "Choose retain, revise, or defer.")
    if value["action"] == "defer":
        require(value["choice"] is None, "A deferred decision has no final destination.")
    else:
        require(value["choice"] in options, "Choose a valid destination.")
        if value["action"] == "retain":
            require(previous is not None and value["choice"] == previous,
                    "Retain must keep the preceding choice; use revise to choose again after deferral.")
        else:
            require(value["choice"] != previous, "Revise must change the preceding choice.")
    check = {key: value[key] for key in ("choice", "confidence", "priorities", "constraints", "reasons")}
    if check["choice"] is None:
        check["choice"] = next(iter(options))
    validate_judgment(check, options)
    nonempty(value["reflection"], "Reflection")


def case_paths(split):
    require(split in ("development", "holdout"), "Unknown split.")
    return sorted((ROOT / "data" / split).glob("*.json"))


def load_case(case_id, split="development"):
    # Match inventory, rather than letting a client-supplied name become a path.
    for path in case_paths(split):
        if path.stem == case_id:
            return validate_case(read_json(path))
    raise ValueError("Unknown case ID.")


def model_input(case, initial):
    """Explicit allowlist: no gold labels, follow-ups, split labels, or expected answers."""
    validate_judgment(initial, {o["id"] for o in case["options"]})
    return copy.deepcopy({"context": case["context"], "options": case["options"],
                          "initial": initial, "advice": case["advice"]})


def source_catalog(payload):
    catalog = {fact["id"]: fact["text"] for option in payload["options"] for fact in option["facts"]}
    for field, value in payload["initial"].items():
        catalog["initial." + field] = value
    catalog["advice"] = payload["advice"]["text"]
    return catalog


def validate_schema(value, schema, path="output"):
    """Validator for the deliberately small JSON-schema subset used by this project."""
    kind = schema["type"]
    ok = {"object": isinstance(value, dict), "array": isinstance(value, list),
          "string": isinstance(value, str), "number": type(value) in (int, float),
          "integer": type(value) is int, "boolean": type(value) is bool,
          "null": value is None}[kind]
    require(ok, path + " must be " + kind)
    if "enum" in schema:
        require(value in schema["enum"], path + " has an unknown value.")
    if kind == "object":
        require(set(schema.get("required", [])) <= set(value), path + " lacks required fields.")
        if schema.get("additionalProperties") is False:
            require(set(value) <= set(schema["properties"]), path + " has extra fields.")
        for key, item in value.items():
            validate_schema(item, schema["properties"][key], path + "." + key)
    elif kind == "array":
        for i, item in enumerate(value):
            validate_schema(item, schema["items"], path + "[%d]" % i)


def validate_comparison(value, payload):
    validate_schema(value, read_json(ROOT / "schemas/comparison.json"))
    for field in ("priorities_interpretation", "reasoning_interpretation", "summary"):
        nonempty(value[field], field)
    catalog = source_catalog(payload)
    option_ids = {o["id"] for o in payload["options"]}
    require(len(value["findings"]) <= 6, "At most 6 findings are allowed.")
    for finding in value["findings"]:
        nonempty(finding["text"], "Finding")
        require(finding["option_ids"] and set(finding["option_ids"]) <= option_ids,
                "Finding has unknown or empty option IDs.")
    for item in value["findings"] + [value["reflection_question"]]:
        text_list(item["source_ids"], "Evidence references")
        require(set(item["source_ids"]) <= set(catalog), "Unknown evidence reference.")
    nonempty(value["reflection_question"]["text"], "Reflection question", 1200)
    text_list(value["limitations"], "Limitations")
    # Valid source IDs do not establish semantic entailment. That requires manual review.
    return value


class Workflow:
    def __init__(self, case, record=None):
        self.case = validate_case(copy.deepcopy(case))
        self.record = copy.deepcopy(record) if record else {
            "case_id": case["id"], "created_at": now(), "stage": "initial",
            "initial": None, "advice": None, "comparison": None,
            "generation": None, "followups": [], "events": []}

    def event(self, name):
        self.record["events"].append({"event": name, "at": now()})

    def commit_initial(self, initial):
        require(self.record["stage"] == "initial", "Initial reasoning is already preserved.")
        validate_judgment(initial, {o["id"] for o in self.case["options"]})
        self.record["initial"] = copy.deepcopy(initial)
        self.record["stage"] = "committed"
        self.event("initial_committed")

    def reveal(self):
        require(self.record["stage"] == "committed", "Record initial reasoning before revealing advice.")
        self.record["advice"] = copy.deepcopy(self.case["advice"])
        self.record["stage"] = "advice"
        self.event("advice_revealed")

    def attach_comparison(self, comparison, generation):
        require(self.record["stage"] == "advice", "Reveal advice before requesting one comparison.")
        validate_comparison(comparison, model_input(self.case, self.record["initial"]))
        self.record["comparison"] = copy.deepcopy(comparison)
        self.record["generation"] = copy.deepcopy(generation)
        self.record["stage"] = "reflection"
        self.event("comparison_attached")

    def followup(self, value):
        require(self.record["stage"] in ("reflection", "complete"), "Read the comparison before responding.")
        previous = (self.record["followups"][-1] if self.record["followups"]
                    else self.record["initial"])["choice"]
        validate_followup(value, {o["id"] for o in self.case["options"]}, previous)
        self.record["followups"].append(copy.deepcopy(value))
        self.record["stage"] = "complete"
        self.event("followup_appended")

    def public(self):
        # Before commitment, neither advice nor scripted follow-ups reach the browser.
        return {"case": {k: copy.deepcopy(self.case[k]) for k in ("id", "title", "context", "options")},
                "record": copy.deepcopy(self.record)}
