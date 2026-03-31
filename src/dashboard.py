"""
Interactive Dash dashboard for financial data visualization.
"""

try:
    import dash
    from dash import dcc, html, Input, Output, callback, State, clientside_callback, ALL, MATCH
    import dash_bootstrap_components as dbc
    import plotly.express as px
    import plotly.graph_objects as go
    HAS_DASH = True
except ImportError:
    HAS_DASH = False

import json
import os
from datetime import datetime, timedelta
from typing import List, Dict, Any
import logging

from .analyzer import analyzer
from .config import config

logger = logging.getLogger(__name__)


class FinancialDashboard:
    """Interactive dashboard for financial data analysis."""
    
    def __init__(self, force_reprocess: bool = False):
        if not HAS_DASH:
            raise ImportError("Dash dependencies not found. Install with: pip install dash plotly dash-bootstrap-components")
        
        self.force_reprocess = force_reprocess
        self.app = dash.Dash(
            __name__,
            external_stylesheets=[dbc.themes.BOOTSTRAP],
            suppress_callback_exceptions=True
        )
        
        self.categorized_data = []
        self.currency_symbol = '£'  # Default currency symbol
        self.currency_code = 'GBP'  # Default currency code
        self.load_data()
        self.setup_layout()
        self.setup_callbacks()
    
    def _get_cache_meta_path(self):
        """Return the path to the cache metadata file."""
        categorized_path = config.get('data.categorized', './data/categorized')
        return os.path.join(categorized_path, '.cache_meta.json')
    
    def _get_cached_pdf_set(self):
        """Read the set of PDF filenames from cache metadata. Returns None if no cache."""
        meta_path = self._get_cache_meta_path()
        if not os.path.exists(meta_path):
            return None
        try:
            with open(meta_path, 'r') as f:
                meta = json.load(f)
            return set(meta.get('source_pdfs', []))
        except Exception:
            return None
    
    def _write_cache_meta(self, pdf_filenames):
        """Write cache metadata after successful processing."""
        meta_path = self._get_cache_meta_path()
        os.makedirs(os.path.dirname(meta_path), exist_ok=True)
        with open(meta_path, 'w') as f:
            json.dump({'source_pdfs': sorted(pdf_filenames)}, f, indent=2)
    
    def auto_process_bank_statements(self):
        """Automatically process any new bank statements in data/raw/"""
        try:
            raw_path = config.get('data.raw', './data/raw')
            processed_path = config.get('data.processed', './data/processed')
            categorized_path = config.get('data.categorized', './data/categorized')
            
            # Check if there are PDF files in raw directory
            pdf_files = [f for f in os.listdir(raw_path) if f.lower().endswith('.pdf')]
            
            if not pdf_files:
                logger.info("No PDF bank statements found in data/raw/")
                return False
            
            # --- Cache check ---
            if not self.force_reprocess:
                cached_file = os.path.join(categorized_path, 'all_categorized_transactions.json')
                cached_pdfs = self._get_cached_pdf_set()
                current_pdfs = set(pdf_files)
                
                if cached_pdfs is not None and os.path.exists(cached_file):
                    new_pdfs = current_pdfs - cached_pdfs
                    if not new_pdfs:
                        # Cache is up to date — skip processing
                        # Count transactions from the cached file for the message
                        try:
                            with open(cached_file, 'r') as f:
                                cached_data = json.load(f)
                            if isinstance(cached_data, list):
                                txn_count = len(cached_data)
                            elif isinstance(cached_data, dict) and 'transactions' in cached_data:
                                txn_count = len(cached_data['transactions'])
                            else:
                                txn_count = '?'
                        except Exception:
                            txn_count = '?'
                        
                        print(f"\n📄 Using cached data ({txn_count} transactions from {len(current_pdfs)} PDFs).")
                        print(f"   Use --reprocess to re-extract from PDFs.\n")
                        return True
                    else:
                        print(f"\n📄 New PDF(s) detected: {', '.join(sorted(new_pdfs))}. Re-processing all statements...")
            else:
                print(f"\n📄 --reprocess flag set. Re-processing all statements...")
            
            logger.info(f"Found {len(pdf_files)} PDF bank statements. Auto-processing...")
            
            # Import processing modules
            from .pdf_extractor import PDFExtractor
            from .parsers.parser_factory import ParserFactory
            from .pure_ml_categorizer import PureMLCategorizer
            
            # Create directories
            os.makedirs(processed_path, exist_ok=True)
            os.makedirs(categorized_path, exist_ok=True)
            
            # Step 1: Extract and parse transactions from PDFs
            parser_factory = ParserFactory()
            all_transactions = []
            failed_pdfs = []
            
            print(f"\n📄 Processing {len(pdf_files)} PDF statements...")
            
            for pdf_file in sorted(pdf_files):
                pdf_path = os.path.join(raw_path, pdf_file)
                
                try:
                    # Get appropriate parser first
                    extractor = PDFExtractor()
                    text = extractor.extract_text(pdf_path)
                    parser = parser_factory.create_parser(text)
                    
                    if parser:
                        # Check if parser has direct PDF parsing method
                        if hasattr(parser, 'parse_transactions_from_pdf'):
                            transactions = parser.parse_transactions_from_pdf(pdf_path)
                        else:
                            tables = extractor.extract_tables(pdf_path)
                            transactions = parser.parse_transactions(text, tables)
                        
                        if len(transactions) == 0:
                            print(f"  ⚠️  {pdf_file}: 0 transactions (parser: {type(parser).__name__}) - SKIPPED")
                            failed_pdfs.append(pdf_file)
                        else:
                            print(f"  ✅  {pdf_file}: {len(transactions)} transactions")
                            all_transactions.extend(transactions)
                        
                        logger.info(f"Extracted {len(transactions)} transactions from {pdf_file}")
                    else:
                        print(f"  ❌  {pdf_file}: no suitable parser found")
                        failed_pdfs.append(pdf_file)
                        logger.warning(f"No suitable parser found for {pdf_file}")
                        
                except Exception as e:
                    print(f"  ❌  {pdf_file}: error - {e}")
                    failed_pdfs.append(pdf_file)
                    logger.error(f"Error processing {pdf_file}: {e}")
                    continue
            
            # Summary
            success_count = len(pdf_files) - len(failed_pdfs)
            print(f"\n📊 Processed {success_count}/{len(pdf_files)} PDFs: {len(all_transactions)} total transactions")
            if failed_pdfs:
                print(f"⚠️  Failed: {', '.join(failed_pdfs)}")
            
            if not all_transactions:
                logger.warning("No transactions extracted from PDF files")
                return False
            
            # Step 2: Save processed transactions
            processed_data = []
            for txn in all_transactions:
                processed_data.append({
                    'date': txn.date.isoformat(),
                    'description': txn.description,
                    'amount': txn.amount,
                    'balance': txn.balance,
                    'transaction_type': txn.transaction_type,
                    'payment_method': txn.payment_method,
                    'merchant': txn.merchant,
                    'location': txn.location,
                    'raw_description': txn.raw_description,
                    'reference': txn.reference
                })
            
            processed_file = os.path.join(processed_path, 'all_transactions.json')
            with open(processed_file, 'w') as f:
                json.dump(processed_data, f, indent=2, default=str)
            
            logger.info(f"Saved {len(processed_data)} processed transactions")
            
            # Step 3: Categorize transactions using Pure ML
            categorizer = PureMLCategorizer()
            categorized_transactions = categorizer.categorize_transactions(all_transactions)
            
            # Step 4: Save categorized transactions
            categorized_file = os.path.join(categorized_path, 'all_categorized_transactions.json')
            with open(categorized_file, 'w') as f:
                json.dump(categorized_transactions, f, indent=2, default=str)
            
            logger.info(f"Auto-processing complete! Categorized {len(categorized_transactions)} transactions")
            
            # Step 5: Write cache metadata so next startup can skip re-processing
            self._write_cache_meta(pdf_files)
            
            # Count ML vs unknown predictions
            ml_predictions = sum(1 for t in categorized_transactions if t.get('category') != 'unknown')
            unknown_predictions = len(categorized_transactions) - ml_predictions
            logger.info(f"ML categorized: {ml_predictions}, Unknown: {unknown_predictions}")
            
            if not categorizer.is_trained:
                logger.info("💡 Train the ML model for better categorization: python scripts/train_ml_model.py")
            
            return True
            
        except Exception as e:
            logger.error(f"Auto-processing failed: {e}")
            return False

    def load_data(self):
        """Load categorized transaction data and detect currency. Auto-process if needed."""
        categorized_path = config.get('data.categorized', './data/categorized')
        
        # First, try auto-processing any new bank statements
        processing_success = self.auto_process_bank_statements()
        
        if not processing_success:
            print("⚠️  Auto-processing extracted 0 transactions from raw PDFs")
            # Check if stale cached data exists
            target_file = os.path.join(categorized_path, 'all_categorized_transactions.json')
            if os.path.exists(target_file):
                mod_time = datetime.fromtimestamp(os.path.getmtime(target_file))
                print(f"   Loading previously cached data from {mod_time.strftime('%Y-%m-%d %H:%M')} (may be outdated)")
            else:
                print("   No cached data available either. Dashboard will be empty.")
        
        # Look for the most recent categorized data file
        try:
            files = [f for f in os.listdir(categorized_path) if f.endswith('.json')]
            if files:
                # Try to find the combined file first
                if 'all_categorized_transactions.json' in files:
                    file_path = os.path.join(categorized_path, 'all_categorized_transactions.json')
                else:
                    latest_file = max(files, key=lambda f: os.path.getctime(os.path.join(categorized_path, f)))
                    file_path = os.path.join(categorized_path, latest_file)
                
                with open(file_path, 'r') as f:
                    data = json.load(f)
                
                # Handle both old format (list of transactions) and new format (dict with metadata)
                if isinstance(data, dict) and 'transactions' in data:
                    # New format with currency information
                    transactions = data['transactions']
                    if 'currency' in data:
                        currency_info = data['currency']
                        self.currency_symbol = currency_info.get('symbol', '£')
                        self.currency_code = currency_info.get('iso_code', 'GBP')
                        logger.info(f"Loaded currency: {self.currency_symbol} ({self.currency_code})")
                else:
                    # Old format - just list of transactions
                    transactions = data
                    # Check if transactions have currency fields
                    if transactions and isinstance(transactions[0], dict):
                        if 'currency_symbol' in transactions[0]:
                            self.currency_symbol = transactions[0]['currency_symbol']
                        if 'currency_code' in transactions[0]:
                            self.currency_code = transactions[0]['currency_code']
                
                # Convert date strings back to datetime objects
                for transaction in transactions:
                    if isinstance(transaction, dict) and 'date' in transaction:
                        transaction['date'] = datetime.fromisoformat(transaction['date'])
                
                self.categorized_data = transactions
                logger.info(f"Loaded {len(self.categorized_data)} transactions from {os.path.basename(file_path)}")
                logger.info(f"Using currency: {self.currency_symbol} ({self.currency_code})")
            else:
                logger.warning("No categorized data files found. Run processing and categorization first.")
                
        except Exception as e:
            logger.error(f"Error loading data: {e}")
            import traceback
            traceback.print_exc()
    
    def setup_layout(self):
        """Setup the dashboard layout."""
        self.app.layout = dbc.Container([
            dbc.NavbarSimple(
                brand="💰 Financial Tracker",
                brand_href="#",
                color="primary",
                dark=True,
                className="mb-4"
            ),
            
            # Enhanced Balance Flow Summary cards
            dbc.Row([
                dbc.Col([
                    dbc.Card([
                        dbc.CardBody([
                            html.H6("Starting Balance", className="card-title"),
                            html.H3(id="starting-balance", className="text-info")
                        ])
                    ])
                ], width=2),
                dbc.Col([
                    dbc.Card([
                        dbc.CardBody([
                            html.H6("Total Income", className="card-title"),
                            html.H3(id="total-income", className="text-success")
                        ])
                    ])
                ], width=2),
                dbc.Col([
                    dbc.Card([
                        dbc.CardBody([
                            html.H6("Total Expenses", className="card-title"),
                            html.H3(id="total-expenses", className="text-danger")
                        ])
                    ])
                ], width=2),
                dbc.Col([
                    dbc.Card([
                        dbc.CardBody([
                            html.H6("Net Flow", className="card-title"),
                            html.H3(id="net-income")
                        ])
                    ])
                ], width=2),
                dbc.Col([
                    dbc.Card([
                        dbc.CardBody([
                            html.H6("Ending Balance", className="card-title"),
                            html.H3(id="ending-balance", className="text-info")
                        ])
                    ])
                ], width=2),
                dbc.Col([
                    dbc.Card([
                        dbc.CardBody([
                            html.H6("Transactions", className="card-title"),
                            html.H3(id="total-transactions")
                        ])
                    ])
                ], width=2),
            ], className="mb-4"),
            
            # Date range selector
            dbc.Row([
                dbc.Col([
                    dbc.Card([
                        dbc.CardBody([
                            html.H5("Date Range"),
                            dcc.DatePickerRange(
                                id='date-range-picker',
                                start_date=datetime.now() - timedelta(days=365),
                                end_date=datetime.now(),
                                display_format='YYYY-MM-DD'
                            )
                        ])
                    ])
                ], width=12)
            ], className="mb-4"),
            
            # Tabs for different views
            dbc.Tabs([
                dbc.Tab(label="📊 Analytics", tab_id="analytics"),
                dbc.Tab(label="📂 Categories", tab_id="categories"),
                dbc.Tab(label="🔄 Recurring & Vendors", tab_id="recurring-vendors"),
                dbc.Tab(label="🔍 Review 'Other'", tab_id="review-other"),
                dbc.Tab(label="📋 All Transactions", tab_id="all-transactions"),
            ], id="main-tabs", active_tab="analytics"),
            
            html.Div(id="tab-content", className="mt-4")
            
        ], fluid=True)
    
    def setup_callbacks(self):
        """Setup dashboard callbacks."""
        
        # Callback for updating enhanced balance flow summary cards
        @self.app.callback(
            [Output('starting-balance', 'children'),
             Output('total-income', 'children'),
             Output('total-expenses', 'children'), 
             Output('net-income', 'children'),
             Output('ending-balance', 'children'),
             Output('total-transactions', 'children')],
            [Input('date-range-picker', 'start_date'),
             Input('date-range-picker', 'end_date')]
        )
        def update_summary_cards(start_date, end_date):
            # Filter data by date range
            if start_date:
                start_date = datetime.fromisoformat(start_date)
            if end_date:
                end_date = datetime.fromisoformat(end_date)
            
            filtered_data = analyzer.filter_transactions_by_date_range(
                self.categorized_data, start_date, end_date
            )
            
            if not filtered_data:
                return (
                    f"{self.currency_symbol}0.00",
                    f"{self.currency_symbol}0.00", 
                    f"{self.currency_symbol}0.00",
                    f"{self.currency_symbol}0.00",
                    f"{self.currency_symbol}0.00",
                    "0",
                    "No transactions in selected date range"
                )
            
            # Sort transactions by date to get chronological order
            sorted_data = sorted(filtered_data, key=lambda x: x['date'])
            
            # Find transactions with actual balance data (not None and not 0.0)
            balance_transactions = [t for t in sorted_data 
                                  if t.get('balance') is not None and t.get('balance') != 0.0]
            
            if not balance_transactions:
                # No balance data available, just show totals from all transactions
                total_income = sum(t['amount'] for t in filtered_data if t['amount'] > 0)
                total_expenses = sum(abs(t['amount']) for t in filtered_data if t['amount'] < 0)
                net_flow = total_income - total_expenses
                
                return (
                    "N/A",
                    f"{self.currency_symbol}{total_income:,.2f}", 
                    f"{self.currency_symbol}{total_expenses:,.2f}",
                    html.Span(f"{self.currency_symbol}{net_flow:,.2f}", 
                             className="text-success" if net_flow >= 0 else "text-danger"),
                    "N/A",
                    f"{len(filtered_data):,}",
                    dbc.Alert("⚠️ No balance information available in transactions", color="warning", className="mb-0")
                )
            
            # Get starting and ending balances from available balance data
            first_balance_txn = balance_transactions[0]
            last_balance_txn = balance_transactions[-1]
            
            # Calculate the true opening balance: the balance field is an end-of-day
            # value, so we must subtract ALL transactions up to and including that
            # transaction, not just its own amount.
            idx = sorted_data.index(first_balance_txn)
            cumulative = sum(t['amount'] for t in sorted_data[:idx + 1])
            opening_balance = first_balance_txn['balance'] - cumulative
            
            starting_balance = opening_balance
            ending_balance = last_balance_txn['balance']
            
            # Calculate total income and expenses from ALL transactions
            total_income = sum(t['amount'] for t in filtered_data if t['amount'] > 0)
            total_expenses = sum(abs(t['amount']) for t in filtered_data if t['amount'] < 0)
            net_flow = total_income - total_expenses
            
            # Format values
            starting_str = f"{self.currency_symbol}{starting_balance:,.2f}"
            income_str = f"{self.currency_symbol}{total_income:,.2f}"
            expenses_str = f"{self.currency_symbol}{total_expenses:,.2f}"
            net_str = f"{self.currency_symbol}{net_flow:,.2f}"
            ending_str = f"{self.currency_symbol}{ending_balance:,.2f}"
            net_color = "text-success" if net_flow >= 0 else "text-danger"
            
            return (
                starting_str,
                income_str,
                expenses_str, 
                html.Span(net_str, className=net_color),
                ending_str,
                f"{len(filtered_data):,}"
            )
        
        # Callback for tab content
        @self.app.callback(
            Output('tab-content', 'children'),
            [Input('main-tabs', 'active_tab'),
             Input('date-range-picker', 'start_date'),
             Input('date-range-picker', 'end_date')]
        )
        def update_tab_content(active_tab, start_date, end_date):
            # Filter data by date range
            if start_date:
                start_date = datetime.fromisoformat(start_date)
            if end_date:
                end_date = datetime.fromisoformat(end_date)
            
            filtered_data = analyzer.filter_transactions_by_date_range(
                self.categorized_data, start_date, end_date
            )
            
            if active_tab == "analytics":
                return self.create_analytics_tab(filtered_data)
            elif active_tab == "categories":
                return self.create_categories_tab(filtered_data)
            elif active_tab == "recurring-vendors":
                return self.create_recurring_vendors_tab(filtered_data)
            elif active_tab == "review-other":
                return self.create_review_other_tab(filtered_data)
            elif active_tab == "all-transactions":
                return self.create_all_transactions_tab(filtered_data)
            
            return html.Div("Select a tab")
        
        # Waterfall aggregation callback
        @self.app.callback(
            [Output('daily-waterfall-chart', 'figure'),
             Output('waterfall-daily-btn', 'color'),
             Output('waterfall-weekly-btn', 'color'),
             Output('waterfall-monthly-btn', 'color')],
            [Input('waterfall-daily-btn', 'n_clicks'),
             Input('waterfall-weekly-btn', 'n_clicks'),
             Input('waterfall-monthly-btn', 'n_clicks'),
             Input('date-range-picker', 'start_date'),
             Input('date-range-picker', 'end_date')],
            [State('daily-waterfall-chart', 'figure')],
            prevent_initial_call=False
        )
        def update_waterfall_aggregation(daily_clicks, weekly_clicks, monthly_clicks, start_date, end_date, current_fig):
            """Handle waterfall aggregation button clicks and date range changes."""
            ctx = dash.callback_context
            
            # Filter data by date range
            if start_date:
                start_date = datetime.fromisoformat(start_date)
            if end_date:
                end_date = datetime.fromisoformat(end_date)
            
            filtered_data = analyzer.filter_transactions_by_date_range(
                self.categorized_data, start_date, end_date
            )
            
            # Determine which aggregation to use
            aggregation = 'daily'  # default
            if ctx.triggered:
                button_id = ctx.triggered[0]['prop_id'].split('.')[0]
                if button_id == 'waterfall-weekly-btn':
                    aggregation = 'weekly'
                elif button_id == 'waterfall-monthly-btn':
                    aggregation = 'monthly'
                elif button_id == 'waterfall-daily-btn':
                    aggregation = 'daily'
            
            # Create the waterfall chart with the selected aggregation
            waterfall_fig = self.create_waterfall_chart_with_aggregation(filtered_data, aggregation)
            
            # Update button colors for active state
            daily_color = "primary" if aggregation == 'daily' else "outline-primary"
            weekly_color = "primary" if aggregation == 'weekly' else "outline-primary"
            monthly_color = "primary" if aggregation == 'monthly' else "outline-primary"
            
            return waterfall_fig, daily_color, weekly_color, monthly_color
        
        # Income & Expenses aggregation callback
        @self.app.callback(
            [Output('income-expenses-chart', 'figure'),
             Output('income-exp-weekly-btn', 'color'),
             Output('income-exp-monthly-btn', 'color')],
            [Input('income-exp-weekly-btn', 'n_clicks'),
             Input('income-exp-monthly-btn', 'n_clicks'),
             Input('date-range-picker', 'start_date'),
             Input('date-range-picker', 'end_date')],
            prevent_initial_call=False
        )
        def update_income_expenses_chart(weekly_clicks, monthly_clicks, start_date, end_date):
            """Handle income/expenses aggregation toggle and date range changes."""
            ctx = dash.callback_context
            
            if start_date:
                start_date = datetime.fromisoformat(start_date)
            if end_date:
                end_date = datetime.fromisoformat(end_date)
            
            filtered_data = analyzer.filter_transactions_by_date_range(
                self.categorized_data, start_date, end_date
            )
            
            # Determine aggregation — default to monthly
            aggregation = 'monthly'
            if ctx.triggered:
                button_id = ctx.triggered[0]['prop_id'].split('.')[0]
                if button_id == 'income-exp-weekly-btn':
                    aggregation = 'weekly'
            
            fig = self.create_income_expenses_chart(filtered_data, aggregation)
            
            weekly_color = "primary" if aggregation == 'weekly' else "outline-primary"
            monthly_color = "primary" if aggregation == 'monthly' else "outline-primary"
            
            return fig, weekly_color, monthly_color
        
        # Callbacks for Review Other tab hierarchical categorization
        # We'll add these dynamically since we don't know how many transactions there will be
        self.setup_review_callbacks()
    
    def setup_review_callbacks(self):
        """Setup callbacks for the enhanced Review Other functionality."""
        
        # Pattern-matching callback for dropdown dependencies  
        @self.app.callback(
            Output({'type': 'group-subcategory-dropdown', 'index': MATCH}, 'options'),
            Output({'type': 'group-subcategory-dropdown', 'index': MATCH}, 'disabled'),
            Output({'type': 'group-subcategory-dropdown', 'index': MATCH}, 'value'),
            [Input({'type': 'group-category-dropdown', 'index': MATCH}, 'value'),
             Input('subcategory-lookup-data', 'children')],
            prevent_initial_call=True
        )
        def update_subcategory_dropdown(category_value, subcategory_data_json):
            """Update a specific subcategory dropdown based on its category selection."""
            if not subcategory_data_json:
                return [], True, None
            
            try:
                subcategory_data = json.loads(subcategory_data_json)
            except:
                return [], True, None
            
            if category_value and category_value != 'CREATE_NEW_CATEGORY' and category_value in subcategory_data:
                # Category selected and has subcategories
                options = subcategory_data[category_value]
                disabled = False
                value = None  # Reset subcategory selection when category changes
            else:
                # No category selected or no subcategories available
                options = []
                disabled = True
                value = None
            
            return options, disabled, value
        
        # Callback for individual apply buttons
        @self.app.callback(
            [Output('review-feedback-messages', 'children'),
             Output('tab-content', 'children')],  # Refresh the tab content
            [Input({'type': 'group-apply-btn', 'index': ALL}, 'n_clicks')],
            [State({'type': 'group-category-dropdown', 'index': ALL}, 'value'),
             State({'type': 'group-subcategory-dropdown', 'index': ALL}, 'value'),
             State('main-tabs', 'active_tab'),
             State('date-range-picker', 'start_date'),
             State('date-range-picker', 'end_date')],
            prevent_initial_call=True
        )
        def handle_apply_button_clicks(n_clicks_list, category_values, subcategory_values, 
                                     active_tab, start_date, end_date):
            """Handle apply button clicks for individual transaction groups."""
            if not any(n_clicks_list) or not category_values:
                return "", dash.no_update
            
            # Find which button was clicked
            import dash
            from dash import no_update
            ctx = dash.callback_context
            if not ctx.triggered:
                return "", no_update
            
            button_id = ctx.triggered[0]['prop_id'].split('.')[0]
            clicked_index = json.loads(button_id)['index']
            
            # Find the corresponding category and subcategory
            clicked_category = None
            clicked_subcategory = None
            
            for i, (cat, subcat) in enumerate(zip(category_values, subcategory_values)):
                if i + 1 == clicked_index:  # group_id is 1-indexed
                    clicked_category = cat
                    clicked_subcategory = subcat
                    break
            
            if not clicked_category:
                return dbc.Alert("Please select a category first.", color="warning", duration=3000), no_update
            
            # Apply the categorization to transactions
            success_result = self._apply_categorization(clicked_index, clicked_category, clicked_subcategory)
            
            if success_result['success']:
                # Refresh the tab content to remove the applied row
                if start_date:
                    start_date = datetime.fromisoformat(start_date)
                if end_date:
                    end_date = datetime.fromisoformat(end_date)
                
                filtered_data = analyzer.filter_transactions_by_date_range(
                    self.categorized_data, start_date, end_date
                )
                
                new_tab_content = self.create_review_other_tab(filtered_data)
                
                category_display = clicked_category.replace('_', ' ').title()
                subcategory_display = clicked_subcategory.replace('_', ' ').title() if clicked_subcategory else 'General'
                
                feedback = dbc.Alert([
                    html.Strong("✅ Applied Successfully!"), 
                    f" Categorized {success_result['count']} transactions as {category_display} → {subcategory_display}. ",
                    f"Row removed from table."
                ], color="success", duration=4000)
                
                return feedback, new_tab_content
            else:
                feedback = dbc.Alert([
                    html.Strong("❌ Error!"), 
                    f" {success_result['error']}"
                ], color="danger", duration=5000)
                
                return feedback, no_update
        
        # Callback for retrain ML model button
        @self.app.callback(
            Output('bulk-action-feedback', 'children'),
            [Input('retrain-model-btn', 'n_clicks')],
            prevent_initial_call=True
        )
        def handle_retrain_model_button(n_clicks):
            """Handle retrain ML model button clicks."""
            if not n_clicks:
                return ""
            
            try:
                from .user_feedback import UserFeedbackManager
                
                # Initialize feedback manager
                feedback_manager = UserFeedbackManager()
                
                # Check if we have any user corrections to train on
                if not os.path.exists(feedback_manager.feedback_file):
                    return dbc.Alert([
                        html.Strong("⚠️ No Training Data"), 
                        " No user corrections found. Apply some category changes first, then retrain the model."
                    ], color="warning", duration=8000)
                
                # Retrain ML model
                training_results = feedback_manager.retrain_ml_model()
                
                if 'error' in training_results:
                    return dbc.Alert([
                        html.Strong("❌ Training Failed"), 
                        f" {training_results['error']}"
                    ], color="danger", duration=8000)
                
                # Success message with training stats
                accuracy = training_results.get('test_accuracy', 0)
                train_size = training_results.get('train_size', 0)
                
                return dbc.Alert([
                    html.Strong("🎉 Model Retrained Successfully!"), 
                    html.Br(),
                    f"Trained on {train_size} transactions",
                    html.Br(),
                    f"New model accuracy: {accuracy:.1%}",
                    html.Br(),
                    html.Small("The model will now provide better categorization suggestions.", className="text-muted")
                ], color="success", duration=10000)
                
            except Exception as e:
                return dbc.Alert([
                    html.Strong("❌ Unexpected Error"), 
                    f" Failed to retrain model: {str(e)}"
                ], color="danger", duration=8000)
        
        # Add transaction filtering and sorting callback
        @self.app.callback(
            Output('filtered-transactions-table', 'children'),
            [Input('transaction-search', 'value'),
             Input('transaction-category-filter', 'value'),
             Input('sort-column-store', 'data'),
             Input('sort-direction-store', 'data')],
            [State('tab-content', 'children')],
            prevent_initial_call=True
        )
        def update_transaction_table(search_value, category_filter, sort_column, sort_direction, tab_content):
            """Update transaction table based on filters and sorting."""
            # Get the current filtered data from the active tab
            if not hasattr(self, '_current_filtered_data'):
                return "No data available"
            
            filtered_data = self._current_filtered_data
            
            # Apply search filter
            if search_value and search_value.strip():
                search_lower = search_value.lower()
                filtered_data = [
                    t for t in filtered_data 
                    if search_lower in t['description'].lower() or
                       search_lower in self.get_payment_method_display(t).lower()
                ]
            
            # Apply category filter
            if category_filter and category_filter != 'all':
                if category_filter == 'income':
                    filtered_data = [t for t in filtered_data if t['amount'] > 0]
                elif category_filter == 'expenses':
                    filtered_data = [t for t in filtered_data if t['amount'] < 0]
                else:
                    filtered_data = [t for t in filtered_data if t.get('category', '').lower() == category_filter.lower()]
            
            # Apply sorting
            if sort_column:
                reverse = (sort_direction == 'desc')
                
                if sort_column == 'date':
                    # Ensure dates are datetime objects for sorting
                    for txn in filtered_data:
                        if isinstance(txn['date'], str):
                            try:
                                txn['date'] = datetime.fromisoformat(txn['date'])
                            except:
                                txn['date'] = datetime.strptime(txn['date'], '%Y-%m-%d %H:%M:%S')
                    filtered_data.sort(key=lambda x: x['date'], reverse=reverse)
                elif sort_column == 'amount':
                    filtered_data.sort(key=lambda x: x['amount'], reverse=reverse)
                elif sort_column == 'description':
                    filtered_data.sort(key=lambda x: x['description'].lower(), reverse=reverse)
                elif sort_column == 'payment_method':
                    filtered_data.sort(key=lambda x: self.get_payment_method_display(x).lower(), reverse=reverse)
                elif sort_column == 'category':
                    filtered_data.sort(key=lambda x: (x.get('category', ''), x.get('subcategory', '')), reverse=reverse)
            
            # Return updated table
            return self.create_transactions_table(filtered_data[:50], sort_by_date=False)
        
        # Add column header click callback for sorting
        @self.app.callback(
            [Output('sort-column-store', 'data'),
             Output('sort-direction-store', 'data')],
             [Input('sort-date-btn', 'n_clicks'),
              Input('sort-payment-method-btn', 'n_clicks'),
              Input('sort-description-btn', 'n_clicks'),
              Input('sort-category-btn', 'n_clicks'),
              Input('sort-amount-btn', 'n_clicks')],
            [State('sort-column-store', 'data'),
             State('sort-direction-store', 'data')],
            prevent_initial_call=True
        )
        def handle_column_sorting(date_clicks, payment_method_clicks, desc_clicks, cat_clicks, amount_clicks, 
                                current_column, current_direction):
            """Handle column header clicks for sorting."""
            ctx = dash.callback_context
            if not ctx.triggered:
                return current_column, current_direction
            
            button_id = ctx.triggered[0]['prop_id'].split('.')[0]
            
            # Determine which column was clicked
            if button_id == 'sort-date-btn':
                new_column = 'date'
            elif button_id == 'sort-payment-method-btn':
                new_column = 'payment_method'
            elif button_id == 'sort-description-btn':
                new_column = 'description'
            elif button_id == 'sort-category-btn':
                new_column = 'category'
            elif button_id == 'sort-amount-btn':
                new_column = 'amount'
            else:
                return current_column, current_direction
            
            # Toggle direction if same column, otherwise default to descending
            if current_column == new_column:
                new_direction = 'asc' if current_direction == 'desc' else 'desc'
            else:
                new_direction = 'desc'  # Default to descending for new columns
            
            return new_column, new_direction
    
    def create_category_pie_chart(self, transactions: List[Dict]) -> go.Figure:
        """Create category spending pie chart."""
        # Only include expenses (negative amounts)
        expense_transactions = [t for t in transactions if t['amount'] < 0]
        
        category_totals = {}
        for transaction in expense_transactions:
            category = transaction['category'].title()
            amount = abs(transaction['amount'])
            
            if category not in category_totals:
                category_totals[category] = 0
            category_totals[category] += amount
        
        if not category_totals:
            # Empty chart if no data
            fig = go.Figure()
            fig.add_annotation(
                text="No expense data available",
                xref="paper", yref="paper",
                x=0.5, y=0.5, xanchor='center', yanchor='middle',
                showarrow=False, font=dict(size=16)
            )
            return fig
        
        fig = px.pie(
            values=list(category_totals.values()),
            names=list(category_totals.keys()),
            title="Spending by Category"
        )
        
        fig.update_traces(textposition='inside', textinfo='percent+label')
        fig.update_layout(template='plotly_white')
        
        return fig
    
    def create_subcategory_pie_chart(self, transactions: List[Dict], selected_category: str = None) -> go.Figure:
        """Create subcategory spending pie chart for a specific category or all subcategories."""
        # Only include expenses (negative amounts)
        expense_transactions = [t for t in transactions if t['amount'] < 0]
        
        # Filter by category if specified
        if selected_category:
            expense_transactions = [t for t in expense_transactions if t.get('category', '').lower() == selected_category.lower()]
        
        subcategory_totals = {}
        for transaction in expense_transactions:
            category = transaction.get('category', 'Unknown').title()
            subcategory = transaction.get('subcategory', 'Unknown')
            amount = abs(transaction['amount'])
            
            # Create hierarchical labels
            if selected_category:
                # Show just subcategories for the selected category
                label = subcategory.title() if subcategory else 'Unknown'
            else:
                # Show category -> subcategory for all
                label = f"{category} → {subcategory.title()}" if subcategory else f"{category} → Unknown"
            
            if label not in subcategory_totals:
                subcategory_totals[label] = 0
            subcategory_totals[label] += amount
        
        if not subcategory_totals:
            # Empty chart if no data
            fig = go.Figure()
            fig.add_annotation(
                text="No expense data available",
                xref="paper", yref="paper",
                x=0.5, y=0.5, xanchor='center', yanchor='middle',
                showarrow=False, font=dict(size=16)
            )
            return fig
        
        # Limit to top 15 subcategories for readability
        sorted_subcategories = sorted(subcategory_totals.items(), key=lambda x: x[1], reverse=True)
        if len(sorted_subcategories) > 15:
            top_subcategories = sorted_subcategories[:14]
            other_total = sum(amount for _, amount in sorted_subcategories[14:])
            top_subcategories.append(('Others', other_total))
            subcategory_totals = dict(top_subcategories)
        
        title = f"Spending by Subcategory" + (f" - {selected_category.title()}" if selected_category else "")
        
        fig = px.pie(
            values=list(subcategory_totals.values()),
            names=list(subcategory_totals.keys()),
            title=title
        )
        
        fig.update_traces(textposition='inside', textinfo='percent+label')
        fig.update_layout(template='plotly_white')
        
        return fig
    
    def create_category_trends_chart(self, transactions: List[Dict]) -> go.Figure:
        """Create category spending trends over time."""
        monthly_data = analyzer.calculate_monthly_summary(transactions)
        
        if not monthly_data:
            fig = go.Figure()
            fig.add_annotation(
                text="No data available",
                xref="paper", yref="paper",
                x=0.5, y=0.5, xanchor='center', yanchor='middle',
                showarrow=False, font=dict(size=16)
            )
            return fig
        
        # Get all categories (excluding income)
        all_categories = set()
        for month_data in monthly_data.values():
            all_categories.update(month_data['categories'].keys())
        all_categories.discard('income')  # Remove income from expenses chart
        
        fig = go.Figure()
        
        months = sorted(monthly_data.keys())
        
        for category in sorted(all_categories):
            values = []
            for month in months:
                category_amount = monthly_data[month]['categories'].get(category, 0)
                # Take absolute value for expenses
                values.append(abs(category_amount) if category_amount < 0 else 0)
            
            if any(v > 0 for v in values):  # Only show categories with data
                fig.add_trace(go.Scatter(
                    x=months,
                    y=values,
                    mode='lines+markers',
                    name=category.title(),
                    marker=dict(size=6)
                ))
        
        fig.update_layout(
            title="Monthly Spending by Category",
            xaxis_title="Month",
            yaxis_title=f"Amount ({self.currency_symbol})",
            hovermode='x unified',
            template='plotly_white'
        )
        
        return fig
    
    def create_income_expenses_chart(self, filtered_data: List[Dict], aggregation: str = 'monthly') -> go.Figure:
        """Create income/expenses bar chart with running balance line.
        
        Args:
            filtered_data: List of transaction dicts
            aggregation: 'weekly' or 'monthly'
        """
        if not filtered_data:
            fig = go.Figure()
            fig.add_annotation(
                text="No data available",
                xref="paper", yref="paper",
                x=0.5, y=0.5, xanchor='center', yanchor='middle',
                showarrow=False, font=dict(size=16)
            )
            return fig
        
        # Ensure dates are datetime objects
        for txn in filtered_data:
            if isinstance(txn['date'], str):
                txn['date'] = datetime.fromisoformat(txn['date'])
        
        sorted_txns = sorted(filtered_data, key=lambda x: x['date'])
        first_date = sorted_txns[0]['date']
        last_date = sorted_txns[-1]['date']
        
        # Build complete sequence of period datetime keys (no gaps)
        period_dates = []  # list of datetime (Monday for weekly, 1st of month for monthly)
        if aggregation == 'weekly':
            cursor = first_date - timedelta(days=first_date.weekday())  # Monday of first week
            end = last_date - timedelta(days=last_date.weekday())       # Monday of last week
            while cursor <= end:
                period_dates.append(cursor)
                cursor += timedelta(weeks=1)
        else:
            cursor = first_date.replace(day=1)
            end = last_date.replace(day=1)
            while cursor <= end:
                period_dates.append(cursor)
                # Advance one month
                if cursor.month == 12:
                    cursor = cursor.replace(year=cursor.year + 1, month=1)
                else:
                    cursor = cursor.replace(month=cursor.month + 1)
        
        # Map each period datetime -> aggregated values
        period_map = {d: {'income': 0.0, 'expenses': 0.0, 'net': 0.0} for d in period_dates}
        
        for txn in sorted_txns:
            d = txn['date']
            if aggregation == 'weekly':
                key = d - timedelta(days=d.weekday())
            else:
                key = d.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            
            if key not in period_map:
                period_map[key] = {'income': 0.0, 'expenses': 0.0, 'net': 0.0}
            
            if txn['amount'] > 0:
                period_map[key]['income'] += txn['amount']
            else:
                period_map[key]['expenses'] += txn['amount']  # keep negative
            period_map[key]['net'] += txn['amount']
        
        x_dates    = period_dates
        income_vals  = [period_map[d]['income']   for d in x_dates]
        expense_vals = [period_map[d]['expenses'] for d in x_dates]
        
        # Calculate running balance
        balance_txns = [t for t in sorted_txns if t.get('balance') is not None and t.get('balance') != 0.0]
        if balance_txns:
            first_balance_txn = balance_txns[0]
            idx = sorted_txns.index(first_balance_txn)
            cumulative_to_first = sum(t['amount'] for t in sorted_txns[:idx + 1])
            opening_balance = first_balance_txn['balance'] - cumulative_to_first
        else:
            opening_balance = 0.0
        
        running_balance = []
        cumulative = opening_balance
        for d in x_dates:
            cumulative += period_map[d]['net']
            running_balance.append(cumulative)
        
        # y-axis range for balance: always include 0 as lower bound
        balance_min = min(running_balance)
        balance_max = max(running_balance)
        y2_min = min(0.0, balance_min * 1.05)
        y2_max = balance_max * 1.05
        
        # x-axis tick format and spacing
        blue = 'rgba(31, 119, 180, 0.9)'
        if aggregation == 'weekly':
            tick_format = '%d %b'
            # Show roughly every 4 weeks to avoid crowding
            n_weeks = len(x_dates)
            dtick = max(1, round(n_weeks / 8)) * 7 * 24 * 3600000  # ms
        else:
            tick_format = '%b %Y'
            dtick = 'M1'
        
        # Build figure with secondary y-axis
        fig = go.Figure()
        
        # Income bars (green, above zero)
        fig.add_trace(go.Bar(
            x=x_dates,
            y=income_vals,
            name='Income',
            marker_color='rgba(44, 160, 44, 0.75)',
            hovertemplate=f'{self.currency_symbol}%{{y:,.2f}}<extra>Income</extra>'
        ))
        
        # Expense bars (red, below zero)
        fig.add_trace(go.Bar(
            x=x_dates,
            y=expense_vals,
            name='Expenses',
            marker_color='rgba(214, 39, 40, 0.75)',
            hovertemplate=f'{self.currency_symbol}%{{y:,.2f}}<extra>Expenses</extra>'
        ))
        
        # Running balance line on secondary y-axis
        fig.add_trace(go.Scatter(
            x=x_dates,
            y=running_balance,
            name='Balance',
            mode='lines+markers',
            line=dict(color=blue, width=2.5),
            marker=dict(size=5),
            yaxis='y2',
            hovertemplate=f'{self.currency_symbol}%{{y:,.2f}}<extra>Balance</extra>'
        ))
        
        fig.update_layout(
            template='plotly_white',
            hovermode='x unified',
            barmode='relative',
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=1.02,
                xanchor="right",
                x=1
            ),
            xaxis=dict(
                type='date',
                tickformat=tick_format,
                dtick=dtick,
                tickangle=0,
            ),
            yaxis=dict(
                tickprefix=self.currency_symbol,
                zeroline=True,
                zerolinecolor='rgba(128, 128, 128, 0.4)',
                zerolinewidth=1,
            ),
            yaxis2=dict(
                tickprefix=self.currency_symbol,
                overlaying='y',
                side='right',
                showgrid=False,
                range=[y2_min, y2_max],
                tickfont=dict(color=blue),
            ),
            margin=dict(t=30, b=60),
        )
        
        return fig
    
    def create_daily_waterfall_chart(self, filtered_data: List[Dict], aggregation='daily') -> go.Figure:
        """Create traditional waterfall chart with aggregated net flows and connecting lines."""
        try:
            if not filtered_data:
                return self._create_empty_chart("No transaction data available")
            
            # Get 6-month window and prepare data
            windowed_data, opening_balance = self._prepare_waterfall_data(filtered_data)
            
            if not windowed_data:
                return self._create_empty_chart("No transactions in the selected time window")
            
            # Create aggregated waterfall data
            waterfall_data = self._create_aggregated_waterfall_data(windowed_data, opening_balance, aggregation)
            
            # Build traditional waterfall visualization
            fig = self._build_traditional_waterfall(waterfall_data, aggregation)
            
            return fig
            
        except Exception as e:
            logger.error(f"Error creating waterfall chart: {e}")
            return self._create_empty_chart(f"Error processing data: {str(e)}")
    
    def create_waterfall_chart_with_aggregation(self, filtered_data: List[Dict], aggregation='daily') -> go.Figure:
        """Wrapper method for callback compatibility."""
        return self.create_daily_waterfall_chart(filtered_data, aggregation)
    
    def _prepare_waterfall_data(self, filtered_data):
        """Prepare data window and calculate opening balance."""
        # Get 6-month window
        dates = []
        for txn in filtered_data:
            if isinstance(txn['date'], str):
                dates.append(datetime.fromisoformat(txn['date']))
            else:
                dates.append(txn['date'])
        
        latest_date = max(dates)
        six_months_ago = latest_date - timedelta(days=180)
        earliest_date = min(dates)
        window_start = max(six_months_ago, earliest_date)
        
        # Filter to window
        windowed_data = []
        for txn in filtered_data:
            txn_date = txn['date'] if isinstance(txn['date'], datetime) else datetime.fromisoformat(txn['date'])
            if txn_date >= window_start:
                windowed_data.append(txn)
        
        # Calculate opening balance using existing dashboard logic
        balance_transactions = [t for t in filtered_data if t.get('balance') is not None]
        balance_transactions.sort(key=lambda x: x['date'] if isinstance(x['date'], datetime) else datetime.fromisoformat(x['date']))
        
        if not balance_transactions:
            raise ValueError("No balance data available")
        
        # Calculate opening balance: the balance field is an end-of-day value,
        # so we must subtract ALL transactions up to and including the first
        # balance transaction, not just its own amount.
        sorted_all = sorted(filtered_data, key=lambda x: x['date'] if isinstance(x['date'], datetime) else datetime.fromisoformat(x['date']))
        first_balance_txn = balance_transactions[0]
        idx = sorted_all.index(first_balance_txn)
        cumulative = sum(t['amount'] for t in sorted_all[:idx + 1])
        base_opening_balance = first_balance_txn['balance'] - cumulative
        
        # Adjust for transactions before window
        transactions_before = []
        for t in filtered_data:
            txn_date = t['date'] if isinstance(t['date'], datetime) else datetime.fromisoformat(t['date'])
            if txn_date < window_start:
                transactions_before.append(t)
        
        total_before = sum(t['amount'] for t in transactions_before)
        opening_balance = base_opening_balance + total_before
        
        return windowed_data, opening_balance
    
    def _create_aggregated_waterfall_data(self, transactions, opening_balance, aggregation='daily'):
        """Create aggregated waterfall data for specified period type."""
        from collections import defaultdict
        
        # Group transactions by period
        periods = defaultdict(lambda: {'income': [], 'expenses': [], 'net_flow': 0})
        
        for txn in transactions:
            # Handle datetime
            txn_date = txn['date'] if isinstance(txn['date'], datetime) else datetime.fromisoformat(txn['date'])
            
            # Determine period key based on aggregation
            if aggregation == 'daily':
                period_key = txn_date.strftime('%Y-%m-%d')
                period_label = txn_date.strftime('%d %b')
            elif aggregation == 'weekly':
                # Week starting Monday
                week_start = txn_date - timedelta(days=txn_date.weekday())
                period_key = week_start.strftime('%Y-W%U')
                period_label = f"Week {week_start.strftime('%d %b')}"
            else:  # monthly
                period_key = txn_date.strftime('%Y-%m')
                period_label = txn_date.strftime('%b %Y')
            
            # Store transaction details
            if txn['amount'] > 0:
                periods[period_key]['income'].append(txn)
            else:
                periods[period_key]['expenses'].append(txn)
            
            periods[period_key]['net_flow'] += txn['amount']
            periods[period_key]['period_label'] = period_label
            periods[period_key]['period_date'] = txn_date
        
        # Sort periods chronologically
        sorted_periods = sorted(periods.items(), key=lambda x: x[1]['period_date'])
        
        # Create waterfall segments
        waterfall_data = {
            'x': [],  # Period labels
            'y': [],  # Amounts (opening balance + net flows)
            'measure': [],  # absolute for opening, relative for changes
            'text': [],  # Display text
            'hover_data': [],  # Detailed hover information
            'connector': {"line": {"color": "rgb(63, 63, 63)"}},
            'increasing': {"marker": {"color": "green"}},
            'decreasing': {"marker": {"color": "red"}},
            'totals': {"marker": {"color": "blue"}}
        }
        
        # Opening balance
        waterfall_data['x'].append('Opening Balance')
        waterfall_data['y'].append(opening_balance)
        waterfall_data['measure'].append('absolute')
        waterfall_data['text'].append(f"{self.currency_symbol}{opening_balance:,.2f}")
        waterfall_data['hover_data'].append(f"Opening Balance: {self.currency_symbol}{opening_balance:,.2f}")
        
        # Add each period's net flow
        for period_key, period_data in sorted_periods:
            if period_data['net_flow'] == 0:
                continue  # Skip periods with no net change
                
            waterfall_data['x'].append(period_data['period_label'])
            waterfall_data['y'].append(period_data['net_flow'])
            waterfall_data['measure'].append('relative')
            
            # Format text
            net_flow = period_data['net_flow']
            text = f"{self.currency_symbol}{net_flow:+,.2f}"
            waterfall_data['text'].append(text)
            
            # Create detailed hover info
            income_count = len(period_data['income'])
            expense_count = len(period_data['expenses'])
            income_total = sum(t['amount'] for t in period_data['income'])
            expense_total = sum(abs(t['amount']) for t in period_data['expenses'])
            
            hover_info = f"""<b>{period_data['period_label']}</b><br>
Net Flow: {self.currency_symbol}{net_flow:+,.2f}<br>
Income: {income_count} transactions ({self.currency_symbol}{income_total:,.2f})<br>
Expenses: {expense_count} transactions ({self.currency_symbol}{expense_total:,.2f})"""
            
            # Add top transactions for this period
            all_period_txns = period_data['income'] + period_data['expenses']
            top_txns = sorted(all_period_txns, key=lambda x: abs(x['amount']), reverse=True)[:3]
            
            if top_txns:
                hover_info += "<br><br>Top Transactions:"
                for txn in top_txns:
                    hover_info += f"<br>• {txn['description'][:30]}... {self.currency_symbol}{txn['amount']:+.2f}"
            
            waterfall_data['hover_data'].append(hover_info)
        
        # Add closing balance (total)
        total_net_flow = sum(period_data['net_flow'] for _, period_data in sorted_periods if period_data['net_flow'] != 0)
        closing_balance = opening_balance + total_net_flow
        
        # Find the latest transaction's actual balance for validation (if available)
        latest_balance = None
        if transactions:
            # Sort transactions by date to find the latest one with balance data
            sorted_txns = sorted(transactions, key=lambda x: x['date'] if isinstance(x['date'], datetime) else datetime.fromisoformat(x['date']))
            for txn in reversed(sorted_txns):
                if txn.get('balance') is not None and txn.get('balance') != 0:
                    latest_balance = txn['balance']
                    break
        
        waterfall_data['x'].append('Closing Balance')
        waterfall_data['y'].append(closing_balance)
        waterfall_data['measure'].append('total')
        waterfall_data['text'].append(f"{self.currency_symbol}{closing_balance:,.2f}")
        
        # Enhanced hover with validation info
        hover_info = f"Closing Balance: {self.currency_symbol}{closing_balance:,.2f}<br>Net Change: {self.currency_symbol}{total_net_flow:+,.2f}"
        if latest_balance is not None:
            balance_diff = abs(closing_balance - latest_balance)
            if balance_diff < 0.01:
                hover_info += f"<br>✅ Validated against latest transaction balance"
            else:
                hover_info += f"<br>⚠️ Differs from latest balance: {self.currency_symbol}{latest_balance:,.2f}"
        waterfall_data['hover_data'].append(hover_info)
        
        return waterfall_data
    
    def _build_traditional_waterfall(self, waterfall_data, aggregation='daily'):
        """Build the traditional waterfall chart with plotly."""
        fig = go.Figure()
        
        # Create waterfall chart
        fig.add_trace(go.Waterfall(
            name="Balance Flow",
            orientation="v",
            measure=waterfall_data['measure'],
            x=waterfall_data['x'],
            y=waterfall_data['y'],
            text=waterfall_data['text'],
            textposition="auto",
            connector=waterfall_data['connector'],
            increasing=waterfall_data['increasing'],
            decreasing=waterfall_data['decreasing'],
            totals=waterfall_data['totals'],
            hovertemplate="%{customdata}<extra></extra>",
            customdata=waterfall_data['hover_data']
        ))
        
        # Compute tick subset — always show Opening/Closing, sample ~12 intermediate labels
        all_labels = waterfall_data['x']
        n = len(all_labels)
        intermediate_indices = list(range(1, n - 1))  # exclude first (Opening) and last (Closing)
        target_ticks = 12
        step = max(1, len(intermediate_indices) // target_ticks)
        sampled = intermediate_indices[::step]
        tick_indices = [0] + sampled + [n - 1]
        tickvals = [all_labels[i] for i in tick_indices]
        
        fig.update_layout(
            template='plotly_white',
            hovermode='x unified',
            height=600,
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=1.02,
                xanchor="right",
                x=1
            ),
            xaxis=dict(
                tickmode='array',
                tickvals=tickvals,
                tickangle=0,
            ),
            yaxis=dict(
                tickprefix=self.currency_symbol,
            ),
            margin=dict(l=60, r=60, t=30, b=60)
        )
        
        return fig
    
    def _create_empty_chart(self, message):
        """Create empty chart with message."""
        fig = go.Figure()
        fig.add_annotation(
            text=message,
            xref="paper", yref="paper",
            x=0.5, y=0.5, xanchor='center', yanchor='middle',
            showarrow=False, font=dict(size=16)
        )
        fig.update_layout(
            title="Daily Transaction Waterfall",
            template='plotly_white',
            height=400
        )
        return fig
    
    def _get_smart_category_suggestions(self, description_lower):
        """Smart category suggestions based on keywords and patterns."""
        
        # Food & Drink keywords and patterns
        food_keywords = [
            # Cafes and food places
            'cafe', 'coffee', 'coffe', 'starbucks', 'costa', 'pret', 'nero',
            'restaurant', 'pizz', 'burger', 'mcdonald', 'kfc', 'subway',
            'takeaway', 'chippy', 'fish shop', 'indian', 'chinese', 'thai',
            # University/college food services
            'college', 'university', 'uni ', 'campus', 'refectory', 'canteen',
            'magdalen', 'oxford', 'cambridge', 'dining', 'hall', 'lodge',
            # General food terms
            'food', 'lunch', 'dinner', 'breakfast', 'meal', 'eating',
            'sandwich', 'snack', 'bakery', 'deli', 'grocery',
            # Supermarkets
            'tesco', 'sainsbury', 'asda', 'morrisons', 'aldi', 'lidl',
            'waitrose', 'marks spencer', 'co-op', 'iceland'
        ]
        
        # Transport keywords
        transport_keywords = [
            'petrol', 'fuel', 'diesel', 'bp ', 'shell', 'esso', 'texaco',
            'train', 'railway', 'bus', 'taxi', 'uber', 'lyft', 'parking',
            'ticket', 'travel', 'journey', 'station', 'airport'
        ]
        
        # Shopping keywords
        shopping_keywords = [
            'amazon', 'ebay', 'argos', 'currys', 'john lewis', 'next',
            'h&m', 'zara', 'primark', 'boots', 'superdrug', 'wilko'
        ]
        
        # Bills & Utilities keywords
        utilities_keywords = [
            'electric', 'gas', 'water', 'council tax', 'internet', 'broadband',
            'mobile', 'phone', 'vodafone', 'ee ', 'o2', 'three', 'bt ',
            'sky', 'virgin', 'tv licence', 'netflix', 'spotify'
        ]
        
        # Healthcare keywords
        healthcare_keywords = [
            'pharmacy', 'chemist', 'doctor', 'dentist', 'hospital', 'nhs',
            'medical', 'prescription', 'optician', 'health'
        ]
        
        # Check for food & drink patterns
        for keyword in food_keywords:
            if keyword in description_lower:
                # Determine subcategory based on actual config structure
                if any(k in description_lower for k in ['cafe', 'coffee', 'coffe', 'starbucks', 'costa', 'pret']):
                    return 'food_drink', 'cafe'
                elif any(k in description_lower for k in ['college', 'university', 'magdalen', 'oxford', 'cambridge', 'campus']):
                    return 'food_drink', 'restaurant'
                elif any(k in description_lower for k in ['tesco', 'sainsbury', 'asda', 'morrisons', 'aldi', 'lidl']):
                    return 'groceries', 'tesco' if 'tesco' in description_lower else 'other_grocery'
                elif any(k in description_lower for k in ['restaurant', 'dining', 'takeaway', 'pizz', 'burger']):
                    return 'food_drink', 'restaurant'
                else:
                    return 'groceries', 'other_grocery'
        
        # Check for transport patterns (only if not food)
        for keyword in transport_keywords:
            if keyword in description_lower:
                if any(k in description_lower for k in ['petrol', 'fuel', 'diesel', 'bp', 'shell', 'esso']):
                    return 'transportation', 'fuel'
                elif any(k in description_lower for k in ['train', 'railway', 'bus', 'ticket']):
                    return 'transportation', 'public_transport'
                elif any(k in description_lower for k in ['taxi', 'uber', 'lyft']):
                    return 'transportation', 'taxi'
                else:
                    return 'transportation', 'other_transport'
        
        # Check for shopping patterns
        for keyword in shopping_keywords:
            if keyword in description_lower:
                if 'amazon' in description_lower:
                    return 'shopping', 'amazon'
                else:
                    return 'shopping', 'other_retail'
        
        # Check for utilities patterns
        for keyword in utilities_keywords:
            if keyword in description_lower:
                if any(k in description_lower for k in ['electric', 'gas', 'water']):
                    return 'utilities', 'electricity'
                elif any(k in description_lower for k in ['mobile', 'phone', 'vodafone', 'ee', 'o2']):
                    return 'utilities', 'mobile'
                elif any(k in description_lower for k in ['internet', 'broadband', 'bt', 'sky', 'virgin']):
                    return 'utilities', 'internet'
                else:
                    return 'bills', 'services'
        
        # Check for healthcare patterns
        for keyword in healthcare_keywords:
            if keyword in description_lower:
                return 'healthcare', 'medical'
        
        return None
    
    def _apply_categorization(self, group_index, category, subcategory):
        """Apply categorization to a specific group of transactions."""
        try:
            # We need to find transactions by their description since group_index 
            # corresponds to the order they appear in the Review Other tab
            
            # Get other transactions to find the matching group
            other_transactions = [t for t in self.categorized_data if t.get('category', '').lower() == 'other']
            
            if not other_transactions:
                return {'success': False, 'error': 'No other transactions found'}
            
            # Group by description
            from collections import defaultdict
            desc_groups = defaultdict(list)
            for txn in other_transactions:
                desc = txn['description'].strip()
                desc_groups[desc].append(txn)
            
            # Sort groups by frequency (same as in UI)
            sorted_groups = sorted(desc_groups.items(), key=lambda x: len(x[1]), reverse=True)
            
            # Find the group corresponding to the clicked index
            if group_index > len(sorted_groups):
                return {'success': False, 'error': 'Invalid group index'}
            
            target_description, target_transactions = sorted_groups[group_index - 1]  # group_index is 1-based
            
            # Update all transactions in this group
            updated_count = 0
            for txn in target_transactions:
                # Find the transaction in the main data and update it
                for i, main_txn in enumerate(self.categorized_data):
                    if (main_txn['description'] == txn['description'] and 
                        main_txn['amount'] == txn['amount'] and
                        main_txn['date'] == txn['date']):
                        
                        self.categorized_data[i]['category'] = category
                        self.categorized_data[i]['subcategory'] = subcategory or 'unknown'
                        updated_count += 1
                        break
            
            if updated_count > 0:
                # Save the updated data back to file
                self._save_categorized_data()
                return {'success': True, 'count': updated_count}
            else:
                return {'success': False, 'error': 'No transactions were updated'}
                
        except Exception as e:
            logger.error(f"Error applying categorization: {e}")
            return {'success': False, 'error': f'Error: {str(e)}'}
    
    def _save_categorized_data(self):
        """Save the updated categorized data back to the file."""
        try:
            categorized_path = config.get('data.categorized', './data/categorized')
            file_path = os.path.join(categorized_path, 'all_categorized_transactions.json')
            
            # Convert datetime objects to ISO strings for JSON serialization
            data_to_save = []
            for txn in self.categorized_data:
                txn_copy = txn.copy()
                if isinstance(txn_copy['date'], datetime):
                    txn_copy['date'] = txn_copy['date'].isoformat()
                data_to_save.append(txn_copy)
            
            with open(file_path, 'w') as f:
                json.dump(data_to_save, f, indent=2)
                
            logger.info(f"Saved {len(data_to_save)} transactions to {file_path}")
            return True
            
        except Exception as e:
            logger.error(f"Error saving categorized data: {e}")
            return False
    
    def create_transactions_table(self, transactions: List[Dict], sort_by_date: bool = True) -> html.Table:
        """Create transactions table."""
        if not transactions:
            return html.P("No transactions to display")
        
        if sort_by_date:
            # Ensure dates are datetime objects and sort by date (most recent first)
            for txn in transactions:
                if isinstance(txn['date'], str):
                    try:
                        txn['date'] = datetime.fromisoformat(txn['date'])
                    except:
                        # Fallback for any problematic date strings
                        txn['date'] = datetime.strptime(txn['date'], '%Y-%m-%d %H:%M:%S')
            
            sorted_transactions = sorted(transactions, key=lambda x: x['date'], reverse=True)
        else:
            # Use transactions as-is (assume already sorted)
            sorted_transactions = transactions
        
        header = html.Thead([
            html.Tr([
                html.Th([
                    dbc.Button([
                        html.I(className="fas fa-calendar-alt me-1"),
                        "Date",
                        html.I(className="fas fa-sort ms-1", style={"opacity": "0.6"})
                    ], 
                    id="sort-date-btn",
                    color="link", 
                    className="text-decoration-none p-0 text-dark fw-bold",
                     style={"border": "none", "background": "none"}
                     )
                 ]),
                 html.Th([
                     dbc.Button([
                         html.I(className="fas fa-credit-card me-1"),
                         "Payment Method",
                         html.I(className="fas fa-sort ms-1", style={"opacity": "0.6"})
                     ], 
                     id="sort-payment-method-btn",
                     color="link", 
                     className="text-decoration-none p-0 text-dark fw-bold",
                     style={"border": "none", "background": "none"}
                     )
                 ]),
                 html.Th([
                     dbc.Button([
                         html.I(className="fas fa-align-left me-1"),
                        "Description",
                        html.I(className="fas fa-sort ms-1", style={"opacity": "0.6"})
                    ], 
                    id="sort-description-btn",
                    color="link", 
                    className="text-decoration-none p-0 text-dark fw-bold",
                    style={"border": "none", "background": "none"}
                    )
                ]),
                html.Th([
                    dbc.Button([
                        html.I(className="fas fa-tags me-1"),
                        "Category",
                        html.I(className="fas fa-sort ms-1", style={"opacity": "0.6"})
                    ], 
                    id="sort-category-btn",
                    color="link", 
                    className="text-decoration-none p-0 text-dark fw-bold",
                    style={"border": "none", "background": "none"}
                    )
                ]),
                html.Th([
                    dbc.Button([
                        html.I(className="fas fa-pound-sign me-1"),
                        "Amount",
                        html.I(className="fas fa-sort ms-1", style={"opacity": "0.6"})
                    ], 
                    id="sort-amount-btn",
                    color="link", 
                    className="text-decoration-none p-0 text-dark fw-bold",
                    style={"border": "none", "background": "none"}
                    )
                ], className="text-end")
            ])
        ])
        
        rows = []
        for transaction in sorted_transactions:
            amount = transaction['amount']
            amount_class = "text-success fw-bold" if amount > 0 else "text-danger fw-bold"
            amount_str = f"{self.currency_symbol}{abs(amount):,.2f}"
            
            # Enhanced category display with subcategory
            category = transaction.get('category', 'unknown').title()
            subcategory = transaction.get('subcategory', '')
            
            if subcategory and subcategory.lower() != 'unknown':
                category_display = html.Div([
                    html.Strong(category),
                    html.Br(),
                    html.Small(subcategory.title(), className="text-muted")
                ])
            else:
                category_display = html.Strong(category)
            
            # Truncate long descriptions with tooltip (reduced to 50 chars to accommodate payment method column)
            description = transaction['description']
            reference = transaction.get('reference', None)
            
            # Build full text for tooltip
            full_tooltip = description
            if reference:
                full_tooltip = f"{description} | {reference}"
            
            # Main description (truncate if needed)
            if len(description) > 50:
                desc_element = html.Span(
                    description[:50] + "...",
                    title=full_tooltip
                )
            else:
                desc_element = html.Span(description, title=full_tooltip)
            
            # Build description display with reference underneath
            if reference:
                description_display = html.Div([
                    desc_element,
                    html.Br(),
                    html.Small(reference, className="text-muted")
                ])
            else:
                description_display = desc_element
            
            # Get payment method display
            payment_method_display = self.get_payment_method_display(transaction)
            
            row = html.Tr([
                html.Td(
                    transaction['date'].strftime('%d %b %Y'),
                    className="text-nowrap"
                ),
                html.Td(payment_method_display, className="text-nowrap"),
                html.Td(description_display),
                html.Td(category_display),
                html.Td(amount_str, className=f"{amount_class} text-end text-nowrap")
            ])
            rows.append(row)
        
        body = html.Tbody(rows)
        
        return dbc.Table([header, body], striped=True, bordered=True, hover=True, size="sm")
    
    def get_payment_method_display(self, transaction) -> str:
        """Convert payment method code to human-readable format."""
        # Payment method mappings (from HSBC parser)
        PAYMENT_METHOD_MEANINGS = {
            # Payments & transfers
            'FP': 'Faster Payment', 'FPS': 'Faster Payment Service', 'FPI': 'Faster Payment In',
            'FPO': 'Faster Payment Out', 'TRF': 'Transfer', 'TFR': 'Transfer', 'BP': 'Bill Payment',
            'OBP': 'Open Banking Payment', 'IBP': 'Inter-branch Payment', 'ITL': 'International Transfer',
            'CHAPS': 'Same-day Large Transfer', 'CHP': 'Same-day Large Transfer',
            
            # Regular payments
            'DD': 'Direct Debit', 'DDR': 'Direct Debit Return', 'SO': 'Standing Order', 
            'STO': 'Standing Order', 'BACS': 'Salary or Business Payment',
            
            # Card & retail
            'POS': 'Card Payment at Shop', 'VIS': 'Visa Transaction', 'MC': 'Mastercard Transaction',
            ')))': 'Contactless Payment', 'CSH': 'Cash',
            
            # Banking operations  
            'CR': 'Credit', 'DR': 'Debit', 'CHG': 'Charge', 'INT': 'Interest',
            'ATM': 'Cash Machine', 'DEP': 'Deposit', 'CHQ': 'Cheque'
        }
        
        # Handle both transaction dict and direct payment_method string (backward compatibility)
        if isinstance(transaction, dict):
            payment_method = transaction.get('payment_method')
            description = transaction.get('description', '')
        else:
            # If just a string is passed (backward compatibility)
            payment_method = transaction
            description = ''
        
        # If payment_method is available and not null, use it
        if payment_method:
            return PAYMENT_METHOD_MEANINGS.get(payment_method, payment_method)
        
        # If payment_method is null/empty, try to extract from description
        if description:
            # Split by newlines and check first part for payment method codes
            desc_parts = description.split('\n')
            if len(desc_parts) > 1:
                first_part = desc_parts[0].strip()
                if first_part in PAYMENT_METHOD_MEANINGS:
                    return PAYMENT_METHOD_MEANINGS[first_part]
        
        return "Unknown"
    
    def create_analytics_tab(self, filtered_data):
        """Create the analytics tab content."""
        # Store filtered data for callback access
        self._current_filtered_data = filtered_data
        
        # Income & Expenses chart (callback-driven with weekly/monthly toggle)
        income_expenses_fig = self.create_income_expenses_chart(filtered_data, 'monthly')
        
        # Category pie chart
        category_pie_fig = self.create_category_pie_chart(filtered_data)
        
        # Category trends chart
        category_trends_fig = self.create_category_trends_chart(filtered_data)
        
        # Subcategory pie chart 
        subcategory_pie_fig = self.create_subcategory_pie_chart(filtered_data)
        
        # Daily waterfall chart
        daily_waterfall_fig = self.create_daily_waterfall_chart(filtered_data)
        
        # Transactions table - sort first, then take top 50 most recent
        # Ensure dates are datetime objects for proper sorting
        for txn in filtered_data:
            if isinstance(txn['date'], str):
                try:
                    txn['date'] = datetime.fromisoformat(txn['date'])
                except:
                    # Fallback for any problematic date strings
                    txn['date'] = datetime.strptime(txn['date'], '%Y-%m-%d %H:%M:%S')
        
        sorted_filtered_data = sorted(filtered_data, key=lambda x: x['date'], reverse=True)
        transactions_table = self.create_transactions_table(sorted_filtered_data[:50], sort_by_date=False)  # Show 50 most recent
        
        return html.Div([
            # Charts
            dbc.Row([
                dbc.Col([
                    dbc.Card([
                        dbc.CardHeader([
                            dbc.Row([
                                dbc.Col(html.H5("Income & Expenses", className="mb-0"), width=8),
                                dbc.Col(dbc.ButtonGroup([
                                    dbc.Button("Weekly", id="income-exp-weekly-btn", color="outline-primary", size="sm", n_clicks=0),
                                    dbc.Button("Monthly", id="income-exp-monthly-btn", color="primary", size="sm", n_clicks=0),
                                ], size="sm", className="float-end"), width=4)
                            ], align="center")
                        ]),
                        dbc.CardBody([
                            dcc.Graph(id="income-expenses-chart", figure=income_expenses_fig)
                        ])
                    ])
                ], width=6),
                dbc.Col([
                    dbc.Card([
                        dbc.CardHeader("Spending by Category"),
                        dbc.CardBody([
                            dcc.Graph(figure=category_pie_fig)
                        ])
                    ])
                ], width=6),
            ], className="mb-4"),
            
            dbc.Row([
                dbc.Col([
                    dbc.Card([
                        dbc.CardHeader("Monthly Category Breakdown"),
                        dbc.CardBody([
                            dcc.Graph(figure=category_trends_fig)
                        ])
                    ])
                ], width=6),
                dbc.Col([
                    dbc.Card([
                        dbc.CardHeader("Spending by Subcategory"),
                        dbc.CardBody([
                            dcc.Graph(figure=subcategory_pie_fig)
                        ])
                    ])
                ], width=6),
            ], className="mb-4"),
            
            # Daily waterfall chart - full width
            dbc.Row([
                dbc.Col([
                    dbc.Card([
                        dbc.CardHeader([
                            dbc.Row([
                                dbc.Col([
                                    html.H5("Daily Transaction Waterfall - Latest 6 Months", className="mb-0")
                                ], width=8),
                                dbc.Col([
                                    dbc.ButtonGroup([
                                        dbc.Button("Daily", id="waterfall-daily-btn", color="primary", size="sm", n_clicks=0),
                                        dbc.Button("Weekly", id="waterfall-weekly-btn", color="outline-primary", size="sm", n_clicks=0), 
                                        dbc.Button("Monthly", id="waterfall-monthly-btn", color="outline-primary", size="sm", n_clicks=0)
                                    ], size="sm", className="float-end")
                                ], width=4)
                            ])
                        ]),
                        dbc.CardBody([
                            dcc.Graph(id="daily-waterfall-chart", figure=daily_waterfall_fig)
                        ])
                    ])
                ], width=12),
            ], className="mb-4"),
            
            # Transaction table with search functionality
            dbc.Row([
                dbc.Col([
                    dbc.Card([
                        dbc.CardHeader([
                            "📋 Recent Transactions",
                            html.Small(f" ({min(50, len(filtered_data))}/{len(filtered_data)} shown)", className="text-muted ms-2")
                        ]),
                        dbc.CardBody([
                            # Search/filter controls
                            dbc.Row([
                                dbc.Col([
                                    dbc.InputGroup([
                                        dbc.InputGroupText([
                                            html.I(className="fas fa-search")
                                        ]),
                                        dbc.Input(
                                            id="transaction-search",
                                            placeholder="Search transactions by description...",
                                            type="text",
                                            style={'fontSize': '0.9em'}
                                        )
                                    ], size="sm")
                                ], width=6),
                                dbc.Col([
                                    dbc.Select(
                                        id="transaction-category-filter",
                                        options=[
                                            {"label": "All Categories", "value": "all"},
                                            {"label": "Income Only", "value": "income"},
                                            {"label": "Expenses Only", "value": "expenses"}
                                        ] + [
                                            {"label": cat.title(), "value": cat} 
                                            for cat in sorted(set(t.get('category', 'unknown') for t in filtered_data))
                                        ],
                                        value="all",
                                        size="sm",
                                        style={'fontSize': '0.9em'}
                                    )
                                ], width=4),
                                dbc.Col([
                                    html.Small([
                                        "💡 Tip: Hover over truncated descriptions for full text"
                                    ], className="text-muted")
                                ], width=2)
                            ], className="mb-3"),
                            
                            # Enhanced table with better styling - dynamic filtering
                            html.Div(id='filtered-transactions-table', children=[
                                transactions_table
                            ], style={
                                'maxHeight': '500px',
                                'overflowY': 'auto',
                                'border': '1px solid #dee2e6',
                                'borderRadius': '0.375rem'
                            }),
                            
                            # Hidden data stores for sorting state
                            dcc.Store(id='sort-column-store', data=None),
                            dcc.Store(id='sort-direction-store', data='desc')
                        ])
                    ])
                ], width=12)
            ])
        ])
    
    def create_categories_tab(self, filtered_data):
        """Create the Categories tab with category and subcategory visualizations."""
        from collections import defaultdict
        
        # Aggregate data by categories and subcategories
        category_totals = defaultdict(float)
        subcategory_totals = defaultdict(lambda: defaultdict(float))
        
        for transaction in filtered_data:
            category = transaction.get('category', 'other')
            subcategory = transaction.get('subcategory', 'unknown')
            amount = abs(transaction.get('amount', 0))  # Use absolute values for expense visualization
            
            # Skip income transactions for expense analysis (focus on spending)
            if transaction.get('amount', 0) > 0:
                continue
                
            category_totals[category] += amount
            subcategory_totals[category][subcategory] += amount
        
        # Create main category bar chart
        category_names = list(category_totals.keys())
        category_amounts = list(category_totals.values())
        
        # Sort by amount descending
        category_data = sorted(zip(category_names, category_amounts), key=lambda x: x[1], reverse=True)
        sorted_categories, sorted_amounts = zip(*category_data) if category_data else ([], [])
        
        # Create category bar chart
        category_fig = px.bar(
            x=list(sorted_categories),
            y=list(sorted_amounts),
            title="Spending by Category",
            labels={'x': 'Category', 'y': f'Total Amount ({self.currency_symbol})'},
            color=list(sorted_amounts),
            color_continuous_scale='viridis'
        )
        
        category_fig.update_layout(
            title_font_size=18,
            showlegend=False,
            height=400,
            template='plotly_white'
        )
        
        # Format category labels
        category_fig.update_xaxes(
            tickangle=45,
            title="Category"
        )
        category_fig.update_yaxes(
            title=f"Amount ({self.currency_symbol})",
            tickformat=f'{self.currency_symbol},.0f'
        )
        
        # Create subcategory charts for each category
        subcategory_charts = []
        
        for category in sorted_categories[:8]:  # Show top 8 categories to avoid overcrowding
            if category in subcategory_totals and len(subcategory_totals[category]) > 1:
                subcat_data = subcategory_totals[category]
                
                # Sort subcategories by amount
                subcat_items = sorted(subcat_data.items(), key=lambda x: x[1], reverse=True)
                subcat_names, subcat_amounts = zip(*subcat_items) if subcat_items else ([], [])
                
                # Create subcategory chart
                subcat_fig = px.bar(
                    x=list(subcat_names),
                    y=list(subcat_amounts),
                    title=f"{category.replace('_', ' ').title()} - Subcategories",
                    labels={'x': 'Subcategory', 'y': f'Amount ({self.currency_symbol})'},
                    color=list(subcat_amounts),
                    color_continuous_scale='plasma'
                )
                
                subcat_fig.update_layout(
                    title_font_size=14,
                    showlegend=False,
                    height=300,
                    template='plotly_white'
                )
                
                subcat_fig.update_xaxes(
                    tickangle=45,
                    title=""
                )
                subcat_fig.update_yaxes(
                    title=self.currency_symbol,
                    tickformat=f'{self.currency_symbol},.0f'
                )
                
                subcategory_charts.append(
                    dbc.Col([
                        dbc.Card([
                            dbc.CardBody([
                                dcc.Graph(figure=subcat_fig)
                            ])
                        ])
                    ], width=6, className="mb-3")
                )
        
        # Create layout
        return html.Div([
            # Overall category spending
            dbc.Row([
                dbc.Col([
                    dbc.Card([
                        dbc.CardHeader("💰 Total Spending by Category"),
                        dbc.CardBody([
                            dcc.Graph(figure=category_fig)
                        ])
                    ])
                ], width=12)
            ], className="mb-4"),
            
            # Subcategory breakdowns
            dbc.Row([
                dbc.Col([
                    html.H4("📊 Subcategory Breakdown", className="mb-3"),
                    html.P("Detailed spending within each category", className="text-muted mb-4")
                ], width=12)
            ]),
            
            # Subcategory charts in a grid
            dbc.Row(subcategory_charts) if subcategory_charts else dbc.Alert(
                "📊 Subcategory data will appear here when you have transactions with multiple subcategories per category.",
                color="info"
            )
        ])
    
    def create_review_other_tab(self, filtered_data):
        """Create the enhanced review 'other' transactions tab with duplicate grouping."""
        # Filter for 'other' category transactions
        other_transactions = [t for t in filtered_data if t.get('category', '').lower() == 'other']
        
        if not other_transactions:
            return dbc.Alert("🎉 Great! No transactions are categorized as 'Other'. Your categorization system is working well!", color="success")
        
        # Group transactions by description to handle duplicates efficiently
        from collections import defaultdict
        desc_groups = defaultdict(list)
        for txn in other_transactions:
            desc = txn['description'].strip()
            desc_groups[desc].append(txn)
        
        # Get available categories and subcategories from config
        categories = config.get_categories()
        
        # Create category options for dropdown
        category_options = []
        subcategory_lookup = {}  # Maps category -> list of subcategories
        
        for category, category_data in categories.items():
            if category.lower() == 'other':  # Skip 'other' category
                continue
                
            category_label = category.replace('_', ' ').title()
            category_options.append({'label': category_label, 'value': category})
            
            # Store subcategories for this category
            if 'subcategories' in category_data:
                subcategory_lookup[category] = []
                for subcategory in category_data['subcategories'].keys():
                    subcategory_label = subcategory.replace('_', ' ').title()
                    subcategory_lookup[category].append({
                        'label': subcategory_label, 
                        'value': subcategory
                    })
                # Add "Create New" option for subcategories
                subcategory_lookup[category].append({
                    'label': '➕ Create New Subcategory...', 
                    'value': 'CREATE_NEW_SUBCATEGORY'
                })
        
        # Add "Create New Category" option
        category_options.append({
            'label': '➕ Create New Category...', 
            'value': 'CREATE_NEW_CATEGORY'
        })
        
        # Sort category options
        category_options = sorted([opt for opt in category_options if not opt['value'].startswith('CREATE')], key=lambda x: x['label']) + \
                          [opt for opt in category_options if opt['value'].startswith('CREATE')]
        
        # Check for existing similar categorizations in the dataset
        def get_suggested_categorization(description):
            """Check if similar description has been categorized before."""
            desc_lower = description.lower().strip()
            
            # First, check all transactions for identical descriptions
            for txn in filtered_data:
                if (txn.get('category', '').lower() != 'other' and 
                    txn['description'].lower().strip() == desc_lower):
                    return txn.get('category'), txn.get('subcategory')
            
            # Smart keyword-based categorization for common patterns
            smart_suggestions = self._get_smart_category_suggestions(desc_lower)
            if smart_suggestions:
                return smart_suggestions
            
            # Check for partial matches (keywords)
            for txn in filtered_data:
                if (txn.get('category', '').lower() != 'other'):
                    txn_desc = txn['description'].lower().strip()
                    # Simple keyword matching
                    if (len(desc_lower) > 5 and desc_lower in txn_desc) or \
                       (len(txn_desc) > 5 and txn_desc in desc_lower):
                        return txn.get('category'), txn.get('subcategory')
            
            return None, None
        
        # Create grouped transaction rows for review
        transaction_rows = []
        group_id = 0
        
        # Sort groups by frequency (most common duplicates first)
        sorted_groups = sorted(desc_groups.items(), key=lambda x: len(x[1]), reverse=True)
        
        for description, txn_group in sorted_groups[:15]:  # Show top 15 groups
            group_id += 1
            count = len(txn_group)
            sample_txn = txn_group[0]  # Use first transaction as representative
            
            # Calculate total amount for this group
            total_amount = sum(t['amount'] for t in txn_group)
            amount_display = f"{self.currency_symbol}{total_amount:.2f}"
            amount_color = "text-danger" if total_amount < 0 else "text-success"
            
            # Get suggested categorization
            suggested_cat, suggested_subcat = get_suggested_categorization(description)
            
            # Create display for transaction count and dates
            dates = [t['date'] for t in txn_group]
            if len(dates) > 1:
                date_range = f"{min(dates)} to {max(dates)}"
                count_display = f"{count} transactions"
            else:
                date_range = dates[0]
                count_display = "1 transaction"
            
            # Description display (truncated)
            desc_display = description[:40] + "..." if len(description) > 40 else description
            
            # Current categorization
            current_cat = sample_txn.get('category', 'other').title()
            current_subcat = sample_txn.get('subcategory', 'unknown').title()
            
            # Suggestion display
            if suggested_cat:
                suggestion_display = f"💡 {suggested_cat.replace('_', ' ').title()} → {suggested_subcat.replace('_', ' ').title() if suggested_subcat else 'Unknown'}"
                suggestion_color = "text-success"
            else:
                suggestion_display = "💭 No similar transactions found"
                suggestion_color = "text-muted"
            
            # Create row with grouping
            row = html.Tr([
                # Description and count
                html.Td([
                    html.Div([
                        html.Strong(desc_display, title=description),
                        html.Br(),
                        html.Small(count_display, className="text-muted"),
                        html.Br(),
                        html.Small(date_range, className="text-muted")
                    ])
                ], style={'width': '30%'}),
                
                # Total amount
                html.Td([
                    html.Strong(amount_display, className=amount_color),
                    html.Br(),
                    html.Small(f"({count} × avg {total_amount/count:.2f})" if count > 1 else "", className="text-muted")
                ], style={'width': '12%'}),
                
                # Current categorization
                html.Td([
                    html.Div(f"{current_cat} → {current_subcat}", className="text-muted"),
                    html.Div(suggestion_display, className=suggestion_color, style={'font-size': '0.85em'})
                ], style={'width': '18%'}),
                
                # Category selection
                html.Td([
                    dcc.Dropdown(
                        id={'type': 'group-category-dropdown', 'index': group_id},
                        options=category_options,
                        value=suggested_cat,  # Pre-fill if suggestion available
                        placeholder="Select category...",
                        style={'minWidth': '140px', 'fontSize': '0.9em'}
                    )
                ], style={'width': '15%'}),
                
                # Subcategory selection
                html.Td([
                    dcc.Dropdown(
                        id={'type': 'group-subcategory-dropdown', 'index': group_id},
                        options=subcategory_lookup.get(suggested_cat, []) if suggested_cat else [],
                        value=suggested_subcat if suggested_cat and suggested_subcat else None,
                        placeholder="Select subcategory...",
                        disabled=not suggested_cat,
                        style={'minWidth': '140px', 'fontSize': '0.9em'}
                    )
                ], style={'width': '15%'}),
                
                # Apply button
                html.Td([
                    dbc.Button(
                        f"Apply to {count}", 
                        id={'type': 'group-apply-btn', 'index': group_id}, 
                        size="sm", 
                        color="primary" if count > 1 else "success",
                        disabled=False,  # Always enable - let user decide
                        title=f"Apply categorization to all {count} transactions with this description"
                    )
                ], style={'width': '10%'}),
                
                # Hidden data for JavaScript access
                html.Td([
                    html.Div(
                        json.dumps({
                            'description': description,
                            'transaction_ids': [t.get('id', i) for i, t in enumerate(txn_group)],
                            'count': count
                        }),
                        id=f'group-data-{group_id}',
                        style={'display': 'none'}
                    )
                ], style={'display': 'none'})
            ])
            
            transaction_rows.append(row)
        
        # Enhanced table with grouping
        review_table = dbc.Table([
            html.Thead([
                html.Tr([
                    html.Th("Description & Count", style={'width': '30%'}),
                    html.Th("Total Amount", style={'width': '12%'}),
                    html.Th("Current & Suggestions", style={'width': '18%'}),
                    html.Th("New Category", style={'width': '15%'}),
                    html.Th("New Subcategory", style={'width': '15%'}),
                    html.Th("Apply", style={'width': '10%'}),
                ])
            ], style={'background-color': '#f8f9fa'}),
            html.Tbody(transaction_rows)
        ], striped=True, bordered=True, hover=True, responsive=True, size="sm")
        
        # Store subcategory lookup in a hidden div for JavaScript access
        subcategory_data = html.Div(
            json.dumps(subcategory_lookup),
            id='subcategory-lookup-data',
            style={'display': 'none'}
        )
        
        # Summary statistics
        total_other_count = len(other_transactions)
        grouped_count = sum(len(group) for group in desc_groups.values())
        duplicate_descriptions = sum(1 for group in desc_groups.values() if len(group) > 1)
        
        return html.Div([
            dbc.Alert([
                html.H4("🔍 Smart Review - Grouped 'Other' Transactions", className="alert-heading"),
                html.P([
                    f"Found {total_other_count} transactions categorized as 'Other', grouped into {len(desc_groups)} unique descriptions. ",
                    f"{duplicate_descriptions} descriptions appear multiple times - fix once, apply to all!"
                ]),
                html.Hr(),
                html.P([
                    "💡 ", html.Strong("Smart Features:"), 
                    " • Transactions grouped by identical description", html.Br(),
                    " • 🔍 Suggestions based on similar transactions you've already categorized", html.Br(),
                    " • 🚀 Apply categorization to multiple transactions at once", html.Br(),
                    " • 📊 Most frequent duplicates shown first for maximum impact"
                ], className="mb-0")
            ], color="info"),
            
            subcategory_data,  # Hidden data for callbacks
            
            html.Div([
                review_table
            ], style={'overflow-x': 'auto'}),
            
            html.Div(id='review-feedback-messages', className='mt-3'),
            
            # Enhanced bulk actions
            html.Hr(),
            dbc.Row([
                dbc.Col([
                    dbc.Button(
                        "📝 Apply All Selected Changes", 
                        id='apply-all-grouped-btn', 
                        color="primary", 
                        disabled=True,
                        className="me-2"
                    ),
                    dbc.Button(
                        "🎯 Auto-Apply All Suggestions", 
                        id='auto-apply-suggestions-btn', 
                        color="success", 
                        outline=True,
                        className="me-2"
                    ),
                    dbc.Button(
                        "🔄 Retrain ML Model", 
                        id='retrain-model-btn', 
                        color="warning", 
                        outline=True
                    ),
                ]),
                dbc.Col([
                    html.Div(id='bulk-action-feedback')
                ], width='auto')
            ], justify='between', align='center'),
            
            # Show remaining ungrouped transactions
            html.Div([
                html.Hr(),
                html.H5(f"📋 Showing top {min(15, len(desc_groups))} description groups"),
                html.P([
                    f"Total impact: Fixing these groups will categorize {min(grouped_count, sum(len(group) for _, group in sorted_groups[:15]))} transactions. ",
                    f"Remaining: {max(0, len(desc_groups) - 15)} more description groups available."
                ], className="text-muted")
            ])
        ])
    
    def create_all_transactions_tab(self, filtered_data):
        """Create the all transactions tab."""
        transactions_table = self.create_transactions_table(filtered_data)
        
        return html.Div([
            dbc.Card([
                dbc.CardHeader(f"All Transactions ({len(filtered_data)} total)"),
                dbc.CardBody([
                    transactions_table
                ])
            ])
        ])
    
    def apply_recategorizations(self, table_data):
        """Apply user recategorizations and retrain the ML model."""
        try:
            from .user_feedback import UserFeedbackManager
            
            # Filter for rows with new categories
            corrections = []
            for row in table_data:
                if row.get('new_category'):
                    corrections.append({
                        'description': row.get('description', ''),
                        'original_category': row.get('current_category', 'other'),
                        'new_category': row.get('new_category', ''),
                        'date': row.get('date', ''),
                        'amount': row.get('amount', '')
                    })
            
            if not corrections:
                return dbc.Alert("No changes to apply.", color="warning")
            
            # Apply corrections using the feedback manager
            feedback_manager = UserFeedbackManager()
            
            # Save user feedback
            if not feedback_manager.save_user_corrections(corrections):
                return dbc.Alert("Error saving user corrections.", color="danger")
            
            # Apply corrections to dataset
            if not feedback_manager.apply_corrections_to_dataset(corrections):
                return dbc.Alert("Error applying corrections to dataset.", color="danger")
            
            # Retrain ML model
            training_results = feedback_manager.retrain_ml_model()
            
            if 'error' in training_results:
                return dbc.Alert(f"Error retraining model: {training_results['error']}", color="danger")
            
            # Success message with training stats
            accuracy = training_results.get('test_accuracy', 0)
            return dbc.Alert([
                html.H5("✅ Changes Applied Successfully!"),
                html.P(f"Updated {len(corrections)} transactions and retrained the ML model."),
                html.P(f"New model accuracy: {accuracy:.1%}"),
                html.Hr(),
                html.P([
                    "🔄 ",
                    dbc.Button("Refresh Dashboard", href="/", color="primary", size="sm"),
                    " to see the updated categorization."
                ], className="mb-0")
            ], color="success")
            
        except Exception as e:
            logger.error(f"Error in apply_recategorizations: {e}")
            return dbc.Alert(f"Error applying changes: {str(e)}", color="danger")
    
    def run(self, host='127.0.0.1', port=8050, debug=False):
        """Run the dashboard."""
        dashboard_config = config.get_dashboard_config()
        
        host = dashboard_config.get('host', host)
        port = dashboard_config.get('port', port) 
        debug = dashboard_config.get('debug', debug)
        
        logger.info(f"Starting dashboard at http://{host}:{port}")
        self.app.run(host=host, port=port, debug=debug)
    
    def _create_empty_chart(self, message):
        """Create empty chart with message."""
        fig = go.Figure()
        fig.add_annotation(
            text=message,
            xref="paper", yref="paper",
            x=0.5, y=0.5, xanchor='center', yanchor='middle',
            showarrow=False, font=dict(size=16)
        )
        fig.update_layout(
            title="Daily Transaction Waterfall",
            template='plotly_white',
            height=400
        )
        return fig

    # -------------------------------------------------------------------------
    # Recurring & Vendors tab
    # -------------------------------------------------------------------------

    def _detect_recurring_payments(self, filtered_data: List[Dict]) -> Dict[str, Any]:
        """
        Detect recurring payments by grouping on (description, amount).

        Returns dict with keys 'expenses' and 'income', each a list of dicts:
            vendor, amount, count, avg_interval_days, frequency_label,
            monthly_cost, annual_cost, last_date, first_date
        Only includes combos with 3+ occurrences.
        """
        # Group transactions by (description, rounded amount)
        combos: Dict[tuple, list] = {}
        for t in filtered_data:
            key = (t['description'], round(t['amount'], 2))
            combos.setdefault(key, []).append(t)

        results = {'expenses': [], 'income': []}

        for (desc, amount), txns in combos.items():
            if len(txns) < 3:
                continue

            # Sort by date and compute intervals
            sorted_txns = sorted(txns, key=lambda x: x['date'])
            intervals = []
            for i in range(1, len(sorted_txns)):
                d1 = sorted_txns[i - 1]['date']
                d2 = sorted_txns[i]['date']
                if isinstance(d1, str):
                    d1 = datetime.fromisoformat(d1)
                if isinstance(d2, str):
                    d2 = datetime.fromisoformat(d2)
                delta = (d2 - d1).days
                if delta > 0:
                    intervals.append(delta)

            avg_interval = sum(intervals) / len(intervals) if intervals else 0

            # Classify frequency
            if 25 <= avg_interval <= 35:
                frequency = 'Monthly'
                monthly_cost = abs(amount)
            elif 12 <= avg_interval <= 18:
                frequency = 'Bi-weekly'
                monthly_cost = abs(amount) * 2
            elif 5 <= avg_interval <= 9:
                frequency = 'Weekly'
                monthly_cost = abs(amount) * (30.44 / 7)
            else:
                frequency = 'Irregular'
                # Estimate monthly cost from total spend / months spanned
                first_date = sorted_txns[0]['date']
                last_date = sorted_txns[-1]['date']
                if isinstance(first_date, str):
                    first_date = datetime.fromisoformat(first_date)
                if isinstance(last_date, str):
                    last_date = datetime.fromisoformat(last_date)
                months_spanned = max((last_date - first_date).days / 30.44, 1)
                monthly_cost = abs(amount) * len(txns) / months_spanned

            annual_cost = monthly_cost * 12

            first_date = sorted_txns[0]['date']
            last_date = sorted_txns[-1]['date']
            if isinstance(first_date, str):
                first_date = datetime.fromisoformat(first_date)
            if isinstance(last_date, str):
                last_date = datetime.fromisoformat(last_date)

            entry = {
                'vendor': desc,
                'amount': amount,
                'count': len(txns),
                'avg_interval_days': round(avg_interval, 1),
                'frequency': frequency,
                'monthly_cost': round(monthly_cost, 2),
                'annual_cost': round(annual_cost, 2),
                'first_date': first_date,
                'last_date': last_date,
            }

            if amount < 0:
                results['expenses'].append(entry)
            else:
                results['income'].append(entry)

        # Sort each list by annual cost descending
        results['expenses'].sort(key=lambda x: x['annual_cost'], reverse=True)
        results['income'].sort(key=lambda x: x['annual_cost'], reverse=True)

        return results

    def _build_vendor_summary(self, filtered_data: List[Dict]) -> List[Dict]:
        """
        Build a summary of all vendors with 2+ transactions.

        Returns list of dicts sorted by count descending:
            vendor, count, total, average, first_date, last_date, is_income
        """
        vendors: Dict[str, list] = {}
        for t in filtered_data:
            desc = t['description']
            vendors.setdefault(desc, []).append(t)

        summary = []
        for desc, txns in vendors.items():
            if len(txns) < 2:
                continue

            amounts = [t['amount'] for t in txns]
            total = sum(amounts)

            dates = []
            for t in txns:
                d = t['date']
                if isinstance(d, str):
                    d = datetime.fromisoformat(d)
                dates.append(d)
            dates.sort()

            summary.append({
                'vendor': desc,
                'count': len(txns),
                'total': round(total, 2),
                'average': round(total / len(txns), 2),
                'first_date': dates[0],
                'last_date': dates[-1],
                'is_income': total > 0,
            })

        summary.sort(key=lambda x: x['count'], reverse=True)
        return summary

    def _create_recurring_payments_section(self, recurring_data: Dict[str, Any]) -> html.Div:
        """Render the recurring payments detection section."""
        sections = []

        # Summary cards
        total_monthly_expenses = sum(e['monthly_cost'] for e in recurring_data['expenses'])
        total_monthly_income = sum(e['monthly_cost'] for e in recurring_data['income'])
        total_annual_expenses = sum(e['annual_cost'] for e in recurring_data['expenses'])
        total_annual_income = sum(e['annual_cost'] for e in recurring_data['income'])

        summary_cards = dbc.Row([
            dbc.Col(dbc.Card(dbc.CardBody([
                html.H6("Monthly Recurring Expenses", className="text-muted mb-1"),
                html.H4(f"{self.currency_symbol}{total_monthly_expenses:,.2f}", className="text-danger fw-bold"),
                html.Small(f"{self.currency_symbol}{total_annual_expenses:,.2f} / year", className="text-muted"),
            ]), className="shadow-sm"), width=3),
            dbc.Col(dbc.Card(dbc.CardBody([
                html.H6("Monthly Recurring Income", className="text-muted mb-1"),
                html.H4(f"{self.currency_symbol}{total_monthly_income:,.2f}", className="text-success fw-bold"),
                html.Small(f"{self.currency_symbol}{total_annual_income:,.2f} / year", className="text-muted"),
            ]), className="shadow-sm"), width=3),
            dbc.Col(dbc.Card(dbc.CardBody([
                html.H6("Recurring Expense Items", className="text-muted mb-1"),
                html.H4(f"{len(recurring_data['expenses'])}", className="fw-bold"),
                html.Small("vendor + amount combos", className="text-muted"),
            ]), className="shadow-sm"), width=3),
            dbc.Col(dbc.Card(dbc.CardBody([
                html.H6("Recurring Income Items", className="text-muted mb-1"),
                html.H4(f"{len(recurring_data['income'])}", className="fw-bold"),
                html.Small("vendor + amount combos", className="text-muted"),
            ]), className="shadow-sm"), width=3),
        ], className="mb-4")
        sections.append(summary_cards)

        # Build tables for expenses and income
        for label, entries, color_class in [
            ("Recurring Expenses", recurring_data['expenses'], "text-danger"),
            ("Recurring Income", recurring_data['income'], "text-success"),
        ]:
            if not entries:
                continue

            sections.append(html.H5(label, className="mt-4 mb-3 fw-bold"))

            header = html.Thead(html.Tr([
                html.Th("Vendor"),
                html.Th("Amount", className="text-end"),
                html.Th("Frequency"),
                html.Th("Occurrences", className="text-center"),
                html.Th("Monthly Cost", className="text-end"),
                html.Th("Annual Cost", className="text-end"),
                html.Th("Last Paid"),
            ]))

            rows = []
            for e in entries:
                # Frequency badge color
                freq_colors = {
                    'Monthly': 'primary',
                    'Bi-weekly': 'info',
                    'Weekly': 'warning',
                    'Irregular': 'secondary',
                }
                freq_badge = dbc.Badge(
                    e['frequency'],
                    color=freq_colors.get(e['frequency'], 'secondary'),
                    className="px-2 py-1"
                )

                rows.append(html.Tr([
                    html.Td(e['vendor']),
                    html.Td(
                        f"{self.currency_symbol}{abs(e['amount']):,.2f}",
                        className=f"{color_class} fw-bold text-end"
                    ),
                    html.Td(freq_badge),
                    html.Td(str(e['count']), className="text-center"),
                    html.Td(
                        f"{self.currency_symbol}{e['monthly_cost']:,.2f}",
                        className="text-end"
                    ),
                    html.Td(
                        f"{self.currency_symbol}{e['annual_cost']:,.2f}",
                        className="text-end fw-bold"
                    ),
                    html.Td(
                        e['last_date'].strftime('%d %b %Y'),
                        className="text-nowrap"
                    ),
                ]))

            table = dbc.Table(
                [header, html.Tbody(rows)],
                striped=True, bordered=True, hover=True, size="sm",
                className="mb-4"
            )
            sections.append(table)

        if not recurring_data['expenses'] and not recurring_data['income']:
            sections.append(html.P(
                "No recurring payments detected (need 3+ occurrences of same vendor + amount).",
                className="text-muted"
            ))

        return html.Div(sections)

    def _create_vendor_summary_section(self, vendor_data: List[Dict]) -> html.Div:
        """Render the top vendors summary table."""
        if not vendor_data:
            return html.P("No vendors with 2+ transactions found.", className="text-muted")

        header = html.Thead(html.Tr([
            html.Th("#", className="text-center"),
            html.Th("Vendor"),
            html.Th("Transactions", className="text-center"),
            html.Th("Total", className="text-end"),
            html.Th("Average", className="text-end"),
            html.Th("First Seen"),
            html.Th("Last Seen"),
        ]))

        rows = []
        for rank, v in enumerate(vendor_data, 1):
            color_class = "text-success" if v['is_income'] else "text-danger"

            rows.append(html.Tr([
                html.Td(str(rank), className="text-center text-muted"),
                html.Td(v['vendor'], className="fw-bold"),
                html.Td(str(v['count']), className="text-center"),
                html.Td(
                    f"{self.currency_symbol}{abs(v['total']):,.2f}",
                    className=f"{color_class} fw-bold text-end"
                ),
                html.Td(
                    f"{self.currency_symbol}{abs(v['average']):,.2f}",
                    className=f"{color_class} text-end"
                ),
                html.Td(
                    v['first_date'].strftime('%d %b %Y'),
                    className="text-nowrap"
                ),
                html.Td(
                    v['last_date'].strftime('%d %b %Y'),
                    className="text-nowrap"
                ),
            ]))

        table = dbc.Table(
            [header, html.Tbody(rows)],
            striped=True, bordered=True, hover=True, size="sm"
        )

        return html.Div([
            html.Div(
                table,
                style={"maxHeight": "600px", "overflowY": "auto"}
            )
        ])

    def create_recurring_vendors_tab(self, filtered_data: List[Dict]) -> html.Div:
        """Create the Recurring & Vendors tab content."""
        if not filtered_data:
            return html.Div(html.P("No transaction data available."))

        # Compute data
        recurring_data = self._detect_recurring_payments(filtered_data)
        vendor_data = self._build_vendor_summary(filtered_data)

        # Build layout
        return html.Div([
            # Section 1: Recurring Payments
            dbc.Card([
                dbc.CardHeader(html.H5(
                    "Recurring Payments",
                    className="mb-0 fw-bold"
                )),
                dbc.CardBody(
                    self._create_recurring_payments_section(recurring_data)
                ),
            ], className="shadow-sm mb-4"),

            # Section 2: Top Vendors
            dbc.Card([
                dbc.CardHeader(html.H5(
                    [
                        "Top Vendors",
                        dbc.Badge(
                            f"{len(vendor_data)} vendors",
                            color="secondary",
                            className="ms-2"
                        ),
                    ],
                    className="mb-0 fw-bold"
                )),
                dbc.CardBody(
                    self._create_vendor_summary_section(vendor_data)
                ),
            ], className="shadow-sm mb-4"),
        ])


# Note: Dashboard is now instantiated in scripts/run_dashboard.py with
# the force_reprocess flag. No global instance is created on import.