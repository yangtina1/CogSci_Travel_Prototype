# Evaluation protocol v1.0 — prepared before live runs

## Unit and scope

One initial comparison plus its one reflection question is the evaluation unit. Collect one output per case with the same model settings. There are 12 development and 12 holdout cases. This is an artifact evaluation, with no recruited users, survey, experimental treatment groups, or correct-destination accuracy metric. Scripted follow-ups test storage and action handling; they are not caused by the generated question and are not human outcome measurements.

## Sequence

1. Confirm data and software checks. Inspect the development case expectations. Correct data authoring mistakes before live collection.
2. Set up the free-tier model account. Collect the 12 development outputs through Research console, preserving every attempt. Check API compatibility and real model behavior; this has **not** been done in the delivered preparation package.
3. Review development outputs using the five rubric dimensions, case-specific observations, and every-finding evidence audit. Record concrete failures, examples, and any prompt/app changes in your research notes.
4. If changing code, prompts, schema, model/settings, rubric, or data, preserve the old run and collect a new development run under the final candidate. Do not tune against holdout model outputs.
5. Freeze only after all 12 development calls succeed and a complete manual review records readiness. Low quality scores are not automatically disqualifying: document limitations and decide whether the prototype is ready. The gate checks review completeness, not a hidden quality threshold.
6. Download the frozen development bundle. The freeze records hashes of code, configuration, prompts, schema, rubric/protocol, both input sets, and both expectation sets. The app will reject changed files.
7. Start one holdout run. Do not inspect holdout outputs to tune the implementation. Preserve successful responses and technical failures; do not selectively replace weak outputs.
8. Review and summarize holdout using the frozen criteria. Save qualitative examples and discuss mistakes and limitations. Keep development results separate from holdout results.

## Manual measures

`evaluation/rubric.json` defines anchored 0/1/2 ratings for priority fidelity, reasoning fidelity, evidence handling, tradeoff coverage, and question quality. Only tradeoff coverage allows `NA`, with justification. These dimensions are reported separately; do not average them into an unvalidated “metacognition score.”

For each prewritten observation, mark **covered / partial / missed** and explain ratings in the case rationale. These observations include expected reasoning behaviors and the reflection target; they are not a correct-choice label. Each expected observation counts once, even when the output repeats it.

Audit **every generated finding**, including extra findings not in the expectations, as **supported / partly_supported / unsupported**, with an evidence note. A reference to a valid fact ID is insufficient if the fact does not support the actual assertion. Inspect summaries, interpretations, and the question for additional errors and document them separately. The finding-level denominator is findings only; it must not be described as a rate over all sentences or all claims in the output.

Rate questions for relevance, focus, evidence grounding, and neutrality, not whether a scripted follow-up changed the destination. A question that assumes a false premise, pressures acceptance of AI, treats reasonable disagreement as error, or presumes that priorities cannot change receives a low rating. Appropriate supported agreement should not require an invented concern.

## Descriptive analysis

- Report total attempts, successful valid outputs, and technical failures first.
- For each rubric dimension, report counts at 0, 1, and 2 and the NA count. State the applicable denominator.
- Report covered/partial/missed expected observations with their total. These are researcher-coded coverage counts, not objective destination accuracy or automatic precision/recall.
- Report supported/partly-supported/unsupported findings with the number of audited findings. A case with zero findings has zero finding denominator, not perfect evidence accuracy.
- Include representative omissions, misleading questions, correct uncertainty handling, and well-supported agreement. Do not choose only impressive examples.
- No inferential significance tests or human-effect claims are planned. A small synthetic case set with overlapping categories does not justify population estimates.

The summary tool excludes technical failures from semantic-rating denominators but retains them in attempted-case totals. Describe this distinction explicitly. No-output failures must not silently disappear from the study.

## Error and restart policy

- There are no automatic API retries, alternate models, or fixture fallbacks. The raw failed response is retained where available.
- A free-tier quota error is a technical failure, not evidence that the model reasoned incorrectly. Wait for quota recovery before the next unattempted case.
- Downloads preserve incremental runs. After a restart, restore the bundle rather than creating duplicate successful cases. An interrupted started attempt is recorded as a technical failure; it is not silently retried.
- If a development run contains errors, resolve access or configuration and start a new clearly named development run; retain the failed run. All 12 cases must succeed for the freeze gate.
- If holdout fails for a systemic infrastructure issue, retain the original run. Decide and document a whole-run restart before examining replacement outputs; label the new run and report the earlier failures. Never rerun selected cases to obtain better-looking answers.
- A necessary post-freeze code, prompt, data, or rubric fix invalidates that frozen study. Document it as a deviation; previously inspected cases cannot be presented as untouched holdout. Create a new evaluation set if using their results to tune.

## Interpretation and authorship limits

The same author helped design and rate cases; the expectations are therefore subject to confirmation bias. The pack includes positive cases, reasonable disagreement, and false-positive auditing to make this visible, but they do not remove the bias. Optional independent checking could strengthen credibility but is not part of the promised design. No inter-rater reliability is claimed for a single reviewer. Document any later rubric change and why it was made.

Budget-conscious students are the design audience, not study participants. The model's semantic quality, cloud deployment, and free-tier access must be evaluated separately from software unit-test success. Do not report fixture results as model performance.
