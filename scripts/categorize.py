"""
Pure ML Categorization script - Apply 100% ML-driven categorization to processed transactions.
No rule-based fallbacks - uses advanced ML models for both categories and subcategories.
"""

import os
import sys
import json
import logging
from datetime import datetime
from typing import List, Dict

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.pure_ml_categorizer import PureMLCategorizer
from src.parsers import Transaction

logger = logging.getLogger(__name__)


def load_transactions_from_file(file_path: str) -> List[Transaction]:
    """Load transactions from JSON file and convert to Transaction objects."""
    try:
        with open(file_path, 'r') as f:
            data = json.load(f)
        
        # Handle both old format (direct array) and new format (with "transactions" key)
        if isinstance(data, dict) and 'transactions' in data:
            transaction_list = data['transactions']
        elif isinstance(data, list):
            transaction_list = data
        else:
            logger.error(f"Unexpected data format in {file_path}")
            return []
        
        transactions = []
        for item in transaction_list:
            try:
                # Handle both old format (just raw transaction data) and new format (with currency fields)
                if isinstance(item, str):
                    # This is the problematic case - skip malformed data
                    logger.warning(f"Skipping malformed transaction data: {item}")
                    continue
                
                if not isinstance(item, dict):
                    logger.warning(f"Skipping invalid transaction: expected dict, got {type(item)}")
                    continue
                    
                # Parse date
                date_str = item['date']
                if isinstance(date_str, str):
                    if 'T' in date_str:
                        date = datetime.fromisoformat(date_str)
                    else:
                        date = datetime.strptime(date_str, '%Y-%m-%d')
                else:
                    date = date_str
                
                # Create Transaction object with enhanced fields
                transaction = Transaction(
                    date=date,
                    description=item['description'],
                    amount=item['amount'],
                    balance=item.get('balance'),
                    transaction_type=item.get('type', 'debit' if item['amount'] < 0 else 'credit'),
                    payment_method=item.get('payment_method'),
                    merchant=item['description'],
                    location=None,
                    raw_description=item['description']
                )
                transactions.append(transaction)
            except Exception as e:
                logger.warning(f"Skipping invalid transaction: {e}")
        
        return transactions
        
    except Exception as e:
        logger.error(f"Error loading transactions from {file_path}: {e}")
        return []


def main(input_dir: str, output_dir: str, use_ml: bool = True) -> bool:
    """
    Main categorization function using Pure ML approach.
    
    Args:
        input_dir: Directory containing processed transaction JSON files
        output_dir: Directory to save categorized transaction data
        use_ml: Whether to use ML categorization (Pure ML only - no rule fallback)
        
    Returns:
        True if successful, False otherwise
    """
    try:
        # Ensure output directory exists
        os.makedirs(output_dir, exist_ok=True)
        
        # Find JSON files
        if not os.path.exists(input_dir):
            logger.error(f"Input directory does not exist: {input_dir}")
            return False
        
        json_files = [f for f in os.listdir(input_dir) if f.endswith('.json')]
        
        if not json_files:
            logger.warning(f"No JSON files found in {input_dir}")
            return False
        
        # Process only the combined file to avoid duplicates
        # The individual statement files are subsets of all_transactions.json
        if 'all_transactions.json' in json_files:
            json_files = ['all_transactions.json']
            logger.info(f"Processing combined transaction file to avoid duplicates")
        else:
            logger.info(f"Found {len(json_files)} transaction files to categorize")
        
        # Initialize pure ML categorizer
        if not use_ml:
            logger.warning("Pure ML categorizer requires ML to be enabled. Force-enabling ML mode.")
            use_ml = True
        
        categorizer = PureMLCategorizer()
        
        # Check if model is trained
        if not categorizer.is_trained:
            logger.warning("Pure ML model is not trained. Categorization will return 'unknown' categories.")
            logger.info("To train the model, use: python scripts/train_ml_model.py")
        
        # Process each file
        all_categorized = []
        ml_used_total = 0
        unknown_count = 0
        
        for json_file in json_files:
            file_path = os.path.join(input_dir, json_file)
            logger.info(f"Categorizing: {json_file}")
            
            # Load transactions
            transactions = load_transactions_from_file(file_path)
            
            if not transactions:
                logger.warning(f"No valid transactions found in {json_file}")
                continue
            
            # Categorize transactions using pure ML
            categorized_transactions = categorizer.categorize_transactions(transactions)
            
            # Count ML predictions vs unknown
            ml_count = sum(1 for t in categorized_transactions if t.get('category') != 'unknown')
            unknown = len(categorized_transactions) - ml_count
            ml_used_total += ml_count
            unknown_count += unknown
            
            # Save individual file results
            output_file = os.path.join(output_dir, f"categorized_{json_file}")
            with open(output_file, 'w') as f:
                json.dump(categorized_transactions, f, indent=2, default=str)
            
            all_categorized.extend(categorized_transactions)
            
            logger.info(f"Categorized {len(categorized_transactions)} transactions from {json_file}")
            logger.info(f"  ML predicted: {ml_count}, Unknown: {unknown}")
        
        if all_categorized:
            # Save combined results
            combined_file = os.path.join(output_dir, "all_categorized_transactions.json")
            with open(combined_file, 'w') as f:
                json.dump(all_categorized, f, indent=2, default=str)
            
            # Generate categorization summary
            category_summary = {}
            confidence_summary = []
            for transaction in all_categorized:
                category = transaction.get('category', 'unknown')
                amount = transaction.get('amount', 0)
                confidence = transaction.get('ml_confidence', 0)
                
                if category in category_summary:
                    category_summary[category] += amount
                else:
                    category_summary[category] = amount
                
                if confidence > 0:
                    confidence_summary.append(confidence)
            
            summary_file = os.path.join(output_dir, "category_summary.json")
            with open(summary_file, 'w') as f:
                json.dump(category_summary, f, indent=2)
            
            # Show categorization results
            logger.info(f"Successfully categorized {len(all_categorized)} total transactions")
            logger.info(f"ML predictions: {ml_used_total}, Unknown: {unknown_count}")
            
            if confidence_summary:
                avg_confidence = sum(confidence_summary) / len(confidence_summary)
                logger.info(f"Average ML confidence: {avg_confidence:.3f}")
            
            logger.info("Category breakdown:")
            for category, total in sorted(category_summary.items(), key=lambda x: abs(x[1]), reverse=True):
                logger.info(f"  {category.title()}: ${abs(total):,.2f}")
            
            # Show unknown transactions for model improvement
            unknown_transactions = [t for t in all_categorized if t.get('category') == 'unknown']
            if unknown_transactions:
                unique_unknown = list(set([t['description'] for t in unknown_transactions]))
                logger.info(f"\nFound {len(unique_unknown)} unique 'unknown' transaction types:")
                for desc in unique_unknown[:10]:  # Show first 10
                    logger.info(f"  '{desc}'")
                if len(unique_unknown) > 10:
                    logger.info(f"  ... and {len(unique_unknown) - 10} more")
                logger.info("\nConsider training the ML model with labeled data to improve categorization")
            
            logger.info(f"Results saved to: {output_dir}")
            return True
        else:
            logger.warning("No transactions were categorized")
            return False
            
    except Exception as e:
        logger.error(f"Categorization failed: {e}")
        return False


if __name__ == '__main__':
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(levelname)s:%(name)s:%(message)s'
    )
    
    # Command line interface
    if len(sys.argv) < 3:
        print("Usage: python categorize.py <input_dir> <output_dir>")
        print("\nPure ML Categorization - No rule-based fallbacks")
        print("Uses advanced machine learning models for 100% ML-driven categorization")
        print("\nExamples:")
        print("  python scripts/categorize.py data/processed_new data/categorized")
        print("\nNote: Ensure ML model is trained using 'python scripts/train_ml_model.py'")
        sys.exit(1)
    
    input_dir = sys.argv[1]
    output_dir = sys.argv[2]
    
    print("Using Pure ML categorization (100% ML-driven, no rule-based fallbacks)")
    
    success = main(input_dir, output_dir, use_ml=True)
    sys.exit(0 if success else 1)