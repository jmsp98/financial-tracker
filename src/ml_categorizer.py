"""
Machine Learning categorization system with fallback to rule-based categorization.
Uses scikit-learn for local, free ML processing - no API costs.
"""

import os
import pickle
import logging
from typing import List, Dict, Optional, Tuple, Any
from datetime import datetime
import re

import pandas as pd
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.ensemble import RandomForestClassifier
from sklearn.naive_bayes import MultinomialNB
from sklearn.pipeline import Pipeline
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.metrics import classification_report
import joblib

from .categorizer import RuleBasedCategorizer
from .parsers import Transaction
from .config import config

logger = logging.getLogger(__name__)


class TransactionFeatureExtractor:
    """Extract features from transactions for ML training."""
    
    def __init__(self):
        self.tfidf = TfidfVectorizer(
            max_features=1000,
            stop_words='english',
            ngram_range=(1, 2),
            min_df=2,
            max_df=0.8
        )
        
    def extract_features(self, transactions: List[Transaction]) -> pd.DataFrame:
        """
        Extract features from transactions for ML.
        
        Args:
            transactions: List of Transaction objects
            
        Returns:
            DataFrame with extracted features
        """
        features_data = []
        
        for txn in transactions:
            # Text features
            description = txn.description.lower()
            merchant = getattr(txn, 'merchant', '') or ''
            
            # Amount features
            amount_abs = abs(txn.amount)
            amount_log = np.log(amount_abs + 1)  # Log transform, +1 to avoid log(0)
            
            # Payment method features
            payment_method = getattr(txn, 'payment_method', '') or ''
            is_card = 1 if payment_method in ['VIS', 'CONTACTLESS'] else 0
            is_direct_debit = 1 if payment_method == 'DD' else 0
            is_credit = 1 if payment_method == 'CR' else 0
            
            # Time features
            day_of_week = txn.date.weekday()
            hour = txn.date.hour if hasattr(txn.date, 'hour') else 12  # Default noon
            is_weekend = 1 if day_of_week >= 5 else 0
            
            # Transaction type
            is_debit = 1 if txn.transaction_type == 'debit' else 0
            
            # Combined text for TF-IDF
            combined_text = f"{description} {merchant}".strip()
            
            features_data.append({
                'combined_text': combined_text,
                'amount_abs': amount_abs,
                'amount_log': amount_log,
                'is_card': is_card,
                'is_direct_debit': is_direct_debit,
                'is_credit': is_credit,
                'day_of_week': day_of_week,
                'hour': hour,
                'is_weekend': is_weekend,
                'is_debit': is_debit,
                'payment_method': payment_method
            })
            
        return pd.DataFrame(features_data)


class MLCategorizer:
    """
    Machine Learning transaction categorizer with rule-based fallback.
    Uses local ML models - no API costs.
    """
    
    def __init__(self, model_path: str = None):
        self.rule_based_categorizer = RuleBasedCategorizer()
        self.feature_extractor = TransactionFeatureExtractor()
        self.model_path = model_path or 'data/models/transaction_categorizer.pkl'
        self.model = None
        self.categories = config.get_categories()
        self.is_trained = False
        
        # Try to load existing model
        self.load_model()
        
    def _prepare_features(self, features_df: pd.DataFrame) -> np.ndarray:
        """Prepare features for ML model."""
        # Extract text features using TF-IDF
        if hasattr(self.feature_extractor.tfidf, 'vocabulary_'):
            text_features = self.feature_extractor.tfidf.transform(features_df['combined_text'])
        else:
            text_features = self.feature_extractor.tfidf.fit_transform(features_df['combined_text'])
        
        # Numerical features
        numerical_features = features_df[[
            'amount_log', 'is_card', 'is_direct_debit', 'is_credit',
            'day_of_week', 'hour', 'is_weekend', 'is_debit'
        ]].values
        
        # Combine text and numerical features
        from scipy.sparse import hstack
        if hasattr(text_features, 'toarray'):
            combined_features = np.hstack([text_features.toarray(), numerical_features])
        else:
            combined_features = np.hstack([text_features, numerical_features])
            
        return combined_features
    
    def train_model(self, transactions: List[Transaction], categories: List[str], 
                   test_size: float = 0.2) -> Dict[str, Any]:
        """
        Train ML model on categorized transactions.
        
        Args:
            transactions: List of Transaction objects
            categories: List of category labels (same length as transactions)
            test_size: Fraction of data to use for testing
            
        Returns:
            Training metrics and results
        """
        if len(transactions) != len(categories):
            raise ValueError("Transactions and categories lists must be same length")
            
        logger.info(f"Training ML model on {len(transactions)} transactions")
        
        # Extract features
        features_df = self.feature_extractor.extract_features(transactions)
        X = self._prepare_features(features_df)
        y = np.array(categories)
        
        # Split data
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=test_size, random_state=42, stratify=y
        )
        
        # Train model (Random Forest for interpretability)
        self.model = RandomForestClassifier(
            n_estimators=100,
            max_depth=10,
            min_samples_split=5,
            min_samples_leaf=2,
            random_state=42
        )
        
        self.model.fit(X_train, y_train)
        self.is_trained = True
        
        # Evaluate model
        train_score = self.model.score(X_train, y_train)
        test_score = self.model.score(X_test, y_test)
        cv_scores = cross_val_score(self.model, X, y, cv=5)
        
        # Predictions for detailed metrics
        y_pred = self.model.predict(X_test)
        
        results = {
            'train_accuracy': train_score,
            'test_accuracy': test_score,
            'cv_mean': cv_scores.mean(),
            'cv_std': cv_scores.std(),
            'n_features': X.shape[1],
            'n_samples': X.shape[0],
            'classification_report': classification_report(y_test, y_pred)
        }
        
        logger.info(f"Model trained - Test accuracy: {test_score:.3f}, CV: {cv_scores.mean():.3f} ±{cv_scores.std():.3f}")
        
        # Save model
        self.save_model()
        
        return results
    
    def predict_category(self, transaction: Transaction, confidence_threshold: float = 0.6) -> Tuple[str, float]:
        """
        Predict category for a single transaction.
        
        Args:
            transaction: Transaction object to categorize
            confidence_threshold: Minimum confidence for ML prediction
            
        Returns:
            Tuple of (category, confidence)
        """
        if not self.is_trained or self.model is None:
            # Fall back to rule-based categorization
            category = self.rule_based_categorizer.categorize_transaction(transaction)
            return category, 0.0
        
        try:
            # Extract features for single transaction
            features_df = self.feature_extractor.extract_features([transaction])
            X = self._prepare_features(features_df)
            
            # Get prediction and confidence
            prediction = self.model.predict(X)[0]
            probabilities = self.model.predict_proba(X)[0]
            confidence = probabilities.max()
            
            # Use ML prediction if confidence is high enough
            if confidence >= confidence_threshold:
                return prediction, confidence
            else:
                # Fall back to rule-based categorization
                logger.debug(f"ML confidence {confidence:.2f} below threshold {confidence_threshold}, using rule-based")
                category = self.rule_based_categorizer.categorize_transaction(transaction)
                return category, 0.0
                
        except Exception as e:
            logger.warning(f"ML categorization failed: {e}, falling back to rule-based")
            category = self.rule_based_categorizer.categorize_transaction(transaction)
            return category, 0.0
    
    def categorize_transactions(self, transactions: List[Transaction]) -> List[Dict]:
        """
        Categorize a list of transactions using ML with rule-based fallback.
        
        Args:
            transactions: List of Transaction objects
            
        Returns:
            List of transaction dictionaries with categories and confidence
        """
        categorized_transactions = []
        ml_used_count = 0
        
        for transaction in transactions:
            category, confidence = self.predict_category(transaction)
            
            if confidence > 0:
                ml_used_count += 1
            
            transaction_dict = {
                'date': transaction.date.isoformat() if isinstance(transaction.date, datetime) else transaction.date,
                'description': transaction.description,
                'amount': transaction.amount,
                'balance': transaction.balance if transaction.balance is not None else 0.0,
                'type': transaction.transaction_type,
                'category': category,
                'ml_confidence': confidence,
                'categorization_method': 'ml' if confidence > 0 else 'rule_based'
            }
            
            # Add additional fields if available
            if hasattr(transaction, 'payment_method') and transaction.payment_method:
                transaction_dict['payment_method'] = transaction.payment_method
            if hasattr(transaction, 'merchant') and transaction.merchant:
                transaction_dict['merchant'] = transaction.merchant
            if hasattr(transaction, 'location') and transaction.location:
                transaction_dict['location'] = transaction.location
                
            categorized_transactions.append(transaction_dict)
        
        logger.info(f"Categorized {len(transactions)} transactions: {ml_used_count} using ML, {len(transactions) - ml_used_count} using rules")
        
        return categorized_transactions
    
    def save_model(self):
        """Save trained model to disk."""
        if self.model is None:
            logger.warning("No model to save")
            return
        
        os.makedirs(os.path.dirname(self.model_path), exist_ok=True)
        
        model_data = {
            'model': self.model,
            'feature_extractor': self.feature_extractor,
            'is_trained': self.is_trained
        }
        
        joblib.dump(model_data, self.model_path)
        logger.info(f"Model saved to {self.model_path}")
    
    def load_model(self):
        """Load trained model from disk."""
        if os.path.exists(self.model_path):
            try:
                model_data = joblib.load(self.model_path)
                self.model = model_data['model']
                self.feature_extractor = model_data['feature_extractor']
                self.is_trained = model_data.get('is_trained', False)
                logger.info(f"Model loaded from {self.model_path}")
                return True
            except Exception as e:
                logger.warning(f"Failed to load model: {e}")
                return False
        return False
    
    def get_model_info(self) -> Dict[str, Any]:
        """Get information about the current model."""
        return {
            'is_trained': self.is_trained,
            'model_path': self.model_path,
            'model_exists': os.path.exists(self.model_path),
            'fallback_categorizer': 'rule_based'
        }


class HybridCategorizer:
    """
    Hybrid categorizer that combines ML and rule-based approaches.
    This is the main categorizer class that should be used.
    """
    
    def __init__(self, use_ml: bool = True, ml_confidence_threshold: float = 0.6):
        self.use_ml = use_ml
        self.ml_confidence_threshold = ml_confidence_threshold
        
        if use_ml:
            self.ml_categorizer = MLCategorizer()
        else:
            self.rule_based_categorizer = RuleBasedCategorizer()
    
    def categorize_transactions(self, transactions: List[Transaction]) -> List[Dict]:
        """
        Categorize transactions using the best available method.
        
        Args:
            transactions: List of Transaction objects
            
        Returns:
            List of categorized transaction dictionaries
        """
        if self.use_ml and hasattr(self, 'ml_categorizer'):
            return self.ml_categorizer.categorize_transactions(transactions)
        else:
            return self.rule_based_categorizer.categorize_transactions(transactions)
    
    def train_model_if_possible(self, transactions: List[Transaction], categories: List[str]) -> Optional[Dict]:
        """
        Train ML model if enough data is available.
        
        Args:
            transactions: List of Transaction objects
            categories: List of category labels
            
        Returns:
            Training results or None if not possible
        """
        if not self.use_ml or len(transactions) < 50:  # Need minimum data
            logger.info(f"Not enough data for ML training ({len(transactions)} transactions), using rule-based only")
            return None
        
        if hasattr(self, 'ml_categorizer'):
            return self.ml_categorizer.train_model(transactions, categories)
        
        return None