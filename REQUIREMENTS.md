# Runtime Requirements (Orchestrator — ADK v3)

This project uses the Google AI Python SDK for direct Gemini calls via `from google import genai`.

Required packages (minimal):
- google-genai >= 1.0.0

Install:
```bash
pip install "google-genai>=1.0.0"
```

Notes:
- The orchestrator dynamically selects providers. Gemini requires a valid `GEMINI_API_KEY` (aliases supported: `GOOGLE_GEMINI_API_KEY`, `GOOGLE_GEMINI_KEY`, `GENAI_API_KEY`, `GEMINI_KEY`).
- `.env` is loaded from the workspace root with priority.


