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
    
    def extract_merchant_and_location(self, description: str) -> Tuple[str, Optional[str]]:
        """
        Extract merchant name and location from transaction description.
        
        Args:
            description: Transaction description
            
        Returns:
            Tuple of (merchant, location)
        """
        # Remove common prefixes
        cleaned = description
        for prefix in ['VIS ', 'DD ', '))) ', 'CR ']:
            if cleaned.startswith(prefix):
                cleaned = cleaned[len(prefix):].strip()
                break
        
        # Try to split on location patterns
        # Pattern: MERCHANT NAME LOCATION
        parts = cleaned.split()
        
        if len(parts) <= 1:
            return cleaned, None
        
        # Look for common location indicators
        location_indicators = ['CITY', 'TOWN', 'LOCATION', 'AREA', 'CENTER', 'DISTRICT']
        
        for i, part in enumerate(parts):
            if part.upper() in location_indicators:
                merchant = ' '.join(parts[:i]).strip()
                location = ' '.join(parts[i:]).strip()
                return merchant, location if location else None
        
        # If no clear location found, treat last 1-2 words as potential location
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