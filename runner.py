"""
Main CLI runner for the financial tracker.
"""

import click
import os
import sys
import logging

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from src.config import config

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@click.group()
def cli():
    """Financial Tracker - Process bank statements and analyze spending patterns."""
    pass


@cli.command()
def setup():
    """Initial setup - create necessary directories."""
    try:
        config.ensure_directories()
        click.echo("✅ Setup complete! Directory structure created.")
        click.echo("\nNext steps:")
        click.echo("1. Place your bank statement PDFs in: data/raw/")
        click.echo("2. Run: python runner.py process")
        click.echo("3. Run: python runner.py categorize")
        click.echo("4. Run: python runner.py dashboard")
    except Exception as e:
        click.echo(f"❌ Setup failed: {e}")
        sys.exit(1)


@cli.command()
@click.option('--input-dir', help='Directory containing PDF files')
@click.option('--output-dir', help='Directory to save processed data')
def process(input_dir, output_dir):
    """Extract transactions from bank statement PDFs."""
    try:
        from scripts.process_statements import main as process_main
        
        if not input_dir:
            input_dir = config.get('data.raw_statements', './data/raw')
        if not output_dir:
            output_dir = config.get('data.processed', './data/processed')
        
        click.echo(f"Processing PDFs from: {input_dir}")
        click.echo(f"Saving results to: {output_dir}")
        
        result = process_main(input_dir, output_dir)
        
        if result:
            click.echo("✅ Processing complete!")
            click.echo("Next step: python runner.py categorize")
        else:
            click.echo("❌ Processing failed or no PDFs found")
            
    except ImportError as e:
        click.echo(f"❌ Missing dependencies: {e}")
        click.echo("Install with: pip install -r requirements.txt")
        sys.exit(1)
    except Exception as e:
        click.echo(f"❌ Processing failed: {e}")
        sys.exit(1)


@cli.command()
@click.option('--input-dir', help='Directory containing processed transaction data')
@click.option('--output-dir', help='Directory to save categorized data')
def categorize(input_dir, output_dir):
    """Categorize processed transactions using rule-based matching."""
    try:
        from scripts.categorize import main as categorize_main
        
        if not input_dir:
            input_dir = config.get('data.processed', './data/processed')
        if not output_dir:
            output_dir = config.get('data.categorized', './data/categorized')
        
        click.echo(f"Categorizing transactions from: {input_dir}")
        click.echo(f"Saving results to: {output_dir}")
        
        result = categorize_main(input_dir, output_dir)
        
        if result:
            click.echo("✅ Categorization complete!")
            click.echo("Next step: python runner.py dashboard")
        else:
            click.echo("❌ Categorization failed or no processed data found")
            
    except Exception as e:
        click.echo(f"❌ Categorization failed: {e}")
        sys.exit(1)


@cli.command()
@click.option('--host', default='127.0.0.1', help='Host to run dashboard on')
@click.option('--port', default=8050, help='Port to run dashboard on')
@click.option('--debug', is_flag=True, help='Run in debug mode')
def dashboard(host, port, debug):
    """Launch the interactive web dashboard."""
    try:
        from src.dashboard import dashboard
        
        if dashboard is None:
            click.echo("❌ Dashboard dependencies not found.")
            click.echo("Install with: pip install dash plotly dash-bootstrap-components")
            sys.exit(1)
        
        click.echo(f"🚀 Starting dashboard at http://{host}:{port}")
        click.echo("Press Ctrl+C to stop")
        
        dashboard.run(host=host, port=port, debug=debug)
        
    except KeyboardInterrupt:
        click.echo("\n👋 Dashboard stopped")
    except ImportError as e:
        click.echo(f"❌ Missing dependencies: {e}")
        click.echo("Install with: pip install -r requirements.txt")
        sys.exit(1)
    except Exception as e:
        click.echo(f"❌ Dashboard failed to start: {e}")
        sys.exit(1)


@cli.command()
@click.option('--input-dir', help='Directory containing categorized data')
def analyze(input_dir):
    """Generate analysis report for categorized transactions."""
    try:
        from scripts.analyze import main as analyze_main
        
        if not input_dir:
            input_dir = config.get('data.categorized', './data/categorized')
        
        click.echo(f"Analyzing data from: {input_dir}")
        
        result = analyze_main(input_dir)
        
        if result:
            click.echo("✅ Analysis complete!")
        else:
            click.echo("❌ Analysis failed or no categorized data found")
            
    except Exception as e:
        click.echo(f"❌ Analysis failed: {e}")
        sys.exit(1)


@cli.command()
def status():
    """Show current status of data processing pipeline."""
    data_paths = config.get_data_paths()
    
    click.echo("📊 Financial Tracker Status\n")
    
    # Check each stage
    raw_path = data_paths.get('raw_statements', './data/raw')
    processed_path = data_paths.get('processed', './data/processed')
    categorized_path = data_paths.get('categorized', './data/categorized')
    
    # Count files in each directory
    def count_files(path, extension):
        try:
            if os.path.exists(path):
                files = [f for f in os.listdir(path) if f.endswith(extension)]
                return len(files)
            return 0
        except:
            return 0
    
    pdf_count = count_files(raw_path, '.pdf')
    processed_count = count_files(processed_path, '.json')
    categorized_count = count_files(categorized_path, '.json')
    
    click.echo(f"1. Raw PDFs: {pdf_count} files in {raw_path}")
    click.echo(f"2. Processed: {processed_count} files in {processed_path}")
    click.echo(f"3. Categorized: {categorized_count} files in {categorized_path}")
    
    click.echo("\n📋 Next Steps:")
    if pdf_count == 0:
        click.echo("• Add PDF bank statements to data/raw/")
    elif processed_count == 0:
        click.echo("• Run: python runner.py process")
    elif categorized_count == 0:
        click.echo("• Run: python runner.py categorize") 
    else:
        click.echo("• Run: python runner.py dashboard")


if __name__ == '__main__':
    cli()