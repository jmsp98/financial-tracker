# Financial Tracker

A free, local financial tracker that processes bank statement PDFs and provides interactive analysis through a web dashboard.

## Features

- 📄 **PDF Processing**: Extract transactions from bank statement PDFs
- 🏷️ **Smart Categorization**: Rule-based categorization (100% free, no API costs)
- 📊 **Interactive Dashboard**: Localhost web dashboard with Plotly charts
- 📈 **Analysis**: Monthly summaries, yearly trends, custom period analysis
- 🔧 **Configurable**: Easy YAML configuration for categories and keywords
- 🔒 **Private**: All data stays on your machine

## Quick Start

1. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

2. **Place your bank statement PDFs** in the `data/raw/` folder

3. **Process statements**:
   ```bash
   python runner.py process
   ```

4. **Categorize transactions**:
   ```bash
   python runner.py categorize
   ```

5. **Launch dashboard**:
   ```bash
   python runner.py dashboard
   ```
   Then open http://127.0.0.1:8050 in your browser

## Configuration

Edit `config.yaml` to:
- Add custom expense categories
- Define keyword patterns for categorization
- Adjust dashboard settings

## Project Structure

```
├── data/                    # Git-ignored data folder
│   ├── raw/                # Original PDF bank statements
│   ├── processed/          # Extracted transaction data
│   └── categorized/        # Categorized transactions
├── src/                    # Core modules
├── scripts/               # Processing scripts
├── config.yaml           # Configuration file
└── runner.py             # Main CLI interface
```

## Categorization

This tool uses **rule-based categorization** which is:
- ✅ Completely free (no API costs)
- ✅ Fast and reliable
- ✅ Easy to customize
- ✅ Works offline

Categories are matched using keyword patterns defined in `config.yaml`. You can easily add new categories or modify existing ones.

## Privacy & Security

- All processing happens locally on your machine
- No data is sent to external services
- Bank statements should be placed in the git-ignored `data/` folder
- No API keys or tokens required

## Commands

```bash
python runner.py process      # Extract transactions from PDFs
python runner.py categorize   # Categorize transactions  
python runner.py dashboard    # Launch web dashboard
python runner.py setup       # Initial setup (creates folders)
```

## Requirements

- Python 3.8+
- See `requirements.txt` for package dependencies

## Support

This is a personal finance tool designed to be free and private. All processing happens locally with no external dependencies or costs.