"""
ML model training script for transaction categorization.
Uses existing categorized data to train a local ML model.
"""

import os
import sys
import json
import logging
from datetime import datetime
from typing import List, Dict

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.ml_categorizer import MLCategorizer, HybridCategorizer
from src.parsers import Transaction

logger = logging.getLogger(__name__)


def load_categorized_transactions(file_path: str) -> List[Dict]:
    """Load categorized transactions from JSON file."""
    if not os.path.exists(file_path):
        logger.error(f"Categorized transactions file not found: {file_path}")
        return []
    
    with open(file_path, 'r') as f:
        return json.load(f)


def convert_to_transactions(transaction_dicts: List[Dict]) -> List[Transaction]:
    """Convert transaction dictionaries to Transaction objects."""
    transactions = []
    
    for txn_dict in transaction_dicts:
        try:
            # Parse date
            date_str = txn_dict['date']
            if isinstance(date_str, str):
                try:
                    if 'T' in date_str:
                        date = datetime.fromisoformat(date_str)
                    else:
                        # Handle datetime with space separator
                        date = datetime.strptime(date_str, '%Y-%m-%d %H:%M:%S')
                except ValueError:
                    try:
                        # Try just date part
                        date_part = date_str.split(' ')[0]
                        date = datetime.strptime(date_part, '%Y-%m-%d')
                    except ValueError:
                        logger.warning(f"Could not parse date: {date_str}")
                        continue
            else:
                date = date_str
            
            # Create Transaction object
            transaction = Transaction(
                date=date,
                description=txn_dict['description'],
                amount=float(txn_dict['amount']),
                balance=txn_dict.get('balance'),
                transaction_type=txn_dict['type'],
                payment_method=txn_dict.get('payment_method'),
                merchant=txn_dict.get('merchant', txn_dict['description']),
                location=txn_dict.get('location'),
                raw_description=txn_dict['description']
            )
            
            transactions.append(transaction)
            
        except Exception as e:
            logger.warning(f"Failed to convert transaction: {e}")
            continue
    
    return transactions


def main(categorized_data_path: str) -> bool:
    """
    Train ML model on existing categorized data.
    
    Args:
        categorized_data_path: Path to categorized transactions JSON file
        
    Returns:
        True if training successful, False otherwise
    """
    try:
        # Load categorized data
        logger.info(f"Loading categorized data from: {categorized_data_path}")
        transaction_dicts = load_categorized_transactions(categorized_data_path)
        
        if not transaction_dicts:
            logger.error("No transaction data found")
            return False
        
        logger.info(f"Loaded {len(transaction_dicts)} categorized transactions")
        
        # Convert to Transaction objects
        transactions = convert_to_transactions(transaction_dicts)
        categories = [txn_dict.get('category', 'other') for txn_dict in transaction_dicts]
        
        if len(transactions) != len(categories):
            logger.error(f"Mismatch: {len(transactions)} transactions vs {len(categories)} categories")
            return False
        
        # Check data distribution
        from collections import Counter
        category_counts = Counter(categories)
        logger.info("Category distribution:")
        for category, count in category_counts.most_common():
            logger.info(f"  {category}: {count} transactions")
        
        # Check minimum data requirements
        if len(transactions) < 50:
            logger.warning(f"Only {len(transactions)} transactions available. ML training requires at least 50.")
            logger.info("Will use rule-based categorization only.")
            return False
        
        # Create and train ML categorizer
        logger.info("Initializing ML categorizer...")
        ml_categorizer = MLCategorizer()
        
        # Train model
        logger.info("Training ML model...")
        results = ml_categorizer.train_model(transactions, categories)
        
        # Display results
        logger.info("Training completed successfully!")
        logger.info(f"Test accuracy: {results['test_accuracy']:.3f}")
        logger.info(f"Cross-validation: {results['cv_mean']:.3f} ±{results['cv_std']:.3f}")
        logger.info(f"Features: {results['n_features']}")
        
        print("\n=== ML MODEL TRAINING RESULTS ===")
        print(f"Transactions used: {results['n_samples']}")
        print(f"Features extracted: {results['n_features']}")
        print(f"Test accuracy: {results['test_accuracy']:.1%}")
        print(f"Cross-validation: {results['cv_mean']:.1%} ±{results['cv_std']:.1%}")
        print(f"Categories: {len(category_counts)}")
        
        print("\nDetailed Classification Report:")
        print(results['classification_report'])
        
        return True
        
    except Exception as e:
        logger.error(f"Training failed: {e}")
        return False


if __name__ == '__main__':
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(levelname)s:%(name)s:%(message)s'
    )
    
    # Command line interface
    if len(sys.argv) != 2:
        print("Usage: python train_ml_model.py <categorized_transactions.json>")
        print("\nExample:")
        print("  python scripts/train_ml_model.py data/categorized/all_categorized_transactions.json")
        sys.exit(1)
    
    categorized_file = sys.argv[1]
    
    # Check if file exists
    if not os.path.exists(categorized_file):
        print(f"Error: File not found: {categorized_file}")
        sys.exit(1)
    
    success = main(categorized_file)
    sys.exit(0 if success else 1)