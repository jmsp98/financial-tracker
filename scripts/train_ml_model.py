"""
Pure ML model training script for transaction categorization.
Uses existing categorized data to train 100% ML-driven categorization models.
Trains both category and subcategory models without rule-based dependencies.
Includes comprehensive training data for better accuracy.
"""

import os
import sys
import json
import logging
from datetime import datetime
from typing import List, Dict
from pathlib import Path

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.pure_ml_categorizer import PureMLCategorizer
from src.parsers import Transaction

logger = logging.getLogger(__name__)


def load_training_data() -> List[Dict]:
    """Load training data from multiple sources."""
    project_root = Path(__file__).parent.parent
    training_data = []
    
    # First priority: comprehensive training data (created by create_training_data.py)
    comprehensive_file = project_root / "training_data" / "comprehensive_training_data.json"
    if comprehensive_file.exists():
        logger.info(f"Loading comprehensive training data from {comprehensive_file}")
        with open(comprehensive_file, 'r') as f:
            data = json.load(f)
            training_examples = data.get('training_data', [])
            logger.info(f"Loaded {len(training_examples)} training examples from comprehensive dataset")
            training_data.extend(training_examples)
    else:
        logger.info("No comprehensive training data found, will create it...")
        # Try to create training data
        try:
            import subprocess
            result = subprocess.run([sys.executable, str(project_root / "scripts" / "create_training_data.py")], 
                                  capture_output=True, text=True, cwd=project_root)
            if result.returncode == 0:
                logger.info("Created comprehensive training data, loading...")
                if comprehensive_file.exists():
                    with open(comprehensive_file, 'r') as f:
                        data = json.load(f)
                        training_examples = data.get('training_data', [])
                        logger.info(f"Loaded {len(training_examples)} training examples from newly created dataset")
                        training_data.extend(training_examples)
            else:
                logger.warning("Failed to create comprehensive training data")
        except Exception as e:
            logger.warning(f"Could not auto-create training data: {e}")
    
    # Second priority: existing categorized transactions with meaningful categories
    categorized_files = [
        project_root / "data" / "categorized" / "all_categorized_transactions.json",
        project_root / "data" / "categorized" / "categorized_all_transactions.json"
    ]
    
    for file_path in categorized_files:
        if file_path.exists():
            logger.info(f"Loading additional categorized data from {file_path}")
            with open(file_path, 'r') as f:
                transactions = json.load(f)
            
            # Filter for meaningful categories (not 'other' or 'unknown')
            meaningful_txns = []
            for txn in transactions:
                category = txn.get('category', '').lower()
                subcategory = txn.get('subcategory', '').lower()
                
                if (category not in ['other', 'unknown', ''] and 
                    subcategory not in ['other', 'unknown', '']):
                    meaningful_txns.append(txn)
            
            if meaningful_txns:
                logger.info(f"Found {len(meaningful_txns)} meaningfully categorized transactions")
                training_data.extend(meaningful_txns)
                break  # Use first file with meaningful data
    
    # Third priority: user feedback
    feedback_file = project_root / "data" / "categorized" / "user_feedback.json"
    if feedback_file.exists():
        logger.info(f"Loading user feedback from {feedback_file}")
        with open(feedback_file, 'r') as f:
            feedback_data = json.load(f)
        
        for entry in feedback_data:
            if (entry.get('corrected_category', '').lower() not in ['other', 'unknown', ''] and
                entry.get('corrected_subcategory', '').lower() not in ['other', 'unknown', '']):
                training_data.append({
                    'description': entry.get('original_description', ''),
                    'category': entry.get('corrected_category', ''),
                    'subcategory': entry.get('corrected_subcategory', ''),
                    'amount': entry.get('amount', 0),
                    'date': entry.get('transaction_date', ''),
                    'merchant': '',
                    'location': '',
                    'payment_method': '',
                    'source': 'user_feedback'
                })
        
        logger.info(f"Added {len([e for e in feedback_data if e.get('corrected_category', '').lower() not in ['other', 'unknown']])} user feedback examples")
    
    return training_data


def load_categorized_transactions(file_path: str) -> List[Dict]:
    """Load categorized transactions from JSON file (legacy function)."""
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
    Train Pure ML models on existing categorized data.
    
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
        categories = [txn_dict.get('category', 'unknown') for txn_dict in transaction_dicts]
        subcategories = [txn_dict.get('subcategory', 'unknown') for txn_dict in transaction_dicts]
        
        if len(transactions) != len(categories):
            logger.error(f"Mismatch: {len(transactions)} transactions vs {len(categories)} categories")
            return False
        
        # Check data distribution
        from collections import Counter
        category_counts = Counter(categories)
        subcategory_counts = Counter(subcategories)
        
        logger.info("Category distribution:")
        for category, count in category_counts.most_common():
            logger.info(f"  {category}: {count} transactions")
        
        logger.info("Subcategory distribution:")
        for subcategory, count in subcategory_counts.most_common()[:10]:  # Show top 10
            logger.info(f"  {subcategory}: {count} transactions")
        if len(subcategory_counts) > 10:
            logger.info(f"  ... and {len(subcategory_counts) - 10} more subcategories")
        
        # Check minimum data requirements
        if len(transactions) < 100:
            logger.warning(f"Only {len(transactions)} transactions available. Pure ML training works better with 100+.")
            if len(transactions) < 50:
                logger.error("Need at least 50 transactions for Pure ML training.")
                return False
        
        # Remove 'unknown' categories if they exist (can't train on unknown labels)
        valid_indices = [i for i, cat in enumerate(categories) if cat != 'unknown']
        if len(valid_indices) != len(transactions):
            logger.info(f"Filtering out {len(transactions) - len(valid_indices)} transactions with 'unknown' categories")
            transactions = [transactions[i] for i in valid_indices]
            categories = [categories[i] for i in valid_indices]
            subcategories = [subcategories[i] for i in valid_indices]
        
        if len(transactions) == 0:
            logger.error("No valid training data after filtering unknown categories")
            return False
        
        # Create and train Pure ML categorizer
        logger.info("Initializing Pure ML categorizer...")
        pure_ml_categorizer = PureMLCategorizer()
        
        # Train model with both categories and subcategories
        logger.info("Training Pure ML models (category + subcategory)...")
        results = pure_ml_categorizer.train_model(transactions, categories, subcategories)
        
        # Display results
        logger.info("Training completed successfully!")
        logger.info(f"Category test accuracy: {results['category_test_accuracy']:.3f}")
        if 'subcategory_test_accuracy' in results:
            logger.info(f"Subcategory test accuracy: {results['subcategory_test_accuracy']:.3f}")
        logger.info(f"Features: {results['n_features']}")
        
        print("\n=== PURE ML MODEL TRAINING RESULTS ===")
        print(f"Transactions used: {results['n_samples']}")
        print(f"Features extracted: {results['n_features']}")
        print(f"Category test accuracy: {results['category_test_accuracy']:.1%}")
        if 'subcategory_test_accuracy' in results:
            print(f"Subcategory test accuracy: {results['subcategory_test_accuracy']:.1%}")
        print(f"Categories: {len(category_counts)}")
        print(f"Subcategories: {len(subcategory_counts)}")
        
        print("\nCategory Classification Report:")
        print(results['category_classification_report'])
        
        if 'subcategory_classification_report' in results:
            print("\nSubcategory Classification Report:")
            print(results['subcategory_classification_report'])
        
        # Show feature importance
        feature_importance = pure_ml_categorizer.get_feature_importance()
        if feature_importance:
            print("\nTop 10 Important Features:")
            if 'category' in feature_importance:
                print("\nFor Category Prediction:")
                for feature, importance in feature_importance['category'][:10]:
                    print(f"  {feature}: {importance:.4f}")
            
            if 'subcategory' in feature_importance:
                print("\nFor Subcategory Prediction:")
                for feature, importance in feature_importance['subcategory'][:10]:
                    print(f"  {feature}: {importance:.4f}")
        
        print(f"\nModel saved to: {pure_ml_categorizer.model_path}")
        print("Pure ML categorization is now ready to use!")
        
        return True
        
    except Exception as e:
        logger.error(f"Training failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def main_with_training_data(training_data: List[Dict]) -> bool:
    """Main training function using pre-loaded training data."""
    try:
        logger.info(f"Starting Pure ML training with {len(training_data)} training examples...")
        
        # Convert training data to Transaction objects
        transactions = []
        categories = []
        subcategories = []
        
        for item in training_data:
            try:
                # Create a minimal Transaction object for training
                txn = Transaction(
                    date=datetime.now(),  # Date not used in training
                    description=item.get('description', ''),
                    amount=float(item.get('amount', 0)),
                    balance=None,
                    transaction_type='debit' if float(item.get('amount', 0)) < 0 else 'credit',
                    payment_method=item.get('payment_method', ''),
                    merchant=item.get('merchant', ''),
                    location=item.get('location', ''),
                    raw_description=item.get('description', '')
                )
                
                transactions.append(txn)
                categories.append(item.get('category', ''))
                subcategories.append(item.get('subcategory', ''))
                
            except Exception as e:
                logger.warning(f"Skipping invalid training example: {e}")
                continue
        
        if not transactions:
            logger.error("No valid training transactions found")
            return False
        
        # Check data distribution
        from collections import Counter
        category_counts = Counter(categories)
        subcategory_counts = Counter(subcategories)
        
        logger.info("Category distribution:")
        for category, count in category_counts.most_common():
            logger.info(f"  {category}: {count} transactions")
        
        logger.info("Subcategory distribution:")
        for subcategory, count in subcategory_counts.most_common()[:10]:  # Show top 10
            logger.info(f"  {subcategory}: {count} transactions")
        if len(subcategory_counts) > 10:
            logger.info(f"  ... and {len(subcategory_counts) - 10} more subcategories")
        
        # Check minimum data requirements
        if len(transactions) < 20:
            logger.warning(f"Only {len(transactions)} training examples available. Pure ML training works better with 50+.")
            if len(transactions) < 10:
                logger.error("Need at least 10 training examples for Pure ML training.")
                return False
        
        # Filter out 'other' and 'unknown' categories (can't train on these)
        valid_indices = [i for i, cat in enumerate(categories) 
                        if cat.lower() not in ['unknown', 'other', '']]
        
        if len(valid_indices) != len(transactions):
            logger.info(f"Filtering out {len(transactions) - len(valid_indices)} transactions with invalid categories")
            transactions = [transactions[i] for i in valid_indices]
            categories = [categories[i] for i in valid_indices]
            subcategories = [subcategories[i] for i in valid_indices]
        
        if len(transactions) == 0:
            logger.error("No valid training data after filtering")
            return False
        
        # Create and train Pure ML categorizer
        logger.info("Initializing Pure ML categorizer...")
        pure_ml_categorizer = PureMLCategorizer()
        
        # Train model with both categories and subcategories
        logger.info("Training Pure ML models (category + subcategory)...")
        results = pure_ml_categorizer.train_model(transactions, categories, subcategories)
        
        # Display results
        logger.info("Training completed successfully!")
        logger.info(f"Category test accuracy: {results['category_test_accuracy']:.3f}")
        if 'subcategory_test_accuracy' in results:
            logger.info(f"Subcategory test accuracy: {results['subcategory_test_accuracy']:.3f}")
        logger.info(f"Features: {results['n_features']}")
        
        print("\n" + "="*60)
        print("✅ Pure ML Model Training Complete!")
        print("="*60)
        print(f"📊 Training Data: {len(transactions)} examples")
        print(f"📈 Category Accuracy: {results['category_test_accuracy']:.1%}")
        if 'subcategory_test_accuracy' in results:
            print(f"📈 Subcategory Accuracy: {results['subcategory_test_accuracy']:.1%}")
        print(f"🔧 Features: {results['n_features']}")
        print(f"\n📁 Model saved to: {pure_ml_categorizer.model_path}")
        print("🎯 Pure ML categorization is now ready to use!")
        print("\n📋 Next Steps:")
        print("1. Test the model: python scripts/categorize.py data/processed data/categorized")
        print("2. Check results in the dashboard")
        print("3. Add more training data by manually categorizing transactions")
        
        return True
        
    except Exception as e:
        logger.error(f"Training failed: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == '__main__':
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(levelname)s:%(name)s:%(message)s'
    )
    
    # Command line interface - now supports auto-detection of training data
    if len(sys.argv) > 2:
        print("Usage: python train_ml_model.py [categorized_transactions.json]")
        print("\nPure ML Model Training with Comprehensive Training Data")
        print("Automatically loads training data from multiple sources:")
        print("1. Comprehensive training dataset (if available)")
        print("2. Existing categorized transactions") 
        print("3. User feedback corrections")
        print("\nExamples:")
        print("  python scripts/train_ml_model.py")
        print("  python scripts/train_ml_model.py data/categorized/all_categorized_transactions.json")
        print("\nNote: Training data should contain 'category' and 'subcategory' fields")
        sys.exit(1)
    
    # Use automatic training data loading if no file specified
    if len(sys.argv) == 1:
        print("🔧 Auto-loading training data from multiple sources...")
        training_data = load_training_data()
        
        if not training_data:
            print("❌ No training data found.")
            print("💡 Try running: python scripts/create_training_data.py")
            print("   Or manually categorize some transactions using the dashboard")
            sys.exit(1)
        
        success = main_with_training_data(training_data)
    else:
        # Use legacy single-file loading
        categorized_file = sys.argv[1]
        
        # Check if file exists
        if not os.path.exists(categorized_file):
            print(f"Error: File not found: {categorized_file}")
            sys.exit(1)
        
        success = main(categorized_file)
    
    sys.exit(0 if success else 1)