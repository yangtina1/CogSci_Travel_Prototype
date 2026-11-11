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

Create your key through Google AI Studio in a project eligible for the free tier. The configured model is `gemini-2.5-flash-lite`; availability and quota depend on the account. Keep paid billing disabled if you want free-only usage. The app makes one API call per comparison, caps output at 1,800 tokens, disables thinking, and does not retry automatically or switch to a paid model. Only fictional data should be entered.

Streamlit can run an entrypoint in a repository subfolder and find the dependency file beside it. Its documented configuration location is the repository-root `.streamlit/config.toml`; uploading the folder's contents at the repository root is the simplest way to preserve the supplied appearance and configuration. If you retain the enclosing folder, keep its config file in place for the study's file checks; the app's functional code uses paths relative to its own location. See [Streamlit file organization](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/file-organization).

## What the app does

1. Show three fictional destinations and their evidence.
2. Preserve an initial choice, confidence, priorities, requirements, and reasons.
3. Reveal a prewritten recommendation.
4. Use Gemini to compare the reasoning and advice with the evidence and generate one reflection question.
5. Preserve subsequent reflection, retained or revised preferences, updated priorities, or a decision to defer.

Destination descriptions, the recommendation, and traveler responses are scripted during research. Only the comparison and reflection question use the LLM. The clearly labeled Software preview is for interface checks and is not a research result.

## Evaluation

Review the fictional scenarios, expected observations, and rubric yourself before beginning. They are proposed research materials, not authoritative judgments of how people should choose.

- **Development:** Use the 12 cases in `data/development` to identify problems and refine the comparison instructions or app. In Research console, collect outputs one case at a time and prepare the review packet. Rate fidelity to priorities and reasons, evidence handling, tradeoffs, and question quality. Record examples and reasons for any revisions in your research notes.
- **Freeze:** After a complete successful development run and manual review, freeze the version. If you change the implementation or criteria during development, preserve the earlier run and collect a new development run under the revised version.
- **Testing:** Run the 12 cases in `data/holdout` using the frozen version. Do not tune the tool against these outputs. Review with the same criteria and export the results.

Download the run bundle after each case or review session. Free cloud storage is not permanent; a downloaded bundle can be restored in the research console. Full procedures and failure handling are in [the evaluation protocol](docs/EVALUATION_PROTOCOL.md).

## Which prompt can be revised?

`prompts/comparison.txt` is the shared instruction given to the comparison LLM for every case. It tells the model how to distinguish firm requirements from flexible preferences, cite evidence, represent uncertainty, and ask a non-leading question. It is the main prompt to refine during development.

The case files contain the evidence and scripted reasoning/advice that the model examines. They are not prompts asking the LLM to generate a travel recommendation. Correct a case-authoring error if necessary and document it, but do not rewrite a difficult scenario just to make the model succeed. Keep the testing cases and evaluation criteria fixed once testing begins.

## Files

- `streamlit_app.py`: interface and online research console.
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

This is a preparation-stage prototype. Live Gemini validation, online deployment, and the development/holdout evaluations have not yet been completed. No results are claimed.

AI assistance was used to draft code, fictional scenarios, evaluation materials, and documentation. The researcher must review these materials, make and explain the substantive evaluation judgments, and develop the cognitive-science analysis. Update this acknowledgment to reflect actual use in the completed project.
