"""
Interactive Dash dashboard for financial data visualization.
"""

try:
    import dash
    from dash import dcc, html, Input, Output, callback, State, clientside_callback, ALL
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
                dbc.Tab(label="📂 Categories", tab_id="categories"),
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
            elif active_tab == "categories":
                return self.create_categories_tab(filtered_data)
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
        
        # Clientside callback to set up dropdown dependencies
        self.app.clientside_callback(
            """
            function(n_intervals, subcategory_data_json) {
                if (!subcategory_data_json || n_intervals === 0) return "";
                
                const subcategory_data = JSON.parse(subcategory_data_json);
                
                // Set up dropdown dependencies
                setTimeout(function() {
                    // Find all category dropdowns
                    const categoryDropdowns = document.querySelectorAll('[id*="group-category-dropdown-"]');
                    
                    categoryDropdowns.forEach(function(categoryDropdown) {
                        // Extract group ID from the dropdown ID
                        const groupId = categoryDropdown.id.split('-').pop();
                        const subcategoryDropdown = document.getElementById('group-subcategory-dropdown-' + groupId);
                        
                        if (subcategoryDropdown && !categoryDropdown.hasAttribute('data-listener-added')) {
                            // Mark that we've added the listener to avoid duplicates
                            categoryDropdown.setAttribute('data-listener-added', 'true');
                            
                            // Add change event listener to category dropdown
                            categoryDropdown.addEventListener('change', function() {
                                const selectedCategory = this.value;
                                
                                // Clear subcategory dropdown
                                subcategoryDropdown.innerHTML = '<option value="">Select subcategory...</option>';
                                
                                if (selectedCategory && selectedCategory !== 'CREATE_NEW_CATEGORY' && subcategory_data[selectedCategory]) {
                                    // Enable subcategory dropdown
                                    subcategoryDropdown.disabled = false;
                                    
                                    // Populate subcategory options
                                    subcategory_data[selectedCategory].forEach(function(subcat) {
                                        const option = document.createElement('option');
                                        option.value = subcat.value;
                                        option.textContent = subcat.label;
                                        subcategoryDropdown.appendChild(option);
                                    });
                                } else {
                                    // Disable subcategory dropdown
                                    subcategoryDropdown.disabled = true;
                                }
                            });
                            
                            // Trigger change event if category is already selected
                            if (categoryDropdown.value) {
                                categoryDropdown.dispatchEvent(new Event('change'));
                            }
                        }
                    });
                }, 100);
                
                return "";
            }
            """,
            Output('dropdown-setup-trigger', 'children'),
            [Input('dropdown-setup-interval', 'n_intervals'),
             Input('subcategory-lookup-data', 'children')]
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
        
        # Ensure dates are datetime objects and sort by date (most recent first)
        for txn in transactions:
            if isinstance(txn['date'], str):
                try:
                    txn['date'] = datetime.fromisoformat(txn['date'])
                except:
                    # Fallback for any problematic date strings
                    txn['date'] = datetime.strptime(txn['date'], '%Y-%m-%d %H:%M:%S')
        
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
                html.Td(transaction['date'].strftime('%d %b %Y')),  # More readable: "04 Mar 2026"
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
            labels={'x': 'Category', 'y': 'Total Amount (£)'},
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
            title="Amount (£)",
            tickformat='£,.0f'
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
                    labels={'x': 'Subcategory', 'y': 'Amount (£)'},
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
                    title="£",
                    tickformat='£,.0f'
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
            
            # Check all transactions for similar descriptions
            for txn in filtered_data:
                if (txn.get('category', '').lower() != 'other' and 
                    txn['description'].lower().strip() == desc_lower):
                    return txn.get('category'), txn.get('subcategory')
            
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
            amount_display = f"${total_amount:.2f}"
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
                        id=f'group-category-dropdown-{group_id}',
                        options=category_options,
                        value=suggested_cat,  # Pre-fill if suggestion available
                        placeholder="Select category...",
                        style={'minWidth': '140px', 'fontSize': '0.9em'}
                    )
                ], style={'width': '15%'}),
                
                # Subcategory selection
                html.Td([
                    dcc.Dropdown(
                        id=f'group-subcategory-dropdown-{group_id}',
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
                        id=f'group-apply-btn-{group_id}', 
                        size="sm", 
                        color="primary" if count > 1 else "success",
                        disabled=not (suggested_cat),  # Enable if suggestion available
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


# Global dashboard instance
dashboard = FinancialDashboard() if HAS_DASH else None