"""
User feedback system for improving ML categorization.
Handles saving user corrections and retraining the model.
"""

import json
import os
import logging
from datetime import datetime
from typing import List, Dict, Any

from .pure_ml_categorizer import PureMLCategorizer
from .config import config

logger = logging.getLogger(__name__)


class UserFeedbackManager:
    """Manages user feedback for improving transaction categorization."""
    
    def __init__(self):
        self.feedback_file = os.path.join(config.get('data.categorized', './data/categorized'), 'user_feedback.json')
        self.categorized_file = os.path.join(config.get('data.categorized', './data/categorized'), 'all_categorized_transactions.json')
    
    def save_user_corrections(self, corrections: List[Dict[str, Any]]) -> bool:
        """
        Save user corrections for transactions with hierarchical categories.
        
        Args:
            corrections: List of correction dicts with transaction info, new category, and subcategory
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Load existing feedback
            feedback_data = self._load_feedback()
            
            # Add new corrections with hierarchical support
            for correction in corrections:
                feedback_entry = {
                    'timestamp': datetime.now().isoformat(),
                    'original_description': correction.get('description', ''),
                    'original_category': correction.get('original_category', 'other'),
                    'original_subcategory': correction.get('original_subcategory', 'unknown'),
                    'corrected_category': correction.get('new_category', ''),
                    'corrected_subcategory': correction.get('new_subcategory', ''),
                    'transaction_date': correction.get('date', ''),
                    'amount': correction.get('amount', 0),
                    'method': 'user_correction_hierarchical'
                }
                feedback_data.append(feedback_entry)
            
            # Save updated feedback
            os.makedirs(os.path.dirname(self.feedback_file), exist_ok=True)
            with open(self.feedback_file, 'w') as f:
                json.dump(feedback_data, f, indent=2)
            
            logger.info(f"Saved {len(corrections)} user corrections to {self.feedback_file}")
            return True
            
        except Exception as e:
            logger.error(f"Error saving user corrections: {e}")
            return False
    
    def apply_corrections_to_dataset(self, corrections: List[Dict[str, Any]]) -> bool:
        """
        Apply user corrections to the main categorized dataset.
        
        Args:
            corrections: List of corrections to apply
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Load current categorized data
            if not os.path.exists(self.categorized_file):
                logger.error(f"Categorized data file not found: {self.categorized_file}")
                return False
            
            with open(self.categorized_file, 'r') as f:
                categorized_data = json.load(f)
            
            # Apply corrections with hierarchical support
            corrections_applied = 0
            for correction in corrections:
                description = correction.get('description', '').strip()
                new_category = correction.get('new_category', '').lower().strip()
                new_subcategory = correction.get('new_subcategory', '').lower().strip()
                
                if not description or not new_category:
                    continue
                
                # Find matching transactions (by description similarity)
                for transaction in categorized_data:
                    if self._is_similar_transaction(transaction.get('description', ''), description):
                        transaction['category'] = new_category
                        transaction['subcategory'] = new_subcategory
                        transaction['categorization_method'] = 'user_corrected'
                        transaction['user_corrected'] = True
                        transaction['correction_timestamp'] = datetime.now().isoformat()
                        corrections_applied += 1
            
            # Save updated data
            with open(self.categorized_file, 'w') as f:
                json.dump(categorized_data, f, indent=2)
            
            logger.info(f"Applied {corrections_applied} corrections to categorized dataset")
            return True
            
        except Exception as e:
            logger.error(f"Error applying corrections to dataset: {e}")
            return False
    
    def retrain_ml_model(self) -> Dict[str, Any]:
        """
        Retrain the ML model with user corrections.
        
        Returns:
            Training results dictionary
        """
        try:
            from .parsers import Transaction
            
            # Load corrected data
            with open(self.categorized_file, 'r') as f:
                categorized_data = json.load(f)
            
            # Convert to Transaction objects
            transactions = []
            categories = []
            
            for item in categorized_data:
                try:
                    # Parse date
                    date_str = item['date']
                    if isinstance(date_str, str):
                        if 'T' in date_str:
                            date = datetime.fromisoformat(date_str)
                        else:
                            date = datetime.strptime(date_str, '%Y-%m-%d')
                    else:
                        date = date_str
                    
                    # Create Transaction object
                    transaction = Transaction(
                        date=date,
                        description=item['description'],
                        amount=item['amount'],
                        balance=item.get('balance'),
                        transaction_type=item.get('type', 'debit' if item['amount'] < 0 else 'credit'),
                        payment_method=item.get('payment_method'),
                        merchant=item.get('merchant', item['description']),
                        location=item.get('location'),
                        raw_description=item['description']
                    )
                    
                    transactions.append(transaction)
                    
                    # For hierarchical categorization, use combined category-subcategory label
                    # This allows the ML model to learn the full hierarchical patterns
                    category = item.get('category', 'other')
                    subcategory = item.get('subcategory', 'unknown')
                    
                    # Create combined label for training: "category::subcategory"
                    # This way the ML model can predict the full hierarchical classification
                    combined_label = f"{category}::{subcategory}" if subcategory and subcategory != 'unknown' else category
                    categories.append(combined_label)
                    
                except Exception as e:
                    logger.warning(f"Skipping invalid transaction during retraining: {e}")
            
            # Retrain Pure ML model
            pure_ml_categorizer = PureMLCategorizer()
            
            # Parse combined labels back to separate categories and subcategories
            parsed_categories = []
            parsed_subcategories = []
            
            for label in categories:
                if '::' in label:
                    category, subcategory = label.split('::', 1)
                    parsed_categories.append(category)
                    parsed_subcategories.append(subcategory)
                else:
                    parsed_categories.append(label)
                    parsed_subcategories.append('unknown')
            
            training_results = pure_ml_categorizer.train_model(transactions, parsed_categories, parsed_subcategories)
            
            logger.info("Pure ML model retrained successfully with user corrections")
            return training_results
            
        except Exception as e:
            logger.error(f"Error retraining ML model: {e}")
            return {'error': str(e)}
    
    def _load_feedback(self) -> List[Dict[str, Any]]:
        """Load existing feedback data."""
        if os.path.exists(self.feedback_file):
            try:
                with open(self.feedback_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"Error loading feedback file: {e}")
        return []
    
    def _is_similar_transaction(self, desc1: str, desc2: str) -> bool:
        """Check if two transaction descriptions are similar enough to be the same transaction."""
        # Simple similarity check - could be improved with fuzzy matching
        desc1_clean = desc1.lower().strip()
        desc2_clean = desc2.lower().strip()
        
        # Exact match
        if desc1_clean == desc2_clean:
            return True
        
        # Check if desc2 is contained in desc1 (since desc2 might be truncated)
        if len(desc2_clean) > 10 and desc2_clean in desc1_clean:
            return True
        
        # Check if they share most significant words
        words1 = set(desc1_clean.split())
        words2 = set(desc2_clean.split())
        
        if len(words2) > 0:
            similarity = len(words1.intersection(words2)) / len(words2)
            return similarity > 0.8
        
        return False
    
    def get_feedback_stats(self) -> Dict[str, Any]:
        """Get statistics about user feedback."""
        feedback_data = self._load_feedback()
        
        if not feedback_data:
            return {'total_corrections': 0, 'categories_corrected': {}}
        
        categories_corrected = {}
        for entry in feedback_data:
            old_cat = entry.get('original_category', 'unknown')
            new_cat = entry.get('corrected_category', 'unknown')
            key = f"{old_cat} → {new_cat}"
            categories_corrected[key] = categories_corrected.get(key, 0) + 1
        
        return {
            'total_corrections': len(feedback_data),
            'categories_corrected': categories_corrected,
            'latest_correction': max([entry.get('timestamp', '') for entry in feedback_data], default='Never')
        }