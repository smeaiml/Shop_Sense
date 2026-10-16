# ShopSense — VS Code local demo

This ZIP contains the ShopSense web app, FastAPI backend, mock ShopSense data, policy documents, and tests. It runs locally without a Replit account or an API key. All order and refund actions use demo data.

## Requirements

- VS Code
- Node.js 22 LTS or newer
- Python 3.11 or newer
- pnpm 10 (enable with `corepack enable` after installing Node.js)
- Internet access for the first install and the first local embedding-model download

## Set up

1. Extract the ZIP and open the `shopsense-vscode` folder in VS Code.
2. Open the Command Palette (`Ctrl+Shift+P` / `Cmd+Shift+P`), choose **Tasks: Run Task**, then run **ShopSense: Setup**. This installs the JavaScript and Python dependencies and creates a local `.venv`.
3. If `pnpm` is not recognized, run `corepack enable` in a terminal and run **ShopSense: Setup** again.

## Run

Choose **ShopSense: Run Local Demo** from **Tasks: Run Task**. When both services start, open:

**http://localhost:21957/shopsense/**

Stop the demo with `Ctrl+C` in the task terminal.

The demo uses deterministic rules by default, so no `OPENAI_API_KEY` is needed. The backend stores its local SQLite data and generated index under `artifacts/shopsense/backend/runtime/`.

## Tests and evaluation

From the VS Code terminal:

```bash
pnpm --filter @workspace/shopsense run typecheck
```

Run the Python tests from the backend folder:

```bash
cd artifacts/shopsense/backend
python -m pytest -q
```

Run the 20-ticket evaluation from the same folder:

```bash
python scripts/run_evaluation.py
```

The evaluation report is written to `runtime/evaluation/latest.json`.

## Troubleshooting

- If port `21957` or `8001` is already in use, stop the other process or set `SHOPSENSE_WEB_PORT` / `SHOPSENSE_API_PORT` before launching the task.
- On Windows, if Python is not found, install Python 3.11+ and add it to `PATH`, then rerun setup.
- The first policy search can take longer while the embedding model downloads.
