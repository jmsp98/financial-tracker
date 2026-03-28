"""
Interactive Dash dashboard for financial data visualization.
"""

try:
    import dash
    from dash import dcc, html, Input, Output, callback, State
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
    
    def __init__(self):
        if not HAS_DASH:
            raise ImportError("Dash dependencies not found. Install with: pip install dash plotly dash-bootstrap-components")
        
        self.app = dash.Dash(
            __name__,
            external_stylesheets=[dbc.themes.BOOTSTRAP],
            suppress_callback_exceptions=True
        )
        
        self.categorized_data = []
        self.load_data()
        self.setup_layout()
        self.setup_callbacks()
    
    def load_data(self):
        """Load categorized transaction data."""
        categorized_path = config.get('data.categorized', './data/categorized')
        
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
                    
                # Convert date strings back to datetime objects
                for transaction in data:
                    if isinstance(transaction, dict) and 'date' in transaction:
                        transaction['date'] = datetime.fromisoformat(transaction['date'])
                
                self.categorized_data = data
                logger.info(f"Loaded {len(self.categorized_data)} transactions from {os.path.basename(file_path)}")
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
            
            # Summary cards
            dbc.Row([
                dbc.Col([
                    dbc.Card([
                        dbc.CardBody([
                            html.H4("Total Income", className="card-title"),
                            html.H2(id="total-income", className="text-success")
                        ])
                    ])
                ], width=3),
                dbc.Col([
                    dbc.Card([
                        dbc.CardBody([
                            html.H4("Total Expenses", className="card-title"),
                            html.H2(id="total-expenses", className="text-danger")
                        ])
                    ])
                ], width=3),
                dbc.Col([
                    dbc.Card([
                        dbc.CardBody([
                            html.H4("Net Income", className="card-title"),
                            html.H2(id="net-income")
                        ])
                    ])
                ], width=3),
                dbc.Col([
                    dbc.Card([
                        dbc.CardBody([
                            html.H4("Transactions", className="card-title"),
                            html.H2(id="total-transactions")
                        ])
                    ])
                ], width=3),
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
                dbc.Tab(label="🔍 Review 'Other'", tab_id="review-other"),
                dbc.Tab(label="📋 All Transactions", tab_id="all-transactions"),
            ], id="main-tabs", active_tab="analytics"),
            
            html.Div(id="tab-content", className="mt-4")
            
        ], fluid=True)
    
    def setup_callbacks(self):
        """Setup dashboard callbacks."""
        
        # Callback for updating summary cards
        @self.app.callback(
            [Output('total-income', 'children'),
             Output('total-expenses', 'children'), 
             Output('net-income', 'children'),
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
            
            # Calculate summary statistics
            total_income = sum(t['amount'] for t in filtered_data if t['amount'] > 0)
            total_expenses = sum(abs(t['amount']) for t in filtered_data if t['amount'] < 0)
            net_income = total_income - total_expenses
            
            # Format summary values
            income_str = f"${total_income:,.2f}"
            expenses_str = f"${total_expenses:,.2f}"
            net_str = f"${net_income:,.2f}"
            net_color = "text-success" if net_income >= 0 else "text-danger"
            
            return (
                income_str,
                expenses_str, 
                html.Span(net_str, className=net_color),
                f"{len(filtered_data):,}",
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
            elif active_tab == "review-other":
                return self.create_review_other_tab(filtered_data)
            elif active_tab == "all-transactions":
                return self.create_all_transactions_tab(filtered_data)
            
            return html.Div("Select a tab")
        
        # Callbacks for Review Other tab hierarchical categorization
        # We'll add these dynamically since we don't know how many transactions there will be
        self.setup_review_callbacks()
    
    def setup_review_callbacks(self):
        """Setup callbacks for the enhanced Review Other functionality."""
        # Note: These callbacks will be set up dynamically when the Review Other tab is loaded
        # because the number of transactions (and thus dropdown IDs) varies
        pass
    
    def handle_category_creation(self, new_category: str, new_subcategory: str = None) -> bool:
        """
        Handle creation of new categories and subcategories in config.
        
        Args:
            new_category: Name of new category to create
            new_subcategory: Optional subcategory name
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # This would need to update the config.yaml file
            # For now, we'll log the request
            logger.info(f"Request to create new category: {new_category}")
            if new_subcategory:
                logger.info(f"  with subcategory: {new_subcategory}")
            
            # TODO: Implement config.yaml updating logic
            # This would involve:
            # 1. Reading current config.yaml
            # 2. Adding new category/subcategory structure  
            # 3. Writing back to config.yaml
            # 4. Reloading categorizer with new config
            
            return True
        except Exception as e:
            logger.error(f"Failed to create category {new_category}: {e}")
            return False
    
    def apply_categorization_correction(self, transaction_data: dict, new_category: str, new_subcategory: str) -> bool:
        """
        Apply categorization correction to a transaction.
        
        Args:
            transaction_data: Transaction data
            new_category: New category to assign
            new_subcategory: New subcategory to assign
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # This would update the categorized transactions file
            # and provide feedback to the ML model
            logger.info(f"Correcting transaction: {transaction_data.get('description', 'Unknown')}")
            logger.info(f"  From: {transaction_data.get('category', 'other')} -> {transaction_data.get('subcategory', 'unknown')}")
            logger.info(f"  To: {new_category} -> {new_subcategory}")
            
            # TODO: Implement transaction correction logic
            # This would involve:
            # 1. Updating the categorized transactions file
            # 2. Saving user feedback for ML retraining
            # 3. Optionally updating the ML model
            
            return True
        except Exception as e:
            logger.error(f"Failed to apply correction: {e}")
            return False
    
    def create_monthly_trends_chart(self, monthly_data: Dict) -> go.Figure:
        """Create monthly income vs expenses chart."""
        months = sorted(monthly_data.keys())
        income_values = [monthly_data[month]['total_income'] for month in months]
        expense_values = [monthly_data[month]['total_expenses'] for month in months]
        
        fig = go.Figure()
        
        fig.add_trace(go.Scatter(
            x=months,
            y=income_values,
            mode='lines+markers',
            name='Income',
            line=dict(color='green'),
            marker=dict(size=8)
        ))
        
        fig.add_trace(go.Scatter(
            x=months,
            y=expense_values,
            mode='lines+markers',
            name='Expenses', 
            line=dict(color='red'),
            marker=dict(size=8)
        ))
        
        fig.update_layout(
            title="Monthly Income vs Expenses",
            xaxis_title="Month",
            yaxis_title="Amount ($)",
            hovermode='x unified',
            template='plotly_white'
        )
        
        return fig
    
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
            yaxis_title="Amount ($)",
            hovermode='x unified',
            template='plotly_white'
        )
        
        return fig
    
    def create_transactions_table(self, transactions: List[Dict]) -> html.Table:
        """Create transactions table."""
        if not transactions:
            return html.P("No transactions to display")
        
        # Sort by date (most recent first)
        sorted_transactions = sorted(transactions, key=lambda x: x['date'], reverse=True)
        
        header = html.Thead([
            html.Tr([
                html.Th("Date"),
                html.Th("Description"),
                html.Th("Category"),
                html.Th("Amount", className="text-end")
            ])
        ])
        
        rows = []
        for transaction in sorted_transactions:
            amount = transaction['amount']
            amount_class = "text-success" if amount > 0 else "text-danger"
            amount_str = f"${abs(amount):,.2f}"
            
            row = html.Tr([
                html.Td(transaction['date'].strftime('%Y-%m-%d')),
                html.Td(transaction['description'][:50] + "..." if len(transaction['description']) > 50 else transaction['description']),
                html.Td(transaction['category'].title()),
                html.Td(amount_str, className=f"{amount_class} text-end")
            ])
            rows.append(row)
        
        body = html.Tbody(rows)
        
        return dbc.Table([header, body], striped=True, bordered=True, hover=True, size="sm")
    
    def create_analytics_tab(self, filtered_data):
        """Create the analytics tab content."""
        # Monthly trends chart
        monthly_data = analyzer.calculate_monthly_summary(filtered_data)
        monthly_trend_fig = self.create_monthly_trends_chart(monthly_data)
        
        # Category pie chart
        category_pie_fig = self.create_category_pie_chart(filtered_data)
        
        # Category trends chart
        category_trends_fig = self.create_category_trends_chart(filtered_data)
        
        # Subcategory pie chart 
        subcategory_pie_fig = self.create_subcategory_pie_chart(filtered_data)
        
        # Transactions table
        transactions_table = self.create_transactions_table(filtered_data[:50])  # Show 50 most recent
        
        return html.Div([
            # Charts
            dbc.Row([
                dbc.Col([
                    dbc.Card([
                        dbc.CardHeader("Monthly Income vs Expenses"),
                        dbc.CardBody([
                            dcc.Graph(figure=monthly_trend_fig)
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
            
            # Transaction table
            dbc.Row([
                dbc.Col([
                    dbc.Card([
                        dbc.CardHeader("Recent Transactions"),
                        dbc.CardBody([
                            transactions_table
                        ])
                    ])
                ], width=12)
            ])
        ])
    
    def create_review_other_tab(self, filtered_data):
        """Create the enhanced review 'other' transactions tab with hierarchical categorization."""
        # Filter for 'other' category transactions
        other_transactions = [t for t in filtered_data if t.get('category', '').lower() == 'other']
        
        if not other_transactions:
            return dbc.Alert("🎉 Great! No transactions are categorized as 'Other'. Your categorization system is working well!", color="success")
        
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
        
        # Create transaction rows for review
        transaction_rows = []
        for i, transaction in enumerate(other_transactions[:20]):
            date_str = transaction['date'].strftime('%Y-%m-%d') if hasattr(transaction['date'], 'strftime') else str(transaction['date'])
            desc = transaction['description'][:50] + "..." if len(transaction['description']) > 50 else transaction['description']
            amount = f"${transaction['amount']:.2f}"
            amount_color = "text-danger" if transaction['amount'] < 0 else "text-success"
            
            # Current categorization info
            current_cat = transaction.get('category', 'other').title()
            current_subcat = transaction.get('subcategory', 'unknown').title()
            current_info = f"{current_cat} → {current_subcat}"
            
            row = html.Tr([
                html.Td(date_str, style={'font-size': '0.9em'}),
                html.Td(desc, title=transaction['description'], style={'font-size': '0.9em'}),
                html.Td(amount, className=amount_color, style={'font-weight': 'bold'}),
                html.Td(current_info, style={'font-size': '0.8em', 'color': 'gray'}),
                html.Td([
                    dcc.Dropdown(
                        id=f'category-dropdown-{i}',
                        options=category_options,
                        placeholder="Select category...",
                        style={'minWidth': '160px', 'fontSize': '0.9em'}
                    )
                ]),
                html.Td([
                    dcc.Dropdown(
                        id=f'subcategory-dropdown-{i}',
                        options=[],  # Will be populated based on category selection
                        placeholder="Select subcategory...",
                        disabled=True,
                        style={'minWidth': '160px', 'fontSize': '0.9em'}
                    )
                ]),
                html.Td([
                    dbc.Button("✓", id=f'apply-btn-{i}', size="sm", color="success", disabled=True)
                ]),
                
                # Hidden inputs for new category/subcategory creation
                html.Td([
                    dbc.Input(
                        id=f'new-category-input-{i}',
                        placeholder="New category name...",
                        style={'display': 'none', 'fontSize': '0.9em'}
                    )
                ], style={'display': 'none'}),
                html.Td([
                    dbc.Input(
                        id=f'new-subcategory-input-{i}',
                        placeholder="New subcategory name...",
                        style={'display': 'none', 'fontSize': '0.9em'}
                    )
                ], style={'display': 'none'}),
            ])
            transaction_rows.append(row)
        
        # Create enhanced table
        review_table = dbc.Table([
            html.Thead([
                html.Tr([
                    html.Th("Date", style={'width': '10%'}),
                    html.Th("Description", style={'width': '25%'}),
                    html.Th("Amount", style={'width': '10%'}),
                    html.Th("Current", style={'width': '15%'}),
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
        
        return html.Div([
            dbc.Alert([
                html.H4("🔍 Review 'Other' Transactions", className="alert-heading"),
                html.P([
                    f"Found {len(other_transactions)} transactions categorized as 'Other'. ",
                    "Select both category and subcategory for each transaction, or create new ones as needed."
                ]),
                html.Hr(),
                html.P([
                    "💡 ", html.Strong("Tip:"), " You can create new categories and subcategories by selecting the '➕ Create New...' options. ",
                    "This helps improve future categorization accuracy."
                ], className="mb-0")
            ], color="info"),
            
            subcategory_data,  # Hidden data for callbacks
            
            html.Div([
                review_table
            ], style={'overflow-x': 'auto'}),
            
            html.Div(id='review-feedback-messages', className='mt-3'),
            
            # Bulk actions
            html.Hr(),
            dbc.Row([
                dbc.Col([
                    dbc.Button(
                        "📝 Apply All Selected Changes", 
                        id='apply-all-btn', 
                        color="primary", 
                        disabled=True,
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
            ], justify='between', align='center')
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


# Global dashboard instance
dashboard = FinancialDashboard() if HAS_DASH else None