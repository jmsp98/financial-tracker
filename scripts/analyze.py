"""
Analysis script - Generate insights from categorized transaction data.
"""

import os
import sys
import json
import logging
from datetime import datetime
from typing import List, Dict

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from src.analyzer import analyzer

logger = logging.getLogger(__name__)


def load_categorized_data(file_path: str) -> List[Dict]:
    """Load categorized transactions from JSON file."""
    try:
        with open(file_path, 'r') as f:
            data = json.load(f)
        
        # Convert date strings back to datetime objects
        for transaction in data:
            transaction['date'] = datetime.fromisoformat(transaction['date'])
        
        return data
        
    except Exception as e:
        logger.error(f"Error loading data from {file_path}: {e}")
        return []


def main(input_dir: str) -> bool:
    """
    Main analysis function.
    
    Args:
        input_dir: Directory containing categorized transaction data
        
    Returns:
        True if successful, False otherwise
    """
    try:
        # Find categorized data files
        if not os.path.exists(input_dir):
            logger.error(f"Input directory does not exist: {input_dir}")
            return False
        
        # Look for the combined categorized data file first
        combined_file = os.path.join(input_dir, "all_categorized_transactions.json")
        
        if os.path.exists(combined_file):
            data = load_categorized_data(combined_file)
        else:
            # Fallback to individual files
            json_files = [f for f in os.listdir(input_dir) if f.startswith('categorized_') and f.endswith('.json')]
            
            if not json_files:
                logger.warning(f"No categorized data files found in {input_dir}")
                return False
            
            data = []
            for json_file in json_files:
                file_path = os.path.join(input_dir, json_file)
                file_data = load_categorized_data(file_path)
                data.extend(file_data)
        
        if not data:
            logger.warning("No transaction data found")
            return False
        
        logger.info(f"Analyzing {len(data)} transactions")
        
        # Perform analysis
        monthly_summary = analyzer.calculate_monthly_summary(data)
        yearly_trends = analyzer.calculate_yearly_trends(data)
        spending_patterns = analyzer.analyze_spending_patterns(data)
        
        # Generate insights
        analysis_results = {
            'monthly': monthly_summary,
            'yearly': yearly_trends,
            'patterns': spending_patterns
        }
        
        insights = analyzer.generate_insights(analysis_results)
        
        # Display results
        print("\n" + "="*60)
        print("💰 FINANCIAL ANALYSIS REPORT")
        print("="*60)
        
        # Overall statistics
        total_income = sum(t['amount'] for t in data if t['amount'] > 0)
        total_expenses = sum(abs(t['amount']) for t in data if t['amount'] < 0)
        net_income = total_income - total_expenses
        
        print(f"\n📊 OVERALL STATISTICS")
        print(f"Total Income:    ${total_income:,.2f}")
        print(f"Total Expenses:  ${total_expenses:,.2f}")
        print(f"Net Income:      ${net_income:,.2f}")
        print(f"Total Transactions: {len(data):,}")
        
        # Top spending categories
        if 'category_analysis' in spending_patterns:
            print(f"\n🏷️ TOP EXPENSE CATEGORIES")
            for i, (category, amount) in enumerate(spending_patterns['category_analysis']['top_expense_categories'][:5], 1):
                print(f"{i}. {category.title()}: ${amount:,.2f}")
        
        # Monthly averages
        if monthly_summary:
            months = len(monthly_summary)
            avg_monthly_income = total_income / months if months > 0 else 0
            avg_monthly_expenses = total_expenses / months if months > 0 else 0
            
            print(f"\n📅 MONTHLY AVERAGES ({months} months)")
            print(f"Average Monthly Income:  ${avg_monthly_income:,.2f}")
            print(f"Average Monthly Expenses: ${avg_monthly_expenses:,.2f}")
            print(f"Average Monthly Savings:  ${(avg_monthly_income - avg_monthly_expenses):,.2f}")
        
        # Recent months comparison
        if len(monthly_summary) >= 2:
            recent_months = sorted(monthly_summary.keys())[-2:]
            current_month = recent_months[-1]
            previous_month = recent_months[-2]
            
            current_expenses = monthly_summary[current_month]['total_expenses']
            previous_expenses = monthly_summary[previous_month]['total_expenses']
            
            change = current_expenses - previous_expenses
            change_percent = (change / previous_expenses * 100) if previous_expenses > 0 else 0
            
            print(f"\n📈 RECENT TRENDS")
            print(f"Previous Month ({previous_month}): ${previous_expenses:,.2f}")
            print(f"Current Month ({current_month}):  ${current_expenses:,.2f}")
            
            if change > 0:
                print(f"Change: +${change:,.2f} ({change_percent:+.1f}%) - Spending increased")
            else:
                print(f"Change: ${change:,.2f} ({change_percent:+.1f}%) - Spending decreased")
        
        # Key insights
        if insights:
            print(f"\n🔍 KEY INSIGHTS")
            for i, insight in enumerate(insights, 1):
                print(f"{i}. {insight}")
        
        # Save detailed analysis
        output_file = os.path.join(input_dir, "analysis_report.json")
        with open(output_file, 'w') as f:
            json.dump(analysis_results, f, indent=2, default=str)
        
        print(f"\n💾 Detailed analysis saved to: {output_file}")
        print("="*60)
        
        return True
        
    except Exception as e:
        logger.error(f"Analysis failed: {e}")
        return False


if __name__ == '__main__':
    # Command line interface
    if len(sys.argv) != 2:
        print("Usage: python analyze.py <input_dir>")
        sys.exit(1)
    
    input_dir = sys.argv[1]
    
    success = main(input_dir)
    sys.exit(0 if success else 1)