<!-- GitHub Copilot / AI agent instructions for the `chatbot` repo -->
# Guidance for AI coding agents

This repository contains a Streamlit demo app. The app implements an "AI Clinical Pathway Agent"
that uses an LLM client plus several helper functions and UI tabs. By default you can keep
using the `openai` package and an OpenAI API key; alternative providers (Gemini) have also
been used historically — see notes below when switching providers.

**Big picture (current app)**
- **Single Streamlit app:** `streamlit_app.py` — a multi-tab app that guides users through
  scope, evidence appraisal (PubMed), logic & visuals (Mermaid), testing, and a final report.
- **Runtime & APIs:** Runs under Streamlit and calls external APIs:
  - OpenAI via the `openai` package (typical model: `gpt-3.5-turbo`).
  - NCBI E-utilities (PubMed) via HTTP (`urllib.request`) for evidence search and summary.
- **State & data flow:** The app stores a single `st.session_state.pathway_data` dict with keys:
  `scope`, `evidence` (list of {point,citation,verification}), `logic`, `testing`, `operations`, and `mermaid`.
  User inputs in each tab update `pathway_data`; AI calls generate charters, verifications, and Mermaid code.

**Key files & locations**
- `streamlit_app.py` — main app; inspect for tab logic, `search_pubmed`, `ai_verify_evidence`, and `ai_generate_mermaid`.
- `requirements.txt` — ensure it includes `openai` (or `google-generative-ai` if you explicitly switch providers). The current repo lists `streamlit` and `openai`.
- `README.md` — run instructions (keep in sync when dependencies change).
- `.streamlit/secrets.toml` — recommended place for `OPENAI_API_KEY` (the app falls back to a sidebar input).

**Concrete patterns to preserve or follow when editing**
- Session state shape: `st.session_state.pathway_data` is the single source of truth. When renaming keys, update all tabs that read/write them.
- Evidence bank: code relies on entries of the form `{"point":"...","citation":"...","verification":"..."}` — preserve this when adding exports or persistence.
- PubMed helper: `search_pubmed(query, retmax=3)` uses NCBI E-utilities (`esearch.fcgi` + `esummary.fcgi`) via `urllib.request` and expects JSON responses.
- LLM usage (OpenAI): the app commonly constructs a client with `OpenAI(api_key=...)` and calls `client.chat.completions.create(...)` (streaming or non-streaming). If you keep OpenAI, expect responses to be available on the returned object (the demo uses streaming via `stream=True`). Handle API failures gracefully (current app catches exceptions and returns fallback strings).
- Provider note: if switching to another provider (e.g., Gemini), update the call sites and response handling — different SDKs return different shapes (e.g., `response.text` for Gemini vs `choices` for OpenAI).
- Mermaid rendering: `mermaid` code is stored in `pathway_data['mermaid']` and rendered via `streamlit.components.v1.components.html` loading Mermaid from CDN. Keep the mermaid string raw (no markdown ticks) when storing.

**Developer workflow / commands**
- Install deps (verify `requirements.txt` first):
	```bash
	pip install -r requirements.txt
	```
- Run locally:
	```bash
	streamlit run streamlit_app.py
	```
-- Secrets: add `OPENAI_API_KEY` to `./.streamlit/secrets.toml` (key name in the app may vary) or use the sidebar input when running locally. The app currently looks for an API key in session or a sidebar input; prefer `./.streamlit/secrets.toml` for CI and local runs.

**Provider differences & compatibility note**
- The repo historically used the `openai` package. If you keep `openai`:
	- Client pattern: `from openai import OpenAI` then `client = OpenAI(api_key=...)`.
	- Chat calls: `client.chat.completions.create(model="gpt-3.5-turbo", messages=..., stream=True)` and streaming helpers are available on the response.
	- Secrets: use `OPENAI_API_KEY` in `./.streamlit/secrets.toml` or pass via UI input.
- If you switch to Google Gemini (`google.generativeai`) be aware the SDK uses `model.generate_content(prompt)` and returns `response.text`. Update code and tests accordingly.

**Integration points & external dependencies**
- OpenAI API (network access + API key).
- NCBI E-utilities (PubMed) HTTP endpoints — be mindful of rate limits and add retries if making many requests.
- Mermaid is embedded via CDN (`https://cdn.jsdelivr.net/npm/mermaid...`) — no local npm dependency required.

**When you edit or extend**
- If you change the session shape (`pathway_data`) update every place that reads/writes those keys (tabs 1–5 and report generation).
- If you switch LLM providers, update the code that builds prompts and adapts to the provider's response shape (`.text`, `choices`, etc.).
- If you add tests or CI, document how to set `OPENAI_API_KEY` for CI (use secrets management) and restrict test calls to mocked responses.

**Examples / quick references**
- PubMed query construction (example): `query = f"({condition}) AND ({node_input}) AND (Guideline[pt] OR Systematic Review[pt])"`
- Evidence entry shape: `{"point": node_input, "citation": top_cite, "verification": verification}`
- Mermaid storage: `st.session_state.pathway_data['mermaid'] = code` (code must be raw `graph TD; ...`)

If anything here is incomplete or you'd like a short migration example (e.g., migrate Gemini calls to OpenAI or switch streaming/non-streaming behavior), tell me which example you want and I will add it.
