#!/usr/bin/env python3
"""
Demo script showing Pure ML categorization system.
Creates sample transactions and demonstrates the categorization process.
"""

import os
import sys
import json
import logging
from datetime import datetime, timedelta

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.pure_ml_categorizer import PureMLCategorizer
from src.parsers import Transaction

logger = logging.getLogger(__name__)


def create_sample_transactions():
    """Create sample transactions for testing."""
    base_date = datetime.now() - timedelta(days=30)
    
    transactions = [
        Transaction(
            date=base_date + timedelta(days=1),
            description="VIS TESCO STORE",
            amount=-45.67,
            balance=1234.33,
            transaction_type="debit",
            payment_method="VIS",
            merchant="VIS TESCO STORE",
            location=None,
            raw_description="VIS TESCO STORE LONDON"
        ),
        Transaction(
            date=base_date + timedelta(days=2),
            description="))) STARBUCKS COFFEE",
            amount=-4.50,
            balance=1229.83,
            transaction_type="debit", 
            payment_method="))))",
            merchant="))) STARBUCKS COFFEE",
            location=None,
            raw_description="))) STARBUCKS COFFEE CENTRAL LONDON"
        ),
        Transaction(
            date=base_date + timedelta(days=3),
            description="DD BRITISH GAS",
            amount=-89.45,
            balance=1140.38,
            transaction_type="debit",
            payment_method="DD",
            merchant="DD BRITISH GAS",
            location=None,
            raw_description="DD BRITISH GAS"
        ),
        Transaction(
            date=base_date + timedelta(days=5),
            description="CR SALARY PAYMENT",
            amount=2500.00,
            balance=3640.38,
            transaction_type="credit",
            payment_method="CR",
            merchant="CR SALARY PAYMENT",
            location=None,
            raw_description="CR SALARY PAYMENT"
        ),
        Transaction(
            date=base_date + timedelta(days=7),
            description="VIS AMAZON.CO.UK",
            amount=-29.99,
            balance=3610.39,
            transaction_type="debit",
            payment_method="VIS",
            merchant="VIS AMAZON.CO.UK",
            location=None,
            raw_description="VIS AMAZON.CO.UK ONLINE"
        )
    ]
    
    return transactions


def demo_pure_ml_categorization():
    """Demonstrate pure ML categorization system."""
    print("🤖 Pure ML Categorization Demo")
    print("=" * 50)
    
    # Create categorizer
    categorizer = PureMLCategorizer()
    print(f"✓ Pure ML categorizer loaded")
    print(f"  Model trained: {categorizer.is_trained}")
    print(f"  Model path: {categorizer.model_path}")
    
    # Create sample transactions  
    transactions = create_sample_transactions()
    print(f"\n📊 Created {len(transactions)} sample transactions")
    
    # Categorize transactions
    print(f"\n🔄 Categorizing transactions (Pure ML approach)")
    categorized = categorizer.categorize_transactions(transactions)
    
    # Display results
    print(f"\n📋 Categorization Results:")
    print("-" * 80)
    
    for i, txn in enumerate(categorized):
        status = "✓ ML" if txn['category'] != 'unknown' else "⚠ Unknown"
        confidence = txn.get('ml_confidence', 0)
        
        print(f"{status} | {txn['description'][:30]:<30} | "
              f"{txn['category']:<12} | {txn['subcategory']:<15} | "
              f"Conf: {confidence:.3f}")
    
    # Summary statistics
    ml_predictions = [t for t in categorized if t['category'] != 'unknown']
    unknown_count = len(categorized) - len(ml_predictions)
    
    print("-" * 80)
    print(f"Summary: {len(ml_predictions)} ML predictions, {unknown_count} unknown")
    
    if ml_predictions:
        avg_confidence = sum(t.get('ml_confidence', 0) for t in ml_predictions) / len(ml_predictions)
        print(f"Average ML confidence: {avg_confidence:.3f}")
    
    # Save demo results
    output_file = "data/demo_pure_ml_results.json"
    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    
    with open(output_file, 'w') as f:
        json.dump(categorized, f, indent=2, default=str)
    
    print(f"\n💾 Results saved to: {output_file}")
    
    if not categorizer.is_trained:
        print("\n💡 Tip: Train the ML model using labeled data:")
        print("   python scripts/train_ml_model.py <categorized_transactions.json>")
    
    return categorized


if __name__ == '__main__':
    logging.basicConfig(
        level=logging.INFO,
        format='%(levelname)s: %(message)s'
    )
    
    try:
        results = demo_pure_ml_categorization()
        print(f"\n🎉 Pure ML categorization demo completed!")
        
    except Exception as e:
        print(f"\n❌ Demo failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)