"""Gemini API adapter. Uses the standard library; no credentials in saved artifacts."""
import json
import os
import re
import time
import urllib.error
import urllib.request

from .core import ROOT, digest, now, read_json, require, validate_comparison

ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/models/"


class GenerationError(RuntimeError):
    def __init__(self, message, artifact=None):
        super().__init__(message)
        self.artifact = artifact or {}


def comparison_error_message(exc):
    """Readable failure categories without exposing API responses or credentials."""
    status = getattr(exc, "artifact", {}).get("http_status")
    messages = {
        400: "The comparison request was rejected. The app owner needs to check the model settings and account eligibility.",
        401: "Gemini could not authenticate the request. The app owner needs to check the API key.",
        403: "Gemini denied access. The app owner needs to check the API key permissions and project access.",
        404: "The configured model is unavailable for this request. The app owner needs to update or check the model configuration.",
        429: "Gemini's usage limit has been reached. Please wait for the quota to reset before trying again.",
    }
    return messages.get(status, "The comparison is currently unavailable. Download this decision record to preserve the error details for troubleshooting.")


def settings():
    value = read_json(ROOT / "config/model.json")
    require(set(value) == {"provider", "model", "max_output_tokens", "temperature", "thinking_level", "timeout_seconds"},
            "Unexpected model configuration fields.")
    require(value["provider"] == "gemini", "This adapter supports Gemini only.")
    require(isinstance(value["model"], str) and re.fullmatch(r"[A-Za-z0-9._-]+", value["model"]), "Specify a model identifier, not a URL.")
    require(type(value["max_output_tokens"]) is int and value["max_output_tokens"] > 0, "Invalid token limit.")
    require(type(value["timeout_seconds"]) in (int, float) and 1 <= value["timeout_seconds"] <= 600,
            "Timeout must be 1 to 600 seconds.")
    require(value["temperature"] is None or (type(value["temperature"]) in (int, float)
            and 0 <= value["temperature"] <= 2), "Invalid temperature.")
    require(value["thinking_level"] == "minimal",
            "This low-token setup fixes thinking_level at minimal.")
    return value


def build_request(payload, config=None):
    config = config or settings()
    return {
        "systemInstruction": {"parts": [{"text": (ROOT / "prompts/comparison.txt").read_text(encoding="utf-8")}]},
        "contents": [{"role": "user", "parts": [{"text": json.dumps(payload, ensure_ascii=False)}]}],
        "generationConfig": {
            "maxOutputTokens": config["max_output_tokens"],
            "temperature": config["temperature"],
            "candidateCount": 1,
            "thinkingConfig": {"thinkingLevel": config["thinking_level"]},
            "responseMimeType": "application/json",
            "responseJsonSchema": read_json(ROOT / "schemas/comparison.json")}}


def parse_response(raw, payload):
    if not isinstance(raw, dict):
        raise GenerationError("Response body is not an object.")
    candidates = raw.get("candidates", [])
    if raw.get("promptFeedback", {}).get("blockReason") or not candidates:
        raise GenerationError("No candidate response or prompt blocked; inspect the saved raw response.")
    if not isinstance(candidates, list) or len(candidates) != 1 or not isinstance(candidates[0], dict) or candidates[0].get("finishReason") != "STOP":
        raise GenerationError("Response did not finish normally (for example token cap or safety filter). No automatic retry.")
    texts = [p["text"] for p in candidates[0].get("content", {}).get("parts", [])
             if "text" in p and not p.get("thought")]
    if not texts:
        raise GenerationError("Response contained no output text.")
    try:
        return validate_comparison(json.loads("".join(texts)), payload)
    except (ValueError, TypeError, KeyError) as exc:
        raise GenerationError("Response failed validation: " + str(exc)) from exc


def fixture(payload):
    """A deliberately generic plumbing stub; never an answer key or research result."""
    result = {
        "priorities_interpretation": "OFFLINE FIXTURE. Stated priorities: " + "; ".join(payload["initial"]["priorities"]),
        "reasoning_interpretation": "OFFLINE FIXTURE. Recorded reason: " + payload["initial"]["reasons"],
        "summary": "This is a software demonstration. No language model has analyzed this decision.",
        "findings": [],
        "reflection_question": {"text": "Which part of your recorded reason would you want to check against the destination descriptions?",
                                "source_ids": ["initial.reasons"]},
        "limitations": ["Offline fixture: not an LLM response and not suitable for semantic evaluation."]}
    return validate_comparison(result, payload), {"backend": "fixture", "at": now(), "request_hash": digest(payload)}


def generate(payload, backend="fixture", config=None, api_key=None):
    require(backend in ("fixture", "live"), "Unknown backend.")
    if backend == "fixture":
        return fixture(payload)
    config = config or settings()
    require(not config["model"].startswith("SET_"), "Set a model snapshot in config/model.json before a live run.")
    key = api_key or os.environ.get("GEMINI_API_KEY")
    require(bool(key), "Set GEMINI_API_KEY in your cloud app secrets before a live run.")
    request = build_request(payload, config)
    artifact = {"backend": "live", "started_at": now(), "request": request,
                "request_hash": digest(request), "settings": config, "endpoint": ENDPOINT + config["model"] + ":generateContent"}
    start = time.monotonic()
    try:
        req = urllib.request.Request(artifact["endpoint"], data=json.dumps(request).encode(), method="POST",
                                     headers={"x-goog-api-key": key, "Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=config["timeout_seconds"]) as response:
            artifact["response"] = json.load(response)
        artifact["elapsed_seconds"] = round(time.monotonic() - start, 3)
        output = parse_response(artifact["response"], payload)
        artifact["returned_model"] = artifact["response"].get("modelVersion")
        artifact["usage"] = artifact["response"].get("usageMetadata")
        return output, artifact
    except urllib.error.HTTPError as exc:
        # Avoid storing server error text that could echo request headers or account details.
        artifact["http_status"] = exc.code
        artifact["elapsed_seconds"] = round(time.monotonic() - start, 3)
        raise GenerationError("API HTTP %d. No automatic retry; check access, quota, and settings." % exc.code, artifact) from None
    except GenerationError as exc:
        raise GenerationError(str(exc), artifact) from None
    except (urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
        artifact["elapsed_seconds"] = round(time.monotonic() - start, 3)
        raise GenerationError("Transport or response decoding failed (%s); no automatic retry." % type(exc).__name__, artifact) from None
