# Financial Tracker

A free, local financial tracker that processes HSBC bank statement PDFs and provides interactive analysis through a web dashboard.

## Features

- **PDF Processing** -- Extracts transactions from HSBC statement PDFs using pdfplumber with penny-perfect balance validation
- **ML Categorization** -- Pure ML-based transaction categorization (no API costs, runs offline)
- **Interactive Dashboard** -- Localhost web dashboard with Plotly charts, recurring payment detection, and vendor analysis
- **Privacy First** -- All data stays on your machine; nothing is sent to external services

## Quick Start

1. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

2. **Place your HSBC statement PDFs** in `data/raw/`

3. **Run the dashboard** (processes PDFs, categorizes, and launches in one step):
   ```bash
   python scripts/run_dashboard.py
   ```
   Then open http://127.0.0.1:8050 in your browser.

## Individual Scripts

You can also run pipeline stages separately:

```bash
python scripts/process_statements.py data/raw data/processed     # Extract transactions from PDFs
python scripts/categorize.py data/processed data/categorized      # ML categorization
python scripts/analyze.py data/categorized                        # Generate analysis report
python scripts/train_ml_model.py                                  # Retrain the ML model
python scripts/create_training_data.py                            # Build training dataset
python scripts/demo_pure_ml.py                                    # Demo the ML categorizer
```

## Project Structure

```
├── data/                    # Git-ignored data folder
│   ├── raw/                 # Original PDF bank statements
│   ├── processed/           # Extracted transaction JSON
│   ├── categorized/         # Categorized transaction JSON
│   └── models/              # Trained ML model (.pkl)
├── src/                     # Core modules
│   ├── parsers/             # PDF parsing (advanced_hsbc_parser.py)
│   ├── dashboard.py         # Dash web dashboard
│   ├── pure_ml_categorizer.py  # ML categorizer
│   ├── config.py            # Configuration with sensible defaults
│   ├── pdf_extractor.py     # PDF text extraction utilities
│   ├── analyzer.py          # Transaction analysis
│   └── user_feedback.py     # User feedback collection
├── scripts/                 # CLI scripts
├── requirements.txt         # Python dependencies
└── .gitignore
```

## Privacy & Security

- All processing happens **locally** on your machine
- No data is sent to external services or APIs
- Bank statements are stored in the **git-ignored `data/` folder**
- No API keys, tokens, or internet connection required

## Requirements

- Python 3.8+
- See `requirements.txt` for package dependencies
