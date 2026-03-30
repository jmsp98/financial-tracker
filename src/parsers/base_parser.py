"""
Abstract base parser for bank statement processing.
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Optional, Tuple
from datetime import datetime
from dataclasses import dataclass
import re
import logging

logger = logging.getLogger(__name__)


@dataclass
class Transaction:
    """Enhanced transaction model with additional metadata."""
    date: datetime
    description: str
    amount: float  # Negative for debits, positive for credits
    balance: Optional[float]
    transaction_type: str  # 'debit' or 'credit'
    payment_method: Optional[str]  # 'VIS', 'CONTACTLESS', 'DD', 'CR', etc.
    merchant: str  # Clean merchant name
    location: Optional[str]  # Transaction location if available
    raw_description: str  # Full original text for debugging
    reference: Optional[str] = None  # Lines 2+ from multi-line PDF transactions (location, card ref, etc.)


class BaseBankParser(ABC):
    """Abstract base class for all bank statement parsers."""
    
    def __init__(self):
        self.bank_name = self.get_bank_name()
        self.supported_patterns = self.get_bank_patterns()
    
    @abstractmethod
    def get_bank_name(self) -> str:
        """Return the name of the bank this parser handles."""
        pass
    
    @abstractmethod 
    def get_bank_patterns(self) -> List[str]:
        """Return patterns that identify this bank's statements."""
        pass
    
    @abstractmethod
    def parse_transactions_from_text(self, text: str) -> List[Transaction]:
        """Parse transactions from extracted PDF text."""
        pass
    
    @abstractmethod
    def parse_transactions_from_table(self, tables: List[List[List[str]]]) -> List[Transaction]:
        """Parse transactions from extracted PDF tables."""
        pass
    
    def parse_transactions(self, text: str, tables: Optional[List[List[List[str]]]] = None) -> List[Transaction]:
        """
        Main entry point for parsing transactions from PDF content.
        
        Args:
            text: Extracted text from PDF
            tables: Optional extracted tables from PDF
            
        Returns:
            List of parsed transactions
        """
        # Try table parsing first if tables are available
        if tables:
            try:
                transactions_from_tables = self.parse_transactions_from_table(tables)
                if transactions_from_tables:
                    return transactions_from_tables
            except Exception as e:
                logger.warning(f"Table parsing failed: {e}, falling back to text parsing")
        
        # Fall back to text parsing
        return self.parse_transactions_from_text(text)
    
    def can_parse(self, text: str) -> bool:
        """Check if this parser can handle the given text."""
        text_lower = text.lower()
        return any(pattern.lower() in text_lower for pattern in self.supported_patterns)
    
    def clean_amount(self, amount_str: str) -> float:
        """
        Convert amount string to float.
        
        Args:
            amount_str: String representation of amount
            
        Returns:
            Float amount (negative for debits in parentheses)
        """
        if not amount_str or amount_str.strip() == '':
            return 0.0
        
        # Remove whitespace
        amount_str = amount_str.strip()
        
        # Handle parentheses (negative amounts)
        is_negative = amount_str.startswith('(') and amount_str.endswith(')')
        
        # Remove currency symbols, parentheses, and commas
        cleaned = re.sub(r'[\$£€\(\),]', '', amount_str)
        
        try:
            amount = float(cleaned)
            return -amount if is_negative else amount
        except ValueError:
            logger.warning(f"Could not parse amount: {amount_str}")
            return 0.0
    
    def parse_date_flexible(self, date_str: str) -> Optional[datetime]:
        """
        Parse date string using multiple format attempts.
        
        Args:
            date_str: String representation of date
            
        Returns:
            Parsed datetime or None if parsing fails
        """
        date_formats = [
            '%d %b %Y',      # 05 Jan 2026
            '%d %b %y',      # 05 Jan 26
            '%d/%m/%Y',      # 05/01/2026
            '%d-%m-%Y',      # 05-01-2026
            '%d/%m/%y',      # 05/01/26
            '%d-%m-%y',      # 05-01-26
            '%Y-%m-%d',      # 2026-01-05
            '%m/%d/%Y',      # 01/05/2026
            '%m-%d-%Y',      # 01-05-2026
        ]
        
        # Clean up the date string
        date_str = date_str.strip()
        
        for fmt in date_formats:
            try:
                parsed_date = datetime.strptime(date_str, fmt)
                
                # Handle 2-digit years
                if parsed_date.year < 1950:
                    parsed_date = parsed_date.replace(year=parsed_date.year + 2000)
                elif parsed_date.year < 100:
                    if parsed_date.year <= 50:
                        parsed_date = parsed_date.replace(year=parsed_date.year + 2000)
                    else:
                        parsed_date = parsed_date.replace(year=parsed_date.year + 1900)
                
                return parsed_date
            except ValueError:
                continue
        
        logger.warning(f"Could not parse date: {date_str}")
        return None
    
    def clean_transaction_description(self, raw_description: str, existing_payment_method: Optional[str] = None) -> Tuple[str, Optional[str]]:
        """
        Extract payment method from description start and return cleaned description.
        
        This function handles transactions where payment method codes appear at the start
        of descriptions with newline separators (e.g., "VIS\nTESCO STORES" -> "TESCO STORES").
        
        Args:
            raw_description: Original transaction description
            existing_payment_method: Already extracted payment method (takes precedence)
            
        Returns:
            Tuple of (cleaned_description, extracted_payment_method)
            
        Logic:
            - If existing_payment_method present → use it, still clean description
            - Extract leftmost code (DD, OBP, ))) etc.) from start of description
            - Remove code + newline/space separator
            - Return cleaned description + extracted code
        """
        if not raw_description:
            return "", None
            
        # Payment method patterns to look for at start of description
        # Based on analysis of actual transaction data
        DESCRIPTION_PAYMENT_PATTERNS = {
            r'^VIS\n': 'VIS',           # Visa transactions
            r'^DD\n': 'DD',             # Direct Debits  
            r'^\)\)\)\n': ')))',        # Contactless payments
            r'^TFR\n': 'TFR',           # Transfers
            r'^BP\n': 'BP',             # Bill Payments
            r'^CR\n': 'CR',             # Credits
            r'^FP\n': 'FP',             # Faster Payments
            r'^SO\n': 'SO',             # Standing Orders
            r'^BACS\n': 'BACS',         # BACS payments
            r'^CHAPS\n': 'CHAPS',       # CHAPS payments
            r'^ATM\n': 'ATM',           # ATM transactions
            r'^POS\n': 'POS',           # Point of Sale
            r'^MC\n': 'MC',             # Mastercard
            r'^OBP\n': 'OBP',           # Open Banking Payment
        }
        
        cleaned_description = raw_description
        extracted_payment_method = None
        
        # Try to extract payment method from description start
        for pattern, payment_method in DESCRIPTION_PAYMENT_PATTERNS.items():
            match = re.match(pattern, raw_description)
            if match:
                # Extract the payment method code
                extracted_payment_method = payment_method
                # Remove the code and newline from description
                cleaned_description = re.sub(pattern, '', raw_description, count=1)
                break
        
        # Additional cleaning: handle space-separated codes (e.g., "))) MERCHANT")
        if not extracted_payment_method:
            space_patterns = {
                r'^\)\)\) ': ')))',      # Contactless with space
                r'^VIS ': 'VIS',         # Visa with space
                r'^DD ': 'DD',           # Direct Debit with space
                r'^CR ': 'CR',           # Credit with space
            }
            
            for pattern, payment_method in space_patterns.items():
                match = re.match(pattern, raw_description)
                if match:
                    extracted_payment_method = payment_method
                    cleaned_description = re.sub(pattern, '', raw_description, count=1)
                    break
        
        # Clean up whitespace
        cleaned_description = cleaned_description.strip()
        
        # Prefer existing payment method if available, but return extracted for logging/validation
        final_payment_method = existing_payment_method if existing_payment_method else extracted_payment_method
        
        logger.debug(f"Description cleaning: '{raw_description}' -> '{cleaned_description}', payment_method: {final_payment_method}")
        
        return cleaned_description, extracted_payment_method

    def extract_merchant_and_location(self, description: str) -> Tuple[str, Optional[str]]:
        """
        Extract merchant name and location from transaction description.
        
        Note: This method now expects pre-cleaned descriptions (payment method codes already removed).
        
        Args:
            description: Clean transaction description (no payment method prefixes)
            
        Returns:
            Tuple of (merchant, location)
        """
        if not description:
            return "", None
            
        cleaned = description.strip()
        
        # Try to split on location patterns
        # Pattern: MERCHANT NAME LOCATION
        parts = cleaned.split()
        
        if len(parts) <= 1:
            return cleaned, None
        
        # Look for common location indicators
        location_indicators = ['CITY', 'TOWN', 'LOCATION', 'AREA', 'CENTER', 'DISTRICT', 'LONDON', 'OXFORD', 'BARNES']
        
        for i, part in enumerate(parts):
            if part.upper() in location_indicators:
                merchant = ' '.join(parts[:i]).strip()
                location = ' '.join(parts[i:]).strip()
                return merchant, location if location else None
        
        # If no clear location found, treat last 1-2 words as potential location
        # Common pattern: "MERCHANT NAME CITY" or "MERCHANT LOCATION"
        if len(parts) > 3:
            merchant = ' '.join(parts[:-1]).strip()
            location = parts[-1]
            return merchant, location
        else:
            return cleaned, None
    
    def validate_transaction(self, transaction: Transaction) -> bool:
        """
        Validate that a transaction has required fields and makes sense.
        
        Args:
            transaction: Transaction to validate
            
        Returns:
            True if transaction is valid
        """
        if not transaction.date:
            logger.warning(f"Transaction missing date: {transaction.raw_description}")
            return False
        
        if not transaction.description.strip():
            logger.warning(f"Transaction missing description: {transaction.raw_description}")
            return False
        
        if transaction.amount == 0.0 and transaction.description.upper() not in ['BALANCEBROUGHTFORWARD', 'BALANCECARRIEDFORWARD']:
            logger.warning(f"Transaction has zero amount: {transaction.description}")
            return False
        
        return True