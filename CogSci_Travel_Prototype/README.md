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

Use the normal app URL. In the sidebar, below **LLM status**, choose **Development** (D01–D12) or **Test** (H01–H12). Select a scenario to load it immediately. Both sets use the same editable interface. There is no research console, run-start control, or enforced freeze gate. Older research/setup URLs also open this interface.

1. Read the three fictional destinations and the fixed default budget-conscious student prompt. Edit your initial destination, confidence, priorities, firm requirements, and reasons as needed.
2. Choose **Preserve initial reasoning**, then **Reveal AI advice**. The prominent advice section retains the disclosure that advice is scripted for the demo; it does not change when you edit your preferences.
3. Choose **Generate comparison and question**. Gemini compares the actual preserved inputs with the evidence and advice in one call. The comparison summary appears above detailed findings. Without an API key, generation is disabled; there is no fake comparison.
4. Optionally record a reflection and retain, revise, or defer your decision. This appends a response without rewriting the initial record or making another LLM call.

Findings identify destinations and their roles. When both choices agree, the destination label says **Your choice and the AI recommendation**. Each finding also identifies whose claim is assessed: original reasoning, AI advice, both, or options compared. Green means a specific claim is supported; red means an unsupported claim or a firm requirement conflict; amber means unresolved information; blue means a flexible tradeoff. These are model classifications to inspect, not verified judgments or an overall endorsement of a destination. The evidence expander concerns the specific statement on that card. Categories appear only when generated; a tradeoff is not required in every case.

### Downloads after results

**Download this decision record** appears below the experience after a comparison or failed attempt. It saves the preserved inputs, displayed advice, comparison/question, model metadata, later reflections, errors, and runtime version hashes as JSON.

**Download all saved results (ZIP)** appears at the bottom once there is a result or failed attempt. It collects experiences across both data sets during the current browser session. Each experience has a JSON file; `results_index.json` lists the case, split, whether inputs match the predefined case, failures, comparison availability, and follow-up count. Adding a reflection updates that experience; starting the same case again creates a separate experience. The ZIP supports later report review and does not calculate a cognitive improvement score.

Download regularly and before refreshing, closing, or rebooting: session storage can disappear. The current interface does not restore ZIPs; keep downloads on your own storage for review. Switching cases saves completed comparisons and failed attempts in the session, but an initial draft without a comparison/error is not collected. Returning to a case starts a new decision; it does not regenerate anything unless you click Generate. **Start a new decision** resets the current case to its prefilled values.

### Development versus evaluation

Use Development for prompt/UI adjustments and the video demonstration. Before evaluating Test, save the chosen repository commit or source archive, model settings, rubric, and evaluation plan. This is a research procedure, not a software lock. For the planned standardized evaluation, leave Test's prefilled inputs unchanged and collect one comparison per case. Editable Test inputs are useful for exploration, but their outputs must be labeled separately; the export flags changed inputs and the original gold expectations may no longer apply.

Keep all attempts and repeated experiences, including failures. Do not tune using Test outputs and then describe the same cases as untouched holdout. Record any deviation. Both sets have 12 cases, with initial choices and AI recommendations each balanced at four A, four B, and four C. See `docs/EVALUATION_PROTOCOL.md` for manual review. Selecting Test does not make this a human-subject study or establish a benefit to human cognition.

## Which prompt can be revised?

`prompts/comparison.txt` is the shared instruction given to the comparison LLM for every case. It tells the model how to distinguish firm requirements from flexible preferences, cite evidence, represent uncertainty, and ask a non-leading question. It is the main prompt to refine during development.

The case files contain the evidence and scripted reasoning/advice that the model examines. They are not prompts asking the LLM to generate a travel recommendation. Correct a case-authoring error if necessary and document it, but do not rewrite a difficult scenario just to make the model succeed. Keep the testing cases and evaluation criteria fixed once testing begins.

## Files

- `streamlit_app.py`: interactive interface and session downloads.
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
