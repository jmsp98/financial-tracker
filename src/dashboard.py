"""
Interactive Dash dashboard for financial data visualization.
"""

try:
    import dash
    from dash import dcc, html, Input, Output, callback
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
            
            # Charts
            dbc.Row([
                dbc.Col([
                    dbc.Card([
                        dbc.CardHeader("Monthly Income vs Expenses"),
                        dbc.CardBody([
                            dcc.Graph(id="monthly-trend-chart")
                        ])
                    ])
                ], width=6),
                dbc.Col([
                    dbc.Card([
                        dbc.CardHeader("Spending by Category"),
                        dbc.CardBody([
                            dcc.Graph(id="category-pie-chart")
                        ])
                    ])
                ], width=6),
            ], className="mb-4"),
            
            dbc.Row([
                dbc.Col([
                    dbc.Card([
                        dbc.CardHeader("Monthly Category Breakdown"),
                        dbc.CardBody([
                            dcc.Graph(id="category-trends-chart")
                        ])
                    ])
                ], width=12)
            ], className="mb-4"),
            
            # Transaction table
            dbc.Row([
                dbc.Col([
                    dbc.Card([
                        dbc.CardHeader("Recent Transactions"),
                        dbc.CardBody([
                            html.Div(id="transactions-table")
                        ])
                    ])
                ], width=12)
            ])
            
        ], fluid=True)
    
    def setup_callbacks(self):
        """Setup dashboard callbacks."""
        
        @self.app.callback(
            [Output('total-income', 'children'),
             Output('total-expenses', 'children'), 
             Output('net-income', 'children'),
             Output('total-transactions', 'children'),
             Output('monthly-trend-chart', 'figure'),
             Output('category-pie-chart', 'figure'),
             Output('category-trends-chart', 'figure'),
             Output('transactions-table', 'children')],
            [Input('date-range-picker', 'start_date'),
             Input('date-range-picker', 'end_date')]
        )
        def update_dashboard(start_date, end_date):
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
            
            # Monthly trends chart
            monthly_data = analyzer.calculate_monthly_summary(filtered_data)
            monthly_trend_fig = self.create_monthly_trends_chart(monthly_data)
            
            # Category pie chart
            category_pie_fig = self.create_category_pie_chart(filtered_data)
            
            # Category trends chart
            category_trends_fig = self.create_category_trends_chart(filtered_data)
            
            # Transactions table
            transactions_table = self.create_transactions_table(filtered_data[:50])  # Show 50 most recent
            
            return (
                income_str,
                expenses_str, 
                html.Span(net_str, className=net_color),
                f"{len(filtered_data):,}",
                monthly_trend_fig,
                category_pie_fig,
                category_trends_fig,
                transactions_table
            )
    
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