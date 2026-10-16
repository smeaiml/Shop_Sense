# Data sources and provenance

This implementation uses the ShopSense data already present under `data/shopsense/`:
- `mock_api/`: synthetic CSV/JSON mock records for customers, products, orders, shipments, refunds, policy tables, and related operations.
- `corpus/markdown/`: 14 generated Markdown policy documents used for retrieval.
- `corpus/pdf/`: corresponding policy PDFs supplied with the dataset.
- `eval/golden_set.json`: 20 frozen evaluation cases.

The starter repository's README identifies the public toolkit project at `https://github.com/AI-Launchpad-Dev/data-toolkit/`. The dataset was already generated before this code update; it was not regenerated as part of the implementation. Keep the manifest and data files unchanged for reproducible evaluation.

The records are synthetic mock data and are not a production order system. The current application reads the CSV mock tables and does not write to them.
