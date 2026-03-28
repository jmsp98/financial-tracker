"""
Free rule-based transaction categorization system.
No API costs or external dependencies required.
"""

import re
from typing import List, Dict, Optional
from datetime import datetime
import logging

from .parsers import Transaction
from .config import config

logger = logging.getLogger(__name__)


class RuleBasedCategorizer:
    """
    Categorize transactions using keyword matching rules.
    Completely free - no external API calls or token costs.
    """
    
    def __init__(self):
        self.categories = config.get_categories()
        self._compile_patterns()
    
    def _compile_patterns(self):
        """Pre-compile regex patterns for better performance."""
        self.category_patterns = {}
        
        for category, category_data in self.categories.items():
            keywords = category_data.get('keywords', [])
            if keywords:
                # Create a regex pattern that matches any of the keywords
                # Make it case-insensitive and match word boundaries
                pattern_parts = []
                for keyword in keywords:
                    # Escape special regex characters and add word boundaries
                    escaped_keyword = re.escape(keyword.lower())
                    pattern_parts.append(f"\\b{escaped_keyword}\\b")
                
                if pattern_parts:
                    pattern = "|".join(pattern_parts)
                    self.category_patterns[category] = re.compile(pattern, re.IGNORECASE)
    
    def categorize_transaction(self, transaction: Transaction) -> str:
        """
        Categorize a single transaction based on its description.
        
        Args:
            transaction: Transaction object to categorize
            
        Returns:
            Category name (e.g., 'groceries', 'dining', 'other')
        """
        description = transaction.description.lower()
        
        # Check for income first (positive amounts or specific keywords)
        if transaction.amount > 0:
            if 'income' in self.category_patterns:
                if self.category_patterns['income'].search(description):
                    return 'income'
            # If no income keywords match but amount is positive, still might be income
            income_indicators = ['deposit', 'payroll', 'salary', 'refund', 'interest']
            if any(indicator in description for indicator in income_indicators):
                return 'income'
        
        # Check other categories for expenses (negative amounts)
        for category, pattern in self.category_patterns.items():
            if category == 'income':  # Skip income, already handled
                continue
                
            if pattern.search(description):
                return category
        
        # Default to 'other' if no match found
        return 'other'
    
    def categorize_transactions(self, transactions: List[Transaction]) -> List[Dict]:
        """
        Categorize a list of transactions.
        
        Args:
            transactions: List of Transaction objects
            
        Returns:
            List of transaction dictionaries with categories
        """
        categorized_transactions = []
        
        for transaction in transactions:
            category = self.categorize_transaction(transaction)
            
            transaction_dict = {
                'date': transaction.date,
                'description': transaction.description,
                'amount': transaction.amount,
                'balance': transaction.balance,
                'type': transaction.transaction_type,
                'category': category
            }
            
            categorized_transactions.append(transaction_dict)
        
        return categorized_transactions
    
    def get_category_summary(self, categorized_transactions: List[Dict]) -> Dict[str, float]:
        """
        Get spending summary by category.
        
        Args:
            categorized_transactions: List of categorized transaction dicts
            
        Returns:
            Dictionary with category totals
        """
        category_totals = {}
        
        for transaction in categorized_transactions:
            category = transaction['category']
            amount = transaction['amount']
            
            if category not in category_totals:
                category_totals[category] = 0.0
            
            category_totals[category] += amount
        
        return category_totals
    
    def get_monthly_summary(self, categorized_transactions: List[Dict]) -> Dict[str, Dict[str, float]]:
        """
        Get spending summary by month and category.
        
        Args:
            categorized_transactions: List of categorized transaction dicts
            
        Returns:
            Dictionary with month -> category -> amount structure
        """
        monthly_summary = {}
        
        for transaction in categorized_transactions:
            date = transaction['date']
            category = transaction['category']
            amount = transaction['amount']
            
            # Create month key (YYYY-MM format)
            month_key = date.strftime('%Y-%m')
            
            if month_key not in monthly_summary:
                monthly_summary[month_key] = {}
            
            if category not in monthly_summary[month_key]:
                monthly_summary[month_key][category] = 0.0
            
            monthly_summary[month_key][category] += amount
        
        return monthly_summary
    
    def add_category(self, category_name: str, keywords: List[str]):
        """
        Add a new category or update existing one.
        
        Args:
            category_name: Name of the category
            keywords: List of keywords to match
        """
        self.categories[category_name] = {'keywords': keywords}
        self._compile_patterns()
        logger.info(f"Added/updated category '{category_name}' with {len(keywords)} keywords")
    
    def get_unmatched_descriptions(self, categorized_transactions: List[Dict]) -> List[str]:
        """
        Get list of transaction descriptions that were categorized as 'other'.
        Useful for identifying new patterns to add to categories.
        
        Args:
            categorized_transactions: List of categorized transaction dicts
            
        Returns:
            List of unique descriptions that were uncategorized
        """
        unmatched = set()
        
        for transaction in categorized_transactions:
            if transaction['category'] == 'other':
                unmatched.add(transaction['description'])
        
        return sorted(list(unmatched))
    
    def suggest_categories_for_unmatched(self, unmatched_descriptions: List[str]) -> Dict[str, List[str]]:
        """
        Suggest potential categories for unmatched descriptions.
        Uses simple heuristics to group similar descriptions.
        
        Args:
            unmatched_descriptions: List of descriptions to analyze
            
        Returns:
            Dictionary with suggested category -> descriptions mapping
        """
        suggestions = {
            'potential_groceries': [],
            'potential_dining': [],
            'potential_shopping': [],
            'potential_bills': [],
            'potential_transportation': []
        }
        
        for desc in unmatched_descriptions:
            desc_lower = desc.lower()
            
            # Simple heuristics for suggestions
            if any(word in desc_lower for word in ['market', 'store', 'shop', 'mart']):
                suggestions['potential_groceries'].append(desc)
            elif any(word in desc_lower for word in ['restaurant', 'cafe', 'food', 'kitchen']):
                suggestions['potential_dining'].append(desc)
            elif any(word in desc_lower for word in ['online', 'purchase', 'buy']):
                suggestions['potential_shopping'].append(desc)
            elif any(word in desc_lower for word in ['bill', 'payment', 'service', 'utility']):
                suggestions['potential_bills'].append(desc)
            elif any(word in desc_lower for word in ['gas', 'fuel', 'transport', 'parking']):
                suggestions['potential_transportation'].append(desc)
        
        # Remove empty categories
        return {k: v for k, v in suggestions.items() if v}


# Global categorizer instance
categorizer = RuleBasedCategorizer()