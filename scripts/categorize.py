"""
Categorization script - Apply rule-based categorization to processed transactions.
"""

import os
import sys
import json
import logging
from datetime import datetime
from typing import List, Dict

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from src.categorizer import categorizer
from src.transaction_parser import Transaction

logger = logging.getLogger(__name__)


def load_transactions_from_file(file_path: str) -> List[Transaction]:
    """Load transactions from JSON file and convert to Transaction objects."""
    try:
        with open(file_path, 'r') as f:
            data = json.load(f)
        
        transactions = []
        for item in data:
            try:
                transaction = Transaction(
                    date=datetime.fromisoformat(item['date']),
                    description=item['description'],
                    amount=item['amount'],
                    balance=item.get('balance'),
                    transaction_type=item.get('type')
                )
                transactions.append(transaction)
            except Exception as e:
                logger.warning(f"Skipping invalid transaction: {e}")
        
        return transactions
        
    except Exception as e:
        logger.error(f"Error loading transactions from {file_path}: {e}")
        return []


def main(input_dir: str, output_dir: str) -> bool:
    """
    Main categorization function.
    
    Args:
        input_dir: Directory containing processed transaction JSON files
        output_dir: Directory to save categorized transaction data
        
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
        
        logger.info(f"Found {len(json_files)} transaction files to categorize")
        
        # Process each file
        all_categorized = []
        
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
            
            # Save individual file results
            output_file = os.path.join(output_dir, f"categorized_{json_file}")
            with open(output_file, 'w') as f:
                json.dump(categorized_transactions, f, indent=2, default=str)
            
            all_categorized.extend(categorized_transactions)
            
            logger.info(f"Categorized {len(categorized_transactions)} transactions from {json_file}")
        
        if all_categorized:
            # Save combined results
            combined_file = os.path.join(output_dir, "all_categorized_transactions.json")
            with open(combined_file, 'w') as f:
                json.dump(all_categorized, f, indent=2, default=str)
            
            # Generate categorization summary
            category_summary = categorizer.get_category_summary(all_categorized)
            summary_file = os.path.join(output_dir, "category_summary.json")
            with open(summary_file, 'w') as f:
                json.dump(category_summary, f, indent=2)
            
            # Show categorization results
            logger.info(f"Successfully categorized {len(all_categorized)} total transactions")
            logger.info("Category breakdown:")
            for category, total in sorted(category_summary.items(), key=lambda x: abs(x[1]), reverse=True):
                logger.info(f"  {category.title()}: ${abs(total):,.2f}")
            
            # Show unmatched descriptions for improvement
            unmatched = categorizer.get_unmatched_descriptions(all_categorized)
            if unmatched:
                logger.info(f"\nFound {len(unmatched)} unmatched transaction types:")
                for desc in unmatched[:10]:  # Show first 10
                    logger.info(f"  '{desc}'")
                if len(unmatched) > 10:
                    logger.info(f"  ... and {len(unmatched) - 10} more")
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
    # Command line interface
    if len(sys.argv) != 3:
        print("Usage: python categorize.py <input_dir> <output_dir>")
        sys.exit(1)
    
    input_dir = sys.argv[1]
    output_dir = sys.argv[2]
    
    success = main(input_dir, output_dir)
    sys.exit(0 if success else 1)