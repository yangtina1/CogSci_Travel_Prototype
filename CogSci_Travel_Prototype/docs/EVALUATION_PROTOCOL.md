# Evaluation protocol v1.3 — interface revision, November 13, 2026

## Unit and scope

One initial comparison plus its one reflection question is the evaluation unit. Collect one output per case with the same model settings. There are 12 development and 12 holdout cases. This is an artifact evaluation, with no recruited users, survey, experimental treatment groups, or correct-destination accuracy metric. The shared browser interface accepts optional interactive follow-ups and saves them separately from the evaluated attempt. They are excluded from effectiveness measures. Optional CLI/software checks still use scripted follow-ups to test storage; neither kind establishes a human outcome.

The original protocol was prepared before live runs. This revision follows two user-supplied development demonstrations; it does not represent a completed research evaluation. A later structural revision balances holdout positions before evaluation, preserving all facts, named choices, expected reasoning, and reference meanings. No holdout model outputs informed that revision.

## Shared interface and evaluation sequence

The sidebar offers Development and Test immediately. Both use editable prefilled inputs and the same preserve → reveal → compare → respond flow. No software freeze or completed development run is required to open Test. This accessibility does not remove the methodological separation between development and evaluation.

1. Validate the software and inspect the development expectations. Use Development to check model access, collect outputs, review errors, and refine the comparison prompt or application. Record changes in `DEVELOPMENT_LOG.md`.
2. Before Test collection, save the selected code/commit, prompt, model settings, schema, data, expectations, rubric, and this protocol. Document readiness and known limitations. The browser records runtime and case hashes per experience; keep a full source archive as well because those hashes do not include the review rubric or every project file.
3. Collect one initial comparison/question per predefined Test case with unchanged initial inputs. Do not tune from these outputs. The same editable controls remain available for demonstrations; changed Test inputs are labeled exploratory and reviewed separately. Their existing gold expectations are not automatically valid.
4. Download each decision or the accumulated session ZIP after attempts. Keep every repeated experience and failure. The index identifies the split, edited inputs, comparison availability, failures, and reflections. Session ZIPs are review artifacts, not resumable CLI run bundles.
5. Review each comparison against the rubric, expected observations, and every-finding evidence audit below. Record ratings and rationales in a separate review table keyed to the exported filename and case ID; preserve raw exports unchanged. Keep development and Test results separate.
6. Optional reflections are provenance for the demonstration, not evidence of improved cognition. They append to the preserved initial comparison record and do not trigger another model call.

Optional CLI collection/review/freeze tools remain available with their own run format. Their stricter gates do not apply to the browser workflow. Choose one collection format for the planned evaluation and document it.

## Manual measures

`evaluation/rubric.json` defines anchored 0/1/2 ratings for priority fidelity, reasoning fidelity, evidence handling, tradeoff coverage, and question quality. Only tradeoff coverage allows `NA`, with justification. These dimensions are reported separately; do not average them into an unvalidated “metacognition score.”

For each prewritten observation, mark **covered / partial / missed** and explain ratings in the case rationale. These observations include expected reasoning behaviors and the reflection target; they are not a correct-choice label. Each expected observation counts once, even when the output repeats it.

Audit **every generated finding**, including extra findings not in the expectations, as **supported / partly_supported / unsupported**, with an evidence note. A reference to a valid fact ID is insufficient if the fact does not support the actual assertion. Inspect summaries, interpretations, and the question for additional errors and document them separately. The finding-level denominator is findings only; it must not be described as a rate over all sentences or all claims in the output.

When reading each output, inspect both the initial choice/reasons and AI-recommended choice/advice. Distinguish factual accuracy, firm-requirement compliance, and fit with flexible priorities; a true advice statement need not justify a recommendation. Check that a claim about a requirement or priority cites both the relevant destination evidence and that requirement or priority. Missing evidence for difficulty, accessibility, or an activity's availability must not become a confident claim. Destination role labels identify choices. The new target field identifies whose claim is assessed; colors reflect model-supplied categories and do not prove a claim. Audit incorrect role/target assignments and misleading colors as output/display errors. Do not require all finding categories in every case.

Rate questions for relevance, focus, evidence grounding, and neutrality, not whether a scripted follow-up changed the destination. A question that assumes a false premise, pressures acceptance of AI, treats reasonable disagreement as error, or presumes that priorities cannot change receives a low rating. Appropriate supported agreement should not require an invented concern.

## Descriptive analysis

- Report total attempts, successful valid outputs, and technical failures first.
- For each rubric dimension, report counts at 0, 1, and 2 and the NA count. State the applicable denominator.
- Report covered/partial/missed expected observations with their total. These are researcher-coded coverage counts, not objective destination accuracy or automatic precision/recall.
- Report supported/partly-supported/unsupported findings with the number of audited findings. A case with zero findings has zero finding denominator, not perfect evidence accuracy.
- Include representative omissions, misleading questions, correct uncertainty handling, and well-supported agreement. Do not choose only impressive examples.
- No inferential significance tests or human-effect claims are planned. A small synthetic case set with overlapping categories does not justify population estimates.

Exclude technical failures from semantic-rating denominators but retain them in attempted-case totals. The optional CLI summary tool uses this convention; browser ZIPs provide records and an index, not scores. Describe this distinction explicitly. No-output failures must not silently disappear from the study.

## Error and restart policy

- No automatic API retries, alternate models, or fixture fallbacks. Failed responses are retained where available. Repeated button clicks are additional attempts, not replacements.
- A quota failure is technical, not proof of bad reasoning. Preserve it before waiting for access recovery.
- Download before a session ends. The browser does not restore archives. After losing a session, consult saved records to continue unattempted cases and document any missing records.
- Document repeated attempts or a whole-run restart before inspecting replacement outputs. Never rerun selected cases just for better answers. Include failures in reporting and distinguish retries from independent cases.
- If a post-selection change is necessary, retain old results and explain the deviation. Cases whose outputs informed tuning cannot be presented as untouched holdout for the revised version; use fresh cases for that claim.

## Interpretation and authorship limits

The same author helped design and rate cases; the expectations are therefore subject to confirmation bias. The pack includes positive cases, reasonable disagreement, and false-positive auditing to make this visible, but they do not remove the bias. Optional independent checking could strengthen credibility but is not part of the promised design. No inter-rater reliability is claimed for a single reviewer. Document any later rubric change and why it was made.

Budget-conscious students are the design audience, not study participants. The model's semantic quality, cloud deployment, and free-tier access must be evaluated separately from software unit-test success. Do not report fixture results as model performance.
