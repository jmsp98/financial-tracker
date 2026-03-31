"""
Pure Machine Learning categorization system.
No rule-based fallbacks - 100% ML-driven transaction categorization.
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
from sklearn.metrics import classification_report, confusion_matrix
from sklearn.multioutput import MultiOutputClassifier
import joblib

from .parsers import Transaction
from .config import config

logger = logging.getLogger(__name__)


class PureMLTransactionFeatureExtractor:
    """Advanced feature extraction for ML transaction categorization."""
    
    def __init__(self):
        # Enhanced TF-IDF for better text understanding
        self.tfidf = TfidfVectorizer(
            max_features=2000,  # Increased for better representation
            stop_words='english',
            ngram_range=(1, 3),  # Include trigrams for better context
            min_df=1,  # More sensitive to rare but important terms
            max_df=0.9,
            sublinear_tf=True  # Better handling of frequent terms
        )
        
    def extract_features(self, transactions: List[Transaction]) -> pd.DataFrame:
        """
        Extract comprehensive features for ML categorization.
        
        Returns:
            DataFrame with engineered features for ML training
        """
        features = []
        
        for txn in transactions:
            # Clean and prepare text
            description = self._clean_description(txn.description)
            
            # Base transaction features
            feature_dict = {
                'description': description,
                'amount': float(txn.amount),
                'amount_abs': abs(float(txn.amount)),
                'is_debit': float(txn.amount) < 0,
                'is_credit': float(txn.amount) > 0,
                'payment_method': txn.payment_method or 'unknown',
            }
            
            # Amount-based features
            feature_dict.update(self._extract_amount_features(txn.amount))
            
            # Time-based features
            feature_dict.update(self._extract_time_features(txn.date))
            
            # Text-based features
            feature_dict.update(self._extract_text_features(description))
            
            # Payment method features
            feature_dict.update(self._extract_payment_method_features(txn.payment_method))
            
            features.append(feature_dict)
        
        return pd.DataFrame(features)
    
    def _clean_description(self, description: str) -> str:
        """Clean transaction description for better ML processing."""
        if not description:
            return ""
        
        # Remove card numbers and reference codes
        desc = re.sub(r'\d{4,}', '', description)
        desc = re.sub(r'[*]{4,}', '', desc)
        desc = re.sub(r'\b\d{6}\s+\d{8}\b', '', desc)
        
        # Normalize whitespace
        desc = re.sub(r'\s+', ' ', desc).strip()
        
        return desc.lower()
    
    def _extract_amount_features(self, amount: float) -> Dict[str, float]:
        """Extract amount-based features."""
        abs_amount = abs(amount)
        
        return {
            'amount_range_micro': 1.0 if abs_amount <= 5 else 0.0,
            'amount_range_small': 1.0 if 5 < abs_amount <= 25 else 0.0,
            'amount_range_medium': 1.0 if 25 < abs_amount <= 100 else 0.0,
            'amount_range_large': 1.0 if 100 < abs_amount <= 500 else 0.0,
            'amount_range_huge': 1.0 if abs_amount > 500 else 0.0,
            'amount_log': np.log1p(abs_amount),
            'is_round_number': 1.0 if abs_amount % 1 == 0 else 0.0,
        }
    
    def _extract_time_features(self, date: datetime) -> Dict[str, float]:
        """Extract time-based features."""
        return {
            'day_of_week': float(date.weekday()),
            'is_weekend': 1.0 if date.weekday() >= 5 else 0.0,
            'is_month_start': 1.0 if date.day <= 5 else 0.0,
            'is_month_end': 1.0 if date.day >= 25 else 0.0,
            'hour_of_day': float(date.hour) if hasattr(date, 'hour') else 12.0,
        }
    
    def _extract_text_features(self, description: str) -> Dict[str, float]:
        """Extract text-based features."""
        words = description.split()
        
        return {
            'desc_length': len(description),
            'desc_word_count': len(words),
            'desc_avg_word_length': np.mean([len(w) for w in words]) if words else 0,
            'has_numbers': 1.0 if re.search(r'\d', description) else 0.0,
            'has_special_chars': 1.0 if re.search(r'[^\w\s]', description) else 0.0,
        }
    
    def _extract_payment_method_features(self, payment_method: Optional[str]) -> Dict[str, float]:
        """Extract payment method features."""
        method = (payment_method or 'unknown').lower()
        
        # Common payment method categories
        categories = {
            'card_payment': method in ['vis', '))))', 'mc', 'pos'],
            'direct_payment': method in ['dd', 'so', 'bacs'],
            'transfer': method in ['trf', 'tfr', 'fp', 'fps', 'fpi', 'fpo'],
            'cash': method in ['atm', 'csh', 'cdm'],
            'credit': method in ['cr'],
            'online': method in ['obp', 'otr', 'sbt'],
        }
        
        return {f'payment_{cat}': 1.0 if is_cat else 0.0 
                for cat, is_cat in categories.items()}


class PureMLCategorizer:
    """
    Pure Machine Learning transaction categorizer.
    No rule-based fallbacks - uses ML for both categories and subcategories.
    """
    
    def __init__(self, model_path: str = None):
        self.feature_extractor = PureMLTransactionFeatureExtractor()
        self.model_path = model_path or 'data/models/pure_ml_categorizer.pkl'
        self.category_model = None
        self.subcategory_model = None
        self.is_trained = False
        self.label_encoders = {}
        self.tfidf_fitted = False
        
        # Try to load existing model
        self.load_model()
    
    def train_model(self, transactions: List[Transaction], categories: List[str], 
                   subcategories: List[str] = None, test_size: float = 0.2) -> Dict[str, Any]:
        """
        Train pure ML models for category and subcategory prediction.
        
        Args:
            transactions: List of Transaction objects
            categories: List of category labels
            subcategories: List of subcategory labels (optional)
            test_size: Fraction for test set
            
        Returns:
            Dictionary with training results and metrics
        """
        if len(transactions) != len(categories):
            raise ValueError("Transactions and categories must have same length")
        
        logger.info(f"Training pure ML model on {len(transactions)} transactions")
        
        # Extract features
        features_df = self.feature_extractor.extract_features(transactions)
        X = self._prepare_features(features_df)
        
        # Prepare targets
        y_category = np.array(categories)
        y_subcategory = np.array(subcategories) if subcategories else None
        
        # Adjust test_size for small datasets to avoid stratification issues
        n_samples = len(transactions)
        unique_categories = len(set(categories))
        
        # For small datasets, disable stratification to avoid sklearn errors
        if n_samples < 50 or n_samples < unique_categories * 3:
            logger.warning(f"Small dataset ({n_samples} samples, {unique_categories} categories). Disabling stratification.")
            adjusted_test_size = min(test_size, 0.3)  # Cap at 30% for small datasets
            stratify = None
        else:
            adjusted_test_size = test_size
            stratify = y_category
        
        logger.info(f"Using test_size={adjusted_test_size:.2f}, stratify={'enabled' if stratify is not None else 'disabled'}")
        
        # Split data
        if y_subcategory is not None:
            if stratify is not None:
                X_train, X_test, y_cat_train, y_cat_test, y_sub_train, y_sub_test = train_test_split(
                    X, y_category, y_subcategory, test_size=adjusted_test_size, random_state=42, 
                    stratify=stratify
                )
            else:
                X_train, X_test, y_cat_train, y_cat_test, y_sub_train, y_sub_test = train_test_split(
                    X, y_category, y_subcategory, test_size=adjusted_test_size, random_state=42
                )
        else:
            if stratify is not None:
                X_train, X_test, y_cat_train, y_cat_test = train_test_split(
                    X, y_category, test_size=adjusted_test_size, random_state=42, 
                    stratify=stratify
                )
            else:
                X_train, X_test, y_cat_train, y_cat_test = train_test_split(
                    X, y_category, test_size=adjusted_test_size, random_state=42
                )
            y_sub_train = y_sub_test = None
        
        # Train category model
        self.category_model = RandomForestClassifier(
            n_estimators=200,  # More trees for better performance
            max_depth=15,
            min_samples_split=3,
            min_samples_leaf=1,
            max_features='sqrt',
            random_state=42,
            n_jobs=-1  # Use all cores
        )
        
        self.category_model.fit(X_train, y_cat_train)
        
        # Train subcategory model if data provided
        if y_subcategory is not None:
            self.subcategory_model = RandomForestClassifier(
                n_estimators=150,
                max_depth=12,
                min_samples_split=3,
                min_samples_leaf=1,
                max_features='sqrt',
                random_state=42,
                n_jobs=-1
            )
            
            self.subcategory_model.fit(X_train, y_sub_train)
        
        self.is_trained = True
        
        # Evaluate models
        results = self._evaluate_models(X_train, X_test, y_cat_train, y_cat_test, 
                                       y_sub_train, y_sub_test)
        
        # Save model
        self.save_model()
        
        logger.info(f"Pure ML model trained - Category accuracy: {results['category_test_accuracy']:.3f}")
        if self.subcategory_model:
            logger.info(f"Subcategory accuracy: {results['subcategory_test_accuracy']:.3f}")
        
        return results
    
    def _prepare_features(self, features_df: pd.DataFrame) -> np.ndarray:
        """Convert feature DataFrame to ML-ready array."""
        # Separate text and numeric features
        text_features = ['description', 'payment_method']
        numeric_features = [col for col in features_df.columns if col not in text_features]
        
        # Combine text for TF-IDF
        combined_text = (features_df['description'].fillna('') + ' ' + 
                        features_df['payment_method'].fillna('')).str.strip()
        
        # Fit TF-IDF on first call
        if not self.tfidf_fitted:
            text_vectors = self.feature_extractor.tfidf.fit_transform(combined_text).toarray()
            self.tfidf_fitted = True
        else:
            text_vectors = self.feature_extractor.tfidf.transform(combined_text).toarray()
        
        # Get numeric features (only float/int types)
        numeric_array = features_df[numeric_features].fillna(0).astype(float).values
        
        # Combine features
        X = np.hstack([text_vectors, numeric_array])
        
        return X
    
    def _evaluate_models(self, X_train, X_test, y_cat_train, y_cat_test, 
                        y_sub_train=None, y_sub_test=None) -> Dict[str, Any]:
        """Evaluate trained models and return metrics."""
        results = {}
        
        # Category model evaluation
        cat_train_score = self.category_model.score(X_train, y_cat_train)
        cat_test_score = self.category_model.score(X_test, y_cat_test)
        cat_pred = self.category_model.predict(X_test)
        
        results.update({
            'category_train_accuracy': cat_train_score,
            'category_test_accuracy': cat_test_score,
            'category_classification_report': classification_report(y_cat_test, cat_pred),
            'n_features': X_train.shape[1],
            'n_samples': X_train.shape[0]
        })
        
        # Subcategory model evaluation
        if self.subcategory_model and y_sub_train is not None:
            sub_train_score = self.subcategory_model.score(X_train, y_sub_train)
            sub_test_score = self.subcategory_model.score(X_test, y_sub_test)
            sub_pred = self.subcategory_model.predict(X_test)
            
            results.update({
                'subcategory_train_accuracy': sub_train_score,
                'subcategory_test_accuracy': sub_test_score,
                'subcategory_classification_report': classification_report(y_sub_test, sub_pred)
            })
        
        return results
    
    def predict_category(self, transaction: Transaction, 
                        return_confidence: bool = False) -> Tuple[str, Optional[str], float]:
        """
        Predict category and subcategory for a transaction using pure ML.
        
        Args:
            transaction: Transaction object
            return_confidence: Whether to return confidence scores
            
        Returns:
            Tuple of (category, subcategory, confidence)
        """
        if not self.is_trained or self.category_model is None:
            # Pure ML approach - if no model, return 'other' for manual training
            logger.warning("ML model not trained. Cannot categorize transaction.")
            return 'other', 'other', 0.0
        
        try:
            # Extract features for single transaction
            features_df = self.feature_extractor.extract_features([transaction])
            X = self._prepare_features(features_df)
            
            # Get category prediction
            category = self.category_model.predict(X)[0]
            category_proba = self.category_model.predict_proba(X)[0]
            category_confidence = category_proba.max()
            
            # Get subcategory prediction if model exists
            subcategory = 'other'
            subcategory_confidence = 0.0
            
            if self.subcategory_model is not None:
                subcategory = self.subcategory_model.predict(X)[0]
                subcategory_proba = self.subcategory_model.predict_proba(X)[0]
                subcategory_confidence = subcategory_proba.max()
            
            # Combined confidence (average of both predictions)
            combined_confidence = (category_confidence + subcategory_confidence) / 2 if self.subcategory_model else category_confidence
            
            logger.debug(f"ML prediction: {transaction.description[:50]} -> {category}/{subcategory} (conf: {combined_confidence:.3f})")
            
            return category, subcategory, combined_confidence
            
        except Exception as e:
            logger.error(f"Pure ML prediction failed for transaction {transaction.description}: {e}")
            # Pure ML approach - return 'other' for manual training instead of unknown
            return 'other', 'other', 0.0
    
    def categorize_transactions(self, transactions: List[Transaction]) -> List[Dict]:
        """
        Categorize transactions using pure ML approach.
        
        Args:
            transactions: List of Transaction objects
            
        Returns:
            List of categorized transaction dictionaries
        """
        categorized = []
        
        for transaction in transactions:
            category, subcategory, confidence = self.predict_category(transaction)
            
            categorized_txn = {
                'date': transaction.date.isoformat(),
                'description': transaction.description,
                'amount': transaction.amount,
                'balance': transaction.balance,
                'transaction_type': transaction.transaction_type,
                'payment_method': transaction.payment_method,
                'reference': transaction.reference if hasattr(transaction, 'reference') else None,
                'category': category,
                'subcategory': subcategory,
                'ml_confidence': round(confidence, 3),
                'categorization_method': 'pure_ml'
            }
            
            categorized.append(categorized_txn)
        
        return categorized
    
    def save_model(self):
        """Save the trained model to disk."""
        if not self.is_trained:
            logger.warning("Cannot save untrained model")
            return
        
        try:
            os.makedirs(os.path.dirname(self.model_path), exist_ok=True)
            
            model_data = {
                'category_model': self.category_model,
                'subcategory_model': self.subcategory_model,
                'tfidf_vectorizer': self.feature_extractor.tfidf,
                'is_trained': self.is_trained,
                'tfidf_fitted': self.tfidf_fitted,
                'model_type': 'pure_ml'
            }
            
            with open(self.model_path, 'wb') as f:
                pickle.dump(model_data, f)
            
            logger.info(f"Pure ML model saved to {self.model_path}")
            
        except Exception as e:
            logger.error(f"Failed to save model: {e}")
    
    def load_model(self):
        """Load a trained model from disk."""
        if not os.path.exists(self.model_path):
            logger.info(f"No existing model found at {self.model_path}")
            return
        
        try:
            with open(self.model_path, 'rb') as f:
                model_data = pickle.load(f)
            
            self.category_model = model_data.get('category_model')
            self.subcategory_model = model_data.get('subcategory_model')
            self.feature_extractor.tfidf = model_data.get('tfidf_vectorizer')
            self.is_trained = model_data.get('is_trained', False)
            self.tfidf_fitted = model_data.get('tfidf_fitted', False)
            
            if self.is_trained:
                logger.info(f"Pure ML model loaded from {self.model_path}")
            
        except Exception as e:
            logger.error(f"Failed to load model: {e}")
            self.is_trained = False
    
    def get_feature_importance(self, top_n: int = 20) -> Dict[str, List[Tuple[str, float]]]:
        """
        Get feature importance for trained models.
        
        Args:
            top_n: Number of top features to return
            
        Returns:
            Dictionary with feature importance for each model
        """
        if not self.is_trained:
            return {}
        
        results = {}
        
        if self.category_model:
            # Get feature names (TF-IDF features + numeric features)
            tfidf_features = self.feature_extractor.tfidf.get_feature_names_out()
            numeric_features = [
                'amount', 'amount_abs', 'is_debit', 'is_credit', 'amount_range_micro',
                'amount_range_small', 'amount_range_medium', 'amount_range_large',
                'amount_range_huge', 'amount_log', 'is_round_number', 'day_of_week',
                'is_weekend', 'is_month_start', 'is_month_end', 'hour_of_day',
                'desc_length', 'desc_word_count', 'desc_avg_word_length',
                'has_numbers', 'has_special_chars', 'payment_card_payment',
                'payment_direct_payment', 'payment_transfer', 'payment_cash',
                'payment_credit', 'payment_online'
            ]
            
            all_features = list(tfidf_features) + numeric_features
            
            # Category model importance
            importances = self.category_model.feature_importances_
            feature_importance = list(zip(all_features, importances))
            feature_importance.sort(key=lambda x: x[1], reverse=True)
            results['category'] = feature_importance[:top_n]
            
            # Subcategory model importance
            if self.subcategory_model:
                sub_importances = self.subcategory_model.feature_importances_
                sub_feature_importance = list(zip(all_features, sub_importances))
                sub_feature_importance.sort(key=lambda x: x[1], reverse=True)
                results['subcategory'] = sub_feature_importance[:top_n]
        
        return results


# Convenience function for backwards compatibility
def create_pure_ml_categorizer() -> PureMLCategorizer:
    """Create a pure ML categorizer instance."""
    return PureMLCategorizer()