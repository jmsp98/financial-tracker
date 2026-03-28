"""
Categorization script - Apply hybrid ML/rule-based categorization to processed transactions.
"""

import os
import sys
import json
import logging
from datetime import datetime
from typing import List, Dict

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.ml_categorizer import HybridCategorizer
from src.parsers import Transaction

logger = logging.getLogger(__name__)


def load_transactions_from_file(file_path: str) -> List[Transaction]:
    """Load transactions from JSON file and convert to Transaction objects."""
    try:
        with open(file_path, 'r') as f:
            data = json.load(f)
        
        transactions = []
        for item in data:
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
                
                # Create Transaction object with enhanced fields
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
            except Exception as e:
                logger.warning(f"Skipping invalid transaction: {e}")
        
        return transactions
        
    except Exception as e:
        logger.error(f"Error loading transactions from {file_path}: {e}")
        return []


def main(input_dir: str, output_dir: str, use_ml: bool = True) -> bool:
    """
    Main categorization function.
    
    Args:
        input_dir: Directory containing processed transaction JSON files
        output_dir: Directory to save categorized transaction data
        use_ml: Whether to use ML categorization (falls back to rule-based)
        
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
        
        # Initialize hybrid categorizer
        categorizer = HybridCategorizer(use_ml=use_ml)
        
        # Process each file
        all_categorized = []
        ml_used_total = 0
        rules_used_total = 0
        
        for json_file in json_files:
            file_path = os.path.join(input_dir, json_file)
            logger.info(f"Categorizing: {json_file}")
            
            # Load transactions
            transactions = load_transactions_from_file(file_path)
            
            if not transactions:
                logger.warning(f"No valid transactions found in {json_file}")
                continue
            
            # Categorize transactions
            categorized_transactions = categorizer.categorize_transactions(transactions)
            
            # Count ML vs rule-based usage
            ml_count = sum(1 for t in categorized_transactions if t.get('categorization_method') == 'ml')
            rules_count = len(categorized_transactions) - ml_count
            ml_used_total += ml_count
            rules_used_total += rules_count
            
            # Save individual file results
            output_file = os.path.join(output_dir, f"categorized_{json_file}")
            with open(output_file, 'w') as f:
                json.dump(categorized_transactions, f, indent=2, default=str)
            
            all_categorized.extend(categorized_transactions)
            
            logger.info(f"Categorized {len(categorized_transactions)} transactions from {json_file}")
            if use_ml:
                logger.info(f"  ML: {ml_count}, Rules: {rules_count}")
        
        if all_categorized:
            # Save combined results
            combined_file = os.path.join(output_dir, "all_categorized_transactions.json")
            with open(combined_file, 'w') as f:
                json.dump(all_categorized, f, indent=2, default=str)
            
            # Generate categorization summary
            category_summary = {}
            for transaction in all_categorized:
                category = transaction.get('category', 'other')
                amount = transaction.get('amount', 0)
                if category in category_summary:
                    category_summary[category] += amount
                else:
                    category_summary[category] = amount
            
            summary_file = os.path.join(output_dir, "category_summary.json")
            with open(summary_file, 'w') as f:
                json.dump(category_summary, f, indent=2)
            
            # Show categorization results
            logger.info(f"Successfully categorized {len(all_categorized)} total transactions")
            if use_ml:
                logger.info(f"ML used: {ml_used_total}, Rule-based: {rules_used_total}")
            
            logger.info("Category breakdown:")
            for category, total in sorted(category_summary.items(), key=lambda x: abs(x[1]), reverse=True):
                logger.info(f"  {category.title()}: ${abs(total):,.2f}")
            
            # Show unmatched descriptions for improvement
            unmatched = [t['description'] for t in all_categorized if t.get('category') == 'other']
            if unmatched:
                unique_unmatched = list(set(unmatched))
                logger.info(f"\nFound {len(unique_unmatched)} unique 'other' transaction types:")
                for desc in unique_unmatched[:10]:  # Show first 10
                    logger.info(f"  '{desc}'")
                if len(unique_unmatched) > 10:
                    logger.info(f"  ... and {len(unique_unmatched) - 10} more")
                logger.info("\nConsider adding these to your config.yaml categories for better categorization")
            
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
        print("Usage: python categorize.py <input_dir> <output_dir> [--no-ml]")
        print("\nOptions:")
        print("  --no-ml    Use only rule-based categorization (disable ML)")
        print("\nExamples:")
        print("  python scripts/categorize.py data/processed_new data/categorized")
        print("  python scripts/categorize.py data/processed_new data/categorized --no-ml")
        sys.exit(1)
    
    input_dir = sys.argv[1]
    output_dir = sys.argv[2]
    use_ml = '--no-ml' not in sys.argv
    
    if use_ml:
        print("Using hybrid ML + rule-based categorization")
    else:
        print("Using rule-based categorization only")
    
    success = main(input_dir, output_dir, use_ml)
    sys.exit(0 if success else 1)