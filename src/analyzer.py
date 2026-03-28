"""
Financial analysis engine for processing categorized transactions.
"""

from typing import List, Dict, Any, Tuple, Optional
from datetime import datetime, timedelta
from collections import defaultdict
import calendar
import logging

logger = logging.getLogger(__name__)


class FinancialAnalyzer:
    """Analyze categorized financial transactions."""
    
    def __init__(self):
        pass
    
    def calculate_monthly_summary(self, categorized_transactions: List[Dict]) -> Dict[str, Any]:
        """
        Calculate monthly financial summary.
        
        Args:
            categorized_transactions: List of categorized transaction dicts
            
        Returns:
            Dictionary with monthly analysis
        """
        monthly_data = defaultdict(lambda: {
            'total_income': 0.0,
            'total_expenses': 0.0,
            'net_income': 0.0,
            'categories': defaultdict(float),
            'transaction_count': 0
        })
        
        for transaction in categorized_transactions:
            date = transaction['date']
            amount = transaction['amount']
            category = transaction['category']
            
            month_key = date.strftime('%Y-%m')
            monthly_data[month_key]['transaction_count'] += 1
            monthly_data[month_key]['categories'][category] += amount
            
            if amount > 0:
                monthly_data[month_key]['total_income'] += amount
            else:
                monthly_data[month_key]['total_expenses'] += abs(amount)
        
        # Calculate net income for each month
        for month_data in monthly_data.values():
            month_data['net_income'] = month_data['total_income'] - month_data['total_expenses']
            # Convert defaultdict to regular dict for JSON serialization
            month_data['categories'] = dict(month_data['categories'])
        
        return dict(monthly_data)
    
    def calculate_yearly_trends(self, categorized_transactions: List[Dict]) -> Dict[str, Any]:
        """
        Calculate yearly spending trends.
        
        Args:
            categorized_transactions: List of categorized transaction dicts
            
        Returns:
            Dictionary with yearly trend analysis
        """
        if not categorized_transactions:
            return {}
        
        # Group by year
        yearly_data = defaultdict(lambda: {
            'total_income': 0.0,
            'total_expenses': 0.0,
            'net_income': 0.0,
            'months': defaultdict(lambda: {'income': 0.0, 'expenses': 0.0}),
            'categories': defaultdict(float)
        })
        
        for transaction in categorized_transactions:
            date = transaction['date']
            amount = transaction['amount']
            category = transaction['category']
            
            year = date.year
            month = date.strftime('%Y-%m')
            
            yearly_data[year]['categories'][category] += amount
            
            if amount > 0:
                yearly_data[year]['total_income'] += amount
                yearly_data[year]['months'][month]['income'] += amount
            else:
                yearly_data[year]['total_expenses'] += abs(amount)
                yearly_data[year]['months'][month]['expenses'] += abs(amount)
        
        # Calculate net income and convert to regular dicts
        result = {}
        for year, data in yearly_data.items():
            data['net_income'] = data['total_income'] - data['total_expenses']
            data['categories'] = dict(data['categories'])
            data['months'] = dict(data['months'])
            result[str(year)] = data
        
        return result
    
    def analyze_spending_patterns(self, categorized_transactions: List[Dict]) -> Dict[str, Any]:
        """
        Analyze spending patterns and identify trends.
        
        Args:
            categorized_transactions: List of categorized transaction dicts
            
        Returns:
            Dictionary with pattern analysis
        """
        if not categorized_transactions:
            return {}
        
        # Get date range
        dates = [t['date'] for t in categorized_transactions]
        start_date = min(dates)
        end_date = max(dates)
        
        # Category analysis
        category_totals = defaultdict(float)
        category_counts = defaultdict(int)
        category_avg_amounts = {}
        
        for transaction in categorized_transactions:
            category = transaction['category']
            amount = abs(transaction['amount'])  # Use absolute value for analysis
            
            category_totals[category] += amount
            category_counts[category] += 1
        
        # Calculate averages
        for category in category_totals:
            category_avg_amounts[category] = category_totals[category] / category_counts[category]
        
        # Find top categories by spending
        sorted_categories = sorted(category_totals.items(), key=lambda x: x[1], reverse=True)
        top_expense_categories = [(cat, amount) for cat, amount in sorted_categories if cat != 'income'][:5]
        
        # Monthly spending trend
        monthly_spending = defaultdict(float)
        for transaction in categorized_transactions:
            if transaction['amount'] < 0:  # Only expenses
                month = transaction['date'].strftime('%Y-%m')
                monthly_spending[month] += abs(transaction['amount'])
        
        # Calculate average monthly spending
        avg_monthly_spending = sum(monthly_spending.values()) / len(monthly_spending) if monthly_spending else 0
        
        return {
            'date_range': {
                'start': start_date.strftime('%Y-%m-%d'),
                'end': end_date.strftime('%Y-%m-%d'),
                'total_days': (end_date - start_date).days
            },
            'category_analysis': {
                'total_by_category': dict(category_totals),
                'average_amount_by_category': category_avg_amounts,
                'transaction_count_by_category': dict(category_counts),
                'top_expense_categories': top_expense_categories
            },
            'spending_trends': {
                'monthly_spending': dict(monthly_spending),
                'average_monthly_spending': avg_monthly_spending
            }
        }
    
    def generate_insights(self, analysis_results: Dict[str, Any]) -> List[str]:
        """
        Generate human-readable insights from analysis results.
        
        Args:
            analysis_results: Results from other analysis methods
            
        Returns:
            List of insight strings
        """
        insights = []
        
        # Monthly analysis insights
        if 'monthly' in analysis_results:
            monthly_data = analysis_results['monthly']
            months = list(monthly_data.keys())
            
            if len(months) >= 2:
                # Compare latest two months
                latest_month = max(months)
                previous_month = sorted(months)[-2] if len(months) > 1 else None
                
                if previous_month:
                    latest_expenses = monthly_data[latest_month]['total_expenses']
                    previous_expenses = monthly_data[previous_month]['total_expenses']
                    
                    if latest_expenses > previous_expenses * 1.1:
                        increase = ((latest_expenses - previous_expenses) / previous_expenses) * 100
                        insights.append(f"Spending increased by {increase:.1f}% from {previous_month} to {latest_month}")
                    elif latest_expenses < previous_expenses * 0.9:
                        decrease = ((previous_expenses - latest_expenses) / previous_expenses) * 100
                        insights.append(f"Spending decreased by {decrease:.1f}% from {previous_month} to {latest_month}")
        
        # Spending pattern insights
        if 'patterns' in analysis_results:
            patterns = analysis_results['patterns']
            
            # Top spending category
            if 'category_analysis' in patterns and patterns['category_analysis']['top_expense_categories']:
                top_category, top_amount = patterns['category_analysis']['top_expense_categories'][0]
                insights.append(f"Your highest expense category is {top_category.title()} (${top_amount:.2f} total)")
            
            # Monthly spending average
            if 'spending_trends' in patterns:
                avg_monthly = patterns['spending_trends']['average_monthly_spending']
                insights.append(f"Your average monthly spending is ${avg_monthly:.2f}")
        
        return insights
    
    def filter_transactions_by_date_range(
        self, 
        categorized_transactions: List[Dict],
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> List[Dict]:
        """
        Filter transactions by date range.
        
        Args:
            categorized_transactions: List of categorized transaction dicts
            start_date: Start date (inclusive)
            end_date: End date (inclusive)
            
        Returns:
            Filtered list of transactions
        """
        filtered = []
        
        for transaction in categorized_transactions:
            transaction_date = transaction['date']
            
            if start_date and transaction_date < start_date:
                continue
            if end_date and transaction_date > end_date:
                continue
            
            filtered.append(transaction)
        
        return filtered
    
    def get_category_comparison(
        self, 
        categorized_transactions: List[Dict],
        months_to_compare: int = 3
    ) -> Dict[str, Any]:
        """
        Compare spending across categories for recent months.
        
        Args:
            categorized_transactions: List of categorized transaction dicts
            months_to_compare: Number of recent months to analyze
            
        Returns:
            Dictionary with category comparison data
        """
        if not categorized_transactions:
            return {}
        
        # Get recent months
        all_months = set()
        for transaction in categorized_transactions:
            month = transaction['date'].strftime('%Y-%m')
            all_months.add(month)
        
        recent_months = sorted(all_months)[-months_to_compare:] if len(all_months) >= months_to_compare else sorted(all_months)
        
        # Calculate spending by category for each month
        comparison_data = {}
        
        for month in recent_months:
            comparison_data[month] = defaultdict(float)
            
            for transaction in categorized_transactions:
                if transaction['date'].strftime('%Y-%m') == month:
                    category = transaction['category']
                    amount = transaction['amount']
                    
                    if amount < 0:  # Only expenses
                        comparison_data[month][category] += abs(amount)
        
        # Convert to regular dicts
        for month in comparison_data:
            comparison_data[month] = dict(comparison_data[month])
        
        return comparison_data


# Global analyzer instance
analyzer = FinancialAnalyzer()