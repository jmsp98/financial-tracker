"""
Parser factory for automatically detecting and creating appropriate bank parsers.
"""

import re
from typing import Optional, Type, Dict, Any
from .base_parser import BaseBankParser
from .advanced_hsbc_parser import AdvancedHSBCParser


class ParserFactory:
    """Factory class for creating appropriate parsers based on bank statement content."""
    
    # Registry of available parsers
    _parsers: Dict[str, Type[BaseBankParser]] = {
        'hsbc': AdvancedHSBCParser,  # Uses pdfplumber word extraction
    }
    
    # Detection patterns for each bank
    _detection_patterns = {
        'hsbc': [
            r'HSBC UK',
            r'Payment type and details',
            r'£Paid out',
            r'£Paid in',
            r'£Balance',
            r'Statement period',
        ]
    }
    
    @classmethod
    def detect_bank(cls, text: str) -> Optional[str]:
        """
        Detect which bank this statement is from based on text content.
        
        Args:
            text: Raw text content from PDF
            
        Returns:
            Bank identifier string or None if not detected
        """
        text_upper = text.upper()
        
        # Check each bank's patterns
        for bank, patterns in cls._detection_patterns.items():
            matches = 0
            for pattern in patterns:
                if re.search(pattern, text_upper, re.IGNORECASE):
                    matches += 1
            
            # Require at least 3 pattern matches for confident detection
            if matches >= 3:
                return bank
        
        return None
    
    @classmethod
    def create_parser(cls, text: str, bank: Optional[str] = None) -> BaseBankParser:
        """
        Create appropriate parser for the given bank statement.
        
        Args:
            text: Raw text content from PDF
            bank: Optional bank identifier (will auto-detect if not provided)
            
        Returns:
            Appropriate parser instance
            
        Raises:
            ValueError: If bank cannot be detected or is not supported
        """
        if bank is None:
            bank = cls.detect_bank(text)
        
        if bank is None:
            raise ValueError(
                "Could not detect bank from statement content. "
                "Supported banks: " + ", ".join(cls._parsers.keys())
            )
        
        if bank not in cls._parsers:
            raise ValueError(f"Unsupported bank: {bank}")
        
        parser_class = cls._parsers[bank]
        return parser_class()
    
    @classmethod
    def get_supported_banks(cls) -> list[str]:
        """Get list of supported bank identifiers."""
        return list(cls._parsers.keys())
    
    @classmethod
    def register_parser(cls, bank: str, parser_class: Type[BaseBankParser], 
                       detection_patterns: list[str]):
        """
        Register a new parser for a bank.
        
        Args:
            bank: Bank identifier
            parser_class: Parser class that extends BaseParser
            detection_patterns: List of regex patterns to detect this bank
        """
        cls._parsers[bank] = parser_class
        cls._detection_patterns[bank] = detection_patterns