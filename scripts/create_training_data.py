#!/usr/bin/env python3
"""
Create training data from historical categorizations for ML model training.
This script is safe to run - it will never commit training data to git.
"""

import json
import os
import sys
import logging
from datetime import datetime
from typing import List, Dict, Any
from pathlib import Path

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


class TrainingDataCreator:
    """Creates training data from various sources for ML model training."""
    
    def __init__(self):
        self.project_root = Path(__file__).parent.parent
        self.data_dir = self.project_root / "data"
        self.training_dir = self.project_root / "training_data"
        self.training_dir.mkdir(exist_ok=True)
        
        # Ensure training directory is ignored by git
        gitignore_path = self.project_root / ".gitignore"
        self._ensure_gitignore_excludes_training(gitignore_path)
    
    def _ensure_gitignore_excludes_training(self, gitignore_path: Path):
        """Ensure .gitignore excludes training data."""
        if not gitignore_path.exists():
            return
        
        with open(gitignore_path, 'r') as f:
            content = f.read()
        
        if "training_data/" not in content:
            logger.info("Adding training_data/ to .gitignore")
            with open(gitignore_path, 'a') as f:
                f.write("\n# Training Data - NEVER COMMIT\ntraining_data/\n")
    
    def create_sample_training_data(self) -> Dict[str, Any]:
        """
        Create sample training data based on common UK transaction patterns.
        This provides a good starting point for ML training.
        """
        sample_training_data = [
            # Food & Dining
            {"description": "TESCO STORES", "category": "Groceries", "subcategory": "Supermarket"},
            {"description": "SAINSBURY'S", "category": "Groceries", "subcategory": "Supermarket"},
            {"description": "MARKS & SPENCER", "category": "Groceries", "subcategory": "Supermarket"},
            {"description": "CO-OP GROUP", "category": "Groceries", "subcategory": "Supermarket"},
            {"description": "MCDONALDS", "category": "Food & Dining", "subcategory": "Fast Food"},
            {"description": "THE SAMPLE_PUB", "category": "Food & Dining", "subcategory": "Pub"},
            {"description": "STARBUCKS", "category": "Food & Dining", "subcategory": "Coffee"},
            {"description": "COSTA COFFEE", "category": "Food & Dining", "subcategory": "Coffee"},
            
            # Transport
            {"description": "TFL TRAVEL", "category": "Transport", "subcategory": "Public Transport"},
            {"description": "UBER", "category": "Transport", "subcategory": "Taxi"},
            {"description": "BP ", "category": "Transport", "subcategory": "Fuel"},
            {"description": "SHELL", "category": "Transport", "subcategory": "Fuel"},
            {"description": "ESSO", "category": "Transport", "subcategory": "Fuel"},
            {"description": "TRAINLINE", "category": "Transport", "subcategory": "Train"},
            
            # Bills & Utilities  
            {"description": "EE LIMITED", "category": "Bills & Utilities", "subcategory": "Mobile Phone"},
            {"description": "VIRGIN MEDIA", "category": "Bills & Utilities", "subcategory": "Internet"},
            {"description": "BT GROUP", "category": "Bills & Utilities", "subcategory": "Phone/Internet"},
            {"description": "OCTOPUS ENERGY", "category": "Bills & Utilities", "subcategory": "Electricity"},
            {"description": "THAMES WATER", "category": "Bills & Utilities", "subcategory": "Water"},
            {"description": "BRITISH GAS", "category": "Bills & Utilities", "subcategory": "Gas"},
            
            # Shopping
            {"description": "AMAZON", "category": "Shopping", "subcategory": "Online"},
            {"description": "ARGOS", "category": "Shopping", "subcategory": "General"},
            {"description": "JOHN LEWIS", "category": "Shopping", "subcategory": "Department Store"},
            {"description": "CURRYS", "category": "Shopping", "subcategory": "Electronics"},
            {"description": "ZARA", "category": "Shopping", "subcategory": "Clothing"},
            {"description": "H&M", "category": "Shopping", "subcategory": "Clothing"},
            
            # Entertainment
            {"description": "NETFLIX", "category": "Entertainment", "subcategory": "Streaming"},
            {"description": "SPOTIFY", "category": "Entertainment", "subcategory": "Music"},
            {"description": "AMAZON PRIME", "category": "Entertainment", "subcategory": "Streaming"},
            {"description": "CINEMA", "category": "Entertainment", "subcategory": "Movies"},
            {"description": "ODEON", "category": "Entertainment", "subcategory": "Movies"},
            
            # Health & Medical
            {"description": "BOOTS", "category": "Health & Medical", "subcategory": "Pharmacy"},
            {"description": "SUPERDRUG", "category": "Health & Medical", "subcategory": "Pharmacy"},
            {"description": "NHS", "category": "Health & Medical", "subcategory": "Healthcare"},
            
            # Banking & Finance
            {"description": "INTERNET TRANSFER", "category": "Transfer", "subcategory": "Internal"},
            {"description": "FASTER PAYMENT", "category": "Transfer", "subcategory": "Bank Transfer"},
            {"description": "DIRECT DEBIT", "category": "Bills & Utilities", "subcategory": "Automatic Payment"},
            {"description": "STANDING ORDER", "category": "Transfer", "subcategory": "Regular Payment"},
            
            # Income
            {"description": "SALARY", "category": "Income", "subcategory": "Salary"},
            {"description": "REFUND", "category": "Income", "subcategory": "Refund"},
            {"description": "INTEREST", "category": "Income", "subcategory": "Interest"},
            
            # Education
            {"description": "UNIVERSITY", "category": "Education", "subcategory": "Tuition"},
            {"description": "STUDENT LOAN", "category": "Education", "subcategory": "Loan"},
            {"description": "COLLEGE", "category": "Education", "subcategory": "Tuition"},
        ]
        
        return {
            "created_date": datetime.now().isoformat(),
            "source": "sample_uk_patterns",
            "total_samples": len(sample_training_data),
            "training_data": sample_training_data
        }
    
    def load_existing_categorized_data(self) -> List[Dict[str, Any]]:
        """Load existing categorized transactions that aren't 'other'."""
        training_transactions = []
        
        # Check categorized data directory
        categorized_files = [
            self.data_dir / "categorized" / "all_categorized_transactions.json",
            self.data_dir / "categorized" / "categorized_all_transactions.json"
        ]
        
        for file_path in categorized_files:
            if file_path.exists():
                logger.info(f"Loading categorized data from {file_path}")
                try:
                    with open(file_path, 'r') as f:
                        transactions = json.load(f)
                    
                    # Filter for transactions with meaningful categories
                    meaningful_categories = []
                    for txn in transactions:
                        category = txn.get('category', '').lower()
                        subcategory = txn.get('subcategory', '').lower()
                        
                        # Skip 'other' and 'unknown' categories
                        if category not in ['other', 'unknown', ''] and subcategory not in ['other', 'unknown', '']:
                            meaningful_categories.append({
                                'description': txn.get('description', ''),
                                'category': txn.get('category', ''),
                                'subcategory': txn.get('subcategory', ''),
                                'amount': txn.get('amount', 0),
                                'date': txn.get('date', ''),
                                'payment_method': txn.get('payment_method', ''),
                            })
                    
                    if meaningful_categories:
                        logger.info(f"Found {len(meaningful_categories)} meaningfully categorized transactions")
                        training_transactions.extend(meaningful_categories)
                        break  # Use the first file with data
                
                except Exception as e:
                    logger.warning(f"Could not load {file_path}: {e}")
        
        return training_transactions
    
    def load_user_feedback(self) -> List[Dict[str, Any]]:
        """Load user feedback corrections."""
        feedback_file = self.data_dir / "categorized" / "user_feedback.json"
        
        if not feedback_file.exists():
            logger.info("No user feedback file found")
            return []
        
        try:
            with open(feedback_file, 'r') as f:
                feedback_data = json.load(f)
            
            training_data = []
            for entry in feedback_data:
                if entry.get('corrected_category') and entry.get('corrected_category').lower() not in ['other', 'unknown']:
                    training_data.append({
                        'description': entry.get('original_description', ''),
                        'category': entry.get('corrected_category', ''),
                        'subcategory': entry.get('corrected_subcategory', ''),
                        'amount': entry.get('amount', 0),
                        'date': entry.get('transaction_date', ''),
                        'source': 'user_feedback'
                    })
            
            logger.info(f"Loaded {len(training_data)} training examples from user feedback")
            return training_data
        
        except Exception as e:
            logger.warning(f"Could not load user feedback: {e}")
            return []
    
    def create_comprehensive_training_data(self):
        """Create comprehensive training data from all available sources."""
        logger.info("Creating comprehensive training data...")
        
        # Collect training data from all sources
        sample_data = self.create_sample_training_data()
        existing_data = self.load_existing_categorized_data()
        user_feedback_data = self.load_user_feedback()
        
        # Combine all training data
        all_training_data = []
        
        # Add sample data
        all_training_data.extend(sample_data['training_data'])
        logger.info(f"Added {len(sample_data['training_data'])} sample training examples")
        
        # Add existing categorized data
        all_training_data.extend(existing_data)
        logger.info(f"Added {len(existing_data)} existing categorized transactions")
        
        # Add user feedback
        all_training_data.extend(user_feedback_data)
        logger.info(f"Added {len(user_feedback_data)} user feedback examples")
        
        # Create comprehensive dataset
        comprehensive_dataset = {
            "created_date": datetime.now().isoformat(),
            "sources": ["sample_uk_patterns", "existing_categorized_data", "user_feedback"],
            "total_training_examples": len(all_training_data),
            "training_data": all_training_data
        }
        
        # Save to training directory (excluded from git)
        output_file = self.training_dir / "comprehensive_training_data.json"
        with open(output_file, 'w') as f:
            json.dump(comprehensive_dataset, f, indent=2)
        
        logger.info(f"✅ Created comprehensive training dataset with {len(all_training_data)} examples")
        logger.info(f"📁 Saved to: {output_file}")
        logger.info("🔒 This file is excluded from git to protect your financial privacy")
        
        # Create category breakdown
        categories = {}
        for item in all_training_data:
            cat = item.get('category', 'Unknown')
            categories[cat] = categories.get(cat, 0) + 1
        
        logger.info("📊 Category breakdown:")
        for cat, count in sorted(categories.items()):
            logger.info(f"   {cat}: {count} examples")
        
        return output_file


def main():
    """Main function to create training data."""
    creator = TrainingDataCreator()
    
    logger.info("🔧 Creating training data for ML model...")
    logger.info("🔒 All training data is excluded from git for privacy")
    
    try:
        training_file = creator.create_comprehensive_training_data()
        
        print("\n" + "="*60)
        print("✅ Training Data Creation Complete!")
        print("="*60)
        print(f"📁 Training data saved to: {training_file}")
        print("🔒 This file is excluded from git to protect your privacy")
        print("\n📋 Next Steps:")
        print("1. Review the training data if needed")
        print("2. Run: python scripts/train_ml_model.py")
        print("3. Test the model: python scripts/categorize.py data/processed data/categorized")
        print("\n💡 To add more training examples:")
        print("- Use the dashboard to manually categorize transactions")
        print("- The ML model will learn from your manual categorizations")
        
    except Exception as e:
        logger.error(f"Failed to create training data: {e}")
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main())