# Liquid Mapper

Liquid Mapper is a Streamlit application that helps generate FHIR mapping table documentation and Liquid templates for transforming source data into FHIR resources.

**Primary flows**

- Step 0: Generate Mapping Table Documentation — Generate comprehensive mapping table documentation from source JSON. Optionally include reference mappings and a Liquid template.
- Step 1: Generate Liquid Template — Generate Liquid templates from existing mapping table documentation.

## Project Structure

- `streamlit_app.py` — Main Streamlit UI and orchestration layer.
- `ioc/` — Inversion of Control (IoC) container wiring (dependency-injector) and configuration helpers.
- `services/` — Core services used by the app:
  - `mapping_search_service.py` — Search and retrieve mapping tables.
  - `context_db_service.py` — Lightweight JSON-backed context store for resource-level context.
  - `file_storage_service.py` — Save generated mapping tables and templates safely.
  - `prompt_builder_service.py` — Build prompts from templates or inline fallbacks for LLM generation.
- `prompts/` — Markdown templates used to build prompts for the LLM.
- `Dataset/` — Local example dataset area where mapping tables, liquid templates, and context are stored.

## Features

- Integrates with Azure OpenAI via `fx_ai_reusables` LLM creators and HCP authentication for secure API access.
- IoC container centralizes configuration and provides named loggers for components.
- Services validate inputs and provide helpful error messages surfaced in the Streamlit UI.
- Safe file handling with path validation and filename sanitization.
- Simple JSON-backed context DB with corruption recovery.

## Requirements

The app uses a Python virtual environment and a requirements file in the repository root. Example:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Environment

Set environment variables in a `.env` file or export them directly. Important variables include:

- `AZURE_OPENAI_ENDPOINT`
- `AZURE_OPENAI_DEPLOYMENT_NAME`
- `HCP_TOKEN_URL`, `HCP_CLIENT_ID`, `HCP_CLIENT_SECRET`

## Running Locally

Run the app from the repository root so local packages are importable:

```bash
cd /path/to/flex-ai-sandbox/flex-ai-sandbox
source .venv/bin/activate
streamlit run use_cases/Liquid_Mapper/streamlit_app.py --server.port 8503
```

## Configuration

- IoC config lives in `ioc/liquid_mapper_ioc_config.py` and provides path helpers for `Dataset/MappingTable` and `Dataset/LiquidMapping`.
- `prompts/` contains Markdown prompt templates. If a template is missing the service will use an inline fallback prompt.

## Troubleshooting

- Module import errors: ensure you run Streamlit from the workspace root so `fx_ai_reusables` is available on `sys.path`.
- Streamlit duplicate widget errors: ensure `main()` is executed once and widgets use explicit `key` values where needed.
- Corrupted `Dataset/ResourceContext/context.json`: the context DB will attempt to recover automatically; if recovery fails, delete the file and restart.

## Development Notes

- Add unit tests for each service to validate input validation and error paths.
- Consider migrating the context DB to SQLite for concurrent access and transaction safety.
- For production deployment, ensure secrets are provided via volume mounts or a secrets manager and the `K8DEPLOYED` config is used.

## License

This repository uses the existing project license in the repository root.
