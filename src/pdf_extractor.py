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

from typing import List, Optional
import logging

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