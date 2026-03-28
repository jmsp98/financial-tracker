"""
PDF text extraction module for bank statements.
"""

try:
    import pdfplumber
    HAS_PDFPLUMBER = True
except ImportError:
    HAS_PDFPLUMBER = False

try:
    import PyPDF2
    HAS_PYPDF2 = True
except ImportError:
    HAS_PYPDF2 = False

from typing import List, Optional, Dict
import logging
import re

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class PDFExtractor:
    """Extract text from PDF bank statements using multiple methods."""
    
    def __init__(self):
        if not HAS_PDFPLUMBER and not HAS_PYPDF2:
            raise ImportError("Either pdfplumber or PyPDF2 is required. Install with: pip install pdfplumber PyPDF2")
    
    def extract_text_pdfplumber(self, pdf_path: str) -> str:
        """
        Extract text using pdfplumber (better for tables and structured data).
        
        Args:
            pdf_path: Path to the PDF file
            
        Returns:
            Extracted text as string
        """
        if not HAS_PDFPLUMBER:
            logger.warning("pdfplumber not available, skipping this method")
            return ""
            
        try:
            text = ""
            with pdfplumber.open(pdf_path) as pdf:
                for page in pdf.pages:
                    page_text = page.extract_text()
                    if page_text:
                        text += page_text + "\n"
            return text
        except Exception as e:
            logger.error(f"Error extracting text with pdfplumber: {e}")
            return ""
    
    def extract_text_pypdf2(self, pdf_path: str) -> str:
        """
        Extract text using PyPDF2 (fallback method).
        
        Args:
            pdf_path: Path to the PDF file
            
        Returns:
            Extracted text as string
        """
        if not HAS_PYPDF2:
            logger.warning("PyPDF2 not available, skipping this method")
            return ""
            
        try:
            text = ""
            with open(pdf_path, 'rb') as file:
                pdf_reader = PyPDF2.PdfReader(file)
                for page in pdf_reader.pages:
                    page_text = page.extract_text()
                    if page_text:
                        text += page_text + "\n"
            return text
        except Exception as e:
            logger.error(f"Error extracting text with PyPDF2: {e}")
            return ""
    
    def extract_text(self, pdf_path: str, method: str = "pdfplumber") -> str:
        """
        Extract text from PDF using specified method.
        
        Args:
            pdf_path: Path to the PDF file
            method: Extraction method ("pdfplumber" or "pypdf2")
            
        Returns:
            Extracted text as string
        """
        if method == "pdfplumber":
            text = self.extract_text_pdfplumber(pdf_path)
            # Fallback to PyPDF2 if pdfplumber fails
            if not text and HAS_PYPDF2:
                logger.info("pdfplumber failed, trying PyPDF2...")
                text = self.extract_text_pypdf2(pdf_path)
        elif method == "pypdf2":
            text = self.extract_text_pypdf2(pdf_path)
        else:
            raise ValueError(f"Unknown extraction method: {method}")
        
        return text
    
    def extract_tables(self, pdf_path: str) -> List[List[List[str]]]:
        """
        Extract tables from PDF using pdfplumber.
        
        Args:
            pdf_path: Path to the PDF file
            
        Returns:
            List of tables, where each table is a list of rows,
            and each row is a list of cell values
        """
        if not HAS_PDFPLUMBER:
            logger.warning("pdfplumber not available, cannot extract tables")
            return []
            
        try:
            tables = []
            with pdfplumber.open(pdf_path) as pdf:
                for page in pdf.pages:
                    page_tables = page.extract_tables()
                    if page_tables:
                        tables.extend(page_tables)
            return tables
        except Exception as e:
            logger.error(f"Error extracting tables: {e}")
            return []

    def detect_currency_from_text(self, text: str) -> Dict:
        """
        Detect currency symbols and information from PDF text.
        
        Args:
            text: Extracted PDF text content
            
        Returns:
            Dict with detected currency info:
            {
                'symbol': '£',  # Primary currency symbol detected
                'iso_code': 'GBP',  # ISO currency code if detectable
                'confidence': 'high',  # Detection confidence level
                'sources': ['column_headers', 'amounts']  # Where currency was detected
            }
        """
        if not text:
            return {
                'symbol': '£',  # Default fallback for UK-focused system
                'iso_code': 'GBP',
                'confidence': 'low',
                'sources': ['default']
            }
        
        # Currency detection patterns
        currency_patterns = {
            '£': {
                'symbol': '£',
                'iso_code': 'GBP', 
                'patterns': [
                    r'£\s*(Paid\s+out|Paid\s+in|Balance)',  # HSBC column headers
                    r'£\s*\d{1,3}(?:,\d{3})*\.\d{2}',       # £ amounts
                    r'GBP',                                   # ISO code
                    r'Pounds?\s+Sterling',                    # Written currency name
                    r'British\s+Pound'                       # Alternative name
                ]
            },
            '$': {
                'symbol': '$',
                'iso_code': 'USD',
                'patterns': [
                    r'\$\s*(Paid\s+out|Paid\s+in|Balance)', # USD column headers
                    r'\$\s*\d{1,3}(?:,\d{3})*\.\d{2}',      # $ amounts
                    r'USD',                                  # ISO code
                    r'US\s+Dollars?',                        # Written currency name
                    r'American\s+Dollars?'                   # Alternative name
                ]
            },
            '€': {
                'symbol': '€',
                'iso_code': 'EUR',
                'patterns': [
                    r'€\s*(Paid\s+out|Paid\s+in|Balance)', # EUR column headers
                    r'€\s*\d{1,3}(?:,\d{3})*\.\d{2}',      # € amounts
                    r'EUR',                                 # ISO code
                    r'Euros?',                              # Written currency name
                    r'European\s+Currency'                  # Alternative name
                ]
            }
        }
        
        # Score each currency based on pattern matches
        currency_scores = {}
        detection_sources = {}
        
        for symbol, currency_info in currency_patterns.items():
            score = 0
            sources = []
            
            for pattern in currency_info['patterns']:
                matches = re.findall(pattern, text, re.IGNORECASE)
                if matches:
                    match_count = len(matches)
                    
                    # Higher score for column headers (stronger indicator)
                    if 'Paid' in pattern or 'Balance' in pattern:
                        score += match_count * 10
                        sources.append('column_headers')
                    # Medium score for amount patterns
                    elif r'\d' in pattern:
                        score += match_count * 5
                        sources.append('amounts')
                    # Lower score for ISO codes and written names
                    else:
                        score += match_count * 2
                        sources.append('text_references')
            
            if score > 0:
                currency_scores[symbol] = score
                detection_sources[symbol] = list(set(sources))
        
        # Determine best currency match
        if not currency_scores:
            # No currency detected, use UK default
            return {
                'symbol': '£',
                'iso_code': 'GBP',
                'confidence': 'low',
                'sources': ['default']
            }
        
        # Get currency with highest score
        best_currency_symbol = max(currency_scores.keys(), key=lambda k: currency_scores[k])
        best_currency_info = currency_patterns[best_currency_symbol]
        best_score = currency_scores[best_currency_symbol]
        
        # Determine confidence level based on score and detection sources
        sources = detection_sources[best_currency_symbol]
        if best_score >= 10 and 'column_headers' in sources:
            confidence = 'high'
        elif best_score >= 5:
            confidence = 'medium'
        else:
            confidence = 'low'
        
        logger.info(f"Currency detection: {best_currency_symbol} ({best_currency_info['iso_code']}) "
                   f"with confidence {confidence}, score: {best_score}, sources: {sources}")
        
        return {
            'symbol': best_currency_symbol,
            'iso_code': best_currency_info['iso_code'],
            'confidence': confidence,
            'sources': sources
        }