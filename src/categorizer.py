"""
Free rule-based transaction categorization system.
No API costs or external dependencies required.
"""

import re
from typing import List, Dict, Optional, Tuple
from datetime import datetime
import logging

from .parsers import Transaction
from .config import config

logger = logging.getLogger(__name__)


class RuleBasedCategorizer:
    """
    Categorize transactions using keyword matching rules with description history lookup.
    Completely free - no external API calls or token costs.
    """
    
    def __init__(self, use_description_history: bool = True):
        self.categories = config.get_categories()
        self.use_description_history = use_description_history
        self.description_history = {}  # Maps description -> (category, subcategory)
        self._compile_patterns()
        
        if self.use_description_history:
            self._load_description_history()
    
    def _load_description_history(self):
        """Load description history from previously categorized transactions."""
        try:
            import os
            categorized_path = config.get('data.categorized', './data/categorized')
            history_file = os.path.join(categorized_path, 'all_categorized_transactions.json')
            
            if os.path.exists(history_file):
                import json
                with open(history_file, 'r') as f:
                    transactions = json.load(f)
                
                for txn in transactions:
                    desc = txn.get('description', '').strip()
                    category = txn.get('category', '')
                    subcategory = txn.get('subcategory', '')
                    
                    # Only save non-"other" categorizations
                    if desc and category and category.lower() != 'other':
                        self.description_history[desc] = (category, subcategory)
                
                logger.info(f"Loaded {len(self.description_history)} description categorizations from history")
        except Exception as e:
            logger.warning(f"Could not load description history: {e}")
            self.description_history = {}
    
    def get_description_categorization(self, description: str) -> Tuple[Optional[str], Optional[str]]:
        """
        Get categorization for a description from history.
        
        Args:
            description: Transaction description
            
        Returns:
            Tuple of (category, subcategory) or (None, None) if not found
        """
        if not self.use_description_history:
            return None, None
        
        desc = description.strip()
        
        # Exact match first
        if desc in self.description_history:
            return self.description_history[desc]
        
        # Fuzzy matching for similar descriptions
        desc_lower = desc.lower()
        for hist_desc, (cat, subcat) in self.description_history.items():
            hist_desc_lower = hist_desc.lower()
            
            # Check for substantial overlap (both ways)
            if (len(desc_lower) > 5 and desc_lower in hist_desc_lower) or \
               (len(hist_desc_lower) > 5 and hist_desc_lower in desc_lower):
                return cat, subcat
        
        return None, None
    
    def update_description_history(self, description: str, category: str, subcategory: str):
        """
        Update description history with new categorization.
        
        Args:
            description: Transaction description
            category: Category name
            subcategory: Subcategory name
        """
        if self.use_description_history:
            desc = description.strip()
            self.description_history[desc] = (category, subcategory)
            logger.info(f"Updated description history: '{desc}' -> {category} -> {subcategory}")
    
    def save_description_history(self):
        """Save description history to file for persistence."""
        try:
            import os
            categorized_path = config.get('data.categorized', './data/categorized')
            os.makedirs(categorized_path, exist_ok=True)
            
            history_file = os.path.join(categorized_path, 'description_history.json')
            import json
            with open(history_file, 'w') as f:
                json.dump(self.description_history, f, indent=2)
            
            logger.info(f"Saved {len(self.description_history)} description categorizations to history")
        except Exception as e:
            logger.error(f"Could not save description history: {e}")
    
    def _compile_patterns(self):
        """Pre-compile regex patterns for better performance with hierarchical categories."""
        self.category_patterns = {}
        self.subcategory_patterns = {}
        
        for category, category_data in self.categories.items():
            # Handle hierarchical structure with subcategories
            if 'subcategories' in category_data:
                self.subcategory_patterns[category] = {}
                
                for subcategory, subcategory_data in category_data['subcategories'].items():
                    keywords = subcategory_data.get('keywords', [])
                    if keywords:
                        pattern_parts = []
                        for keyword in keywords:
                            escaped_keyword = re.escape(keyword.lower())
                            pattern_parts.append(escaped_keyword)
                        
                        if pattern_parts:
                            pattern = "|".join(pattern_parts)
                            self.subcategory_patterns[category][subcategory] = re.compile(pattern, re.IGNORECASE)
            else:
                # Legacy flat structure (for backwards compatibility)
                keywords = category_data.get('keywords', [])
                if keywords:
                    pattern_parts = []
                    for keyword in keywords:
                        escaped_keyword = re.escape(keyword.lower())
                        pattern_parts.append(escaped_keyword)
                    
                    if pattern_parts:
                        pattern = "|".join(pattern_parts)
                        self.category_patterns[category] = re.compile(pattern, re.IGNORECASE)
    
    def categorize_transaction(self, transaction: Transaction) -> Tuple[str, Optional[str]]:
        """
        Categorize a single transaction based on its description.
        Uses description history first, then falls back to keyword matching.
        
        Args:
            transaction: Transaction object to categorize
            
        Returns:
            Tuple of (category, subcategory) e.g., ('groceries', 'tesco') or ('other', None)
        """
        description = transaction.description
        
        # First, check description history for exact or similar matches
        if self.use_description_history:
            hist_category, hist_subcategory = self.get_description_categorization(description)
            if hist_category:
                logger.debug(f"Found historical categorization for '{description}': {hist_category} -> {hist_subcategory}")
                return hist_category, hist_subcategory
        
        # Fall back to keyword-based categorization
        description_lower = description.lower()
        
        # Check for income first (positive amounts or specific keywords)
        if transaction.amount > 0:
            if 'income' in self.subcategory_patterns:
                for subcategory, pattern in self.subcategory_patterns['income'].items():
                    if pattern.search(description_lower):
                        result = ('income', subcategory)
                        self._maybe_update_history(description, result)
                        return result
                # If no subcategory matches but we have income patterns, return general income
                result = ('income', 'transfers')
                self._maybe_update_history(description, result)
                return result
            
            # Fallback income detection
            income_indicators = ['deposit', 'payroll', 'salary', 'refund', 'interest', 'transfer', 'rent received']
            for indicator in income_indicators:
                if indicator in description_lower:
                    result = ('income', 'transfers')
                    self._maybe_update_history(description, result)
                    return result
        
        # Check hierarchical categories for expenses (negative amounts)
        for category in self.subcategory_patterns:
            if category == 'income':  # Skip income, already handled
                continue
                
            for subcategory, pattern in self.subcategory_patterns[category].items():
                if pattern.search(description_lower):
                    result = (category, subcategory)
                    self._maybe_update_history(description, result)
                    return result
        
        # Check legacy flat categories (backwards compatibility)
        for category, pattern in self.category_patterns.items():
            if category == 'income':  # Skip income, already handled
                continue
                
            if pattern.search(description_lower):
                result = (category, None)
                self._maybe_update_history(description, result)
                return result
        
        # Default to 'other' with 'unknown' subcategory if no match found
        return 'other', 'unknown'
    
    def _maybe_update_history(self, description: str, result: Tuple[str, Optional[str]]):
        """Update description history if enabled and result is not 'other'."""
        if self.use_description_history and result[0] != 'other':
            category, subcategory = result
            self.update_description_history(description, category, subcategory or 'unknown')
    
    def categorize_transactions(self, transactions: List[Transaction]) -> List[Dict]:
        """
        Categorize a list of transactions with hierarchical categories.
        
        Args:
            transactions: List of Transaction objects
            
        Returns:
            List of transaction dictionaries with categories and subcategories
        """
        categorized_transactions = []
        
        for transaction in transactions:
            category, subcategory = self.categorize_transaction(transaction)
            
            transaction_dict = {
                'date': transaction.date,
                'description': transaction.description,
                'amount': transaction.amount,
                'balance': transaction.balance,
                'type': transaction.transaction_type,
                'category': category,
                'subcategory': subcategory,
                'categorization_method': 'rules'
            }
            
            # Add optional fields if they exist
            if hasattr(transaction, 'payment_method') and transaction.payment_method:
                transaction_dict['payment_method'] = transaction.payment_method
            if hasattr(transaction, 'merchant') and transaction.merchant:
                transaction_dict['merchant'] = transaction.merchant  
            if hasattr(transaction, 'location') and transaction.location:
                transaction_dict['location'] = transaction.location
                
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