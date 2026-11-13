# Supporting Metacognitive Monitoring in AI-Assisted Decision-Making

CS 6795 Cognitive Science · Ting-An Yang · Computational Model/Tool project

This Python prototype helps inspect how scripted travel advice relates to a fictional student's stated priorities, firm requirements, and reasons. The intended context is budget-conscious university students planning a short leisure trip. The evaluation concerns the tool's outputs, not measured improvements in human thinking or decision quality.

## Run online

This folder contains the complete uploadable app. It does not contain API credentials, development automation, or generated study results.

1. Upload this folder's contents to your private GitHub repository. Keep the folders and files together, including `.streamlit/config.toml`. On macOS, Command–Shift–. shows hidden files in Finder.
2. In Streamlit Community Cloud, choose your repository and branch. If the contents are at the repository root, select `streamlit_app.py` as the main file. If you uploaded the enclosing folder, select `CogSci_Travel_Prototype/streamlit_app.py` instead.
3. Choose Python 3.12 in Advanced settings. The supplied `requirements.txt` installs Streamlit.
4. Add the following in the cloud app's Secrets settings, replacing the placeholder there only:

```toml
GEMINI_API_KEY = "your-key-here"
```

5. Deploy and open the online URL. Keep the app private while developing and evaluating it.

Create your key through Google AI Studio in a project eligible for the free tier. The configured model is `gemini-3.5-flash-lite`; availability and quota depend on the account. Keep paid billing disabled if you want free-only usage. The app makes one API call per comparison, caps output at 1,800 tokens, uses minimal thinking, and does not retry automatically or switch to a paid model. Only fictional data should be entered.

Streamlit can run an entrypoint in a repository subfolder and find the dependency file beside it. Its documented configuration location is the repository-root `.streamlit/config.toml`; uploading the folder's contents at the repository root is the simplest way to preserve the supplied appearance and configuration. If you retain the enclosing folder, keep its config file in place for consistent styling; the app's functional code uses paths relative to its own location. See [Streamlit file organization](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/file-organization).

## One interface, two data sets

Use the normal app URL. The **Data set** selector switches between **Development** and **Final evaluation**. Older `?view=research` and `?view=setup` links now open the same interface. The sidebar shows only LLM status; model setup is in a collapsed section at the bottom.

Both modes use the same three steps: preserve initial reasoning, reveal scripted AI advice and request a comparison, then optionally record a reflection and next decision. The visible default travel prompt keeps the budget-conscious student context fixed. Destination descriptions and advice are scripted; Gemini generates only the comparison and one reflection question. The advice disclosure stays visible. Findings name the destination and its role, and distinguish requirement conflicts, preference tradeoffs, unsupported claims, and uncertainty. Support applies to a particular finding, not to a destination overall.

### Development and video demonstration

Initial destination, confidence, priorities, requirements, and reasons are editable. Select a scenario, then **Start a new decision** to load it. Preserve your reasoning before revealing the advice. Later responses stay separate from the original reasoning and do not make another model call. Download a decision record before replacing an exploratory decision or refreshing the page. Edited inputs may conflict with the fixed advice; exposing that mismatch is part of the prototype.

### Collect fixed cases, review, and freeze

1. In Development, expand **Evaluation records, review, and downloads** and choose **Start development run**. Leave **Use saved development run** checked.
2. Choose a case and **Open selected case**. Keep its initial fields unchanged, preserve them, reveal advice, and generate the comparison. Repeat for all 12 cases. Order is selectable; each case is recorded only once. Reopening a collected case displays its saved result without another API call.
3. Edits remain allowed, but an edited case is explicitly labeled exploratory and is excluded from the fixed run. Use **Open selected case** to reload its original inputs for collection. Turn off **Use saved development run** for independent demonstrations; the run remains saved.
4. Download the run bundle regularly. When all attempts finish, enable **Show evaluation review and freeze tools**, select **Prepare review packet**, and complete all ratings, finding audits, and rationales. Preserve failed attempts. A run with failures cannot be frozen; resolve the problem and start a new development run with a documented reason.
5. After all 12 successful cases are reviewed, mark readiness and choose **Freeze reviewed development version**. Download the frozen bundle. Any code, prompt, data, rubric or settings change requires a new development run and freeze.

### Final evaluation

Select **Final evaluation**. It stays locked until a matching reviewed development freeze exists or is restored from a downloaded bundle. In **Evaluation records, review, and downloads**, confirm you downloaded that bundle, then **Start final evaluation**.

Select a holdout case and **Open selected case**. The same initial fields appear prefilled and locked; the server uses the predefined values even if a browser sends different values. Preserve the initial record, reveal advice, and request one comparison per case. Follow-up fields remain editable, but responses are saved separately and excluded from claims about effectiveness. They do not change the evaluated input/output or invalidate existing reviews. All 12 attempts must finish before the review tools appear. Do not tune from holdout outputs and then report those cases as untouched tests.

Each set has 12 cases, with initial choices and AI recommendations each balanced at four A, four B, and four C. Position corrections preserved facts and named choices and remapped all references. The holdout was reordered before evaluation, without using model outputs.

### Downloads and recovery

**Download this decision record** exports the current experience with its split and exploratory/evaluation label. **Download run bundle** preserves all collected attempts, raw model responses, optional follow-ups, review, and freeze. Restore a downloaded bundle in the same panel after a restart. Restoring does not repeat attempts. Version checks prevent mixing old results with updated files. Do not re-upload an old bundle to a changed app expecting it to qualify for the new version.

Missing required files are reported by relative path. Preserve the folder structure, including the evaluation protocol and gold expectations. `.streamlit/config.toml` is optional when beginning a run; adding/removing it later changes the tracked version. No API key is written to exports. Keep the app's cloud sharing settings private during development and evaluation.

## Which prompt can be revised?

`prompts/comparison.txt` is the shared instruction given to the comparison LLM for every case. It tells the model how to distinguish firm requirements from flexible preferences, cite evidence, represent uncertainty, and ask a non-leading question. It is the main prompt to refine during development.

The case files contain the evidence and scripted reasoning/advice that the model examines. They are not prompts asking the LLM to generate a travel recommendation. Correct a case-authoring error if necessary and document it, but do not rewrite a difficult scenario just to make the model succeed. Keep the testing cases and evaluation criteria fixed once testing begins.

## Files

- `streamlit_app.py`: shared interface, evaluation collection, and review tools.
- `metacog/`: workflow, Gemini connection, validation, review, and record handling.
- `config/model.json`: model and generation settings.
- `prompts/comparison.txt`: shared comparison instructions.
- `schemas/comparison.json`: output structure.
- `data/`: development and testing scenarios.
- `evaluation/rubric.json`: rating criteria.
- `evaluation/gold/`: case-specific expected observations, used only for review and never sent to Gemini.
- `docs/EVALUATION_PROTOCOL.md`: evaluation procedure.
- `requirements.txt`, `.streamlit/config.toml`, `.gitignore`: deployment settings and exclusions.

## Status and AI assistance

Two earlier user-provided live demonstrations informed revisions. No complete standardized study, holdout model evaluation, or human-subject experiment has been completed by the agent. Offline software tests do not establish model quality or human benefit.

AI assistance contributed to code, fictional cases, evaluation materials, and documentation. The researcher must review these materials, make the substantive evaluation judgments, and develop the cognitive-science analysis. Update this acknowledgment to reflect actual use in the final submission.
