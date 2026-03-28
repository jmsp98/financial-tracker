"""
PDF processing script - Extract transactions from bank statement PDFs.
"""

import os
import sys
import json
import logging
from datetime import datetime
from typing import List

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from src.pdf_extractor import PDFExtractor
from src.transaction_parser import TransactionParser

logger = logging.getLogger(__name__)


def process_pdf_file(pdf_path: str, extractor: PDFExtractor, parser: TransactionParser) -> List[dict]:
    """Process a single PDF file and return transactions."""
    logger.info(f"Processing: {pdf_path}")
    
    try:
        # Extract text from PDF
        text = extractor.extract_text(pdf_path)
        tables = extractor.extract_tables(pdf_path)
        
        if not text and not tables:
            logger.warning(f"No text or tables extracted from {pdf_path}")
            return []
        
        # Parse transactions from text
        transactions_from_text = parser.parse_transactions_from_text(text) if text else []
        
        # Parse transactions from tables
        transactions_from_tables = parser.parse_transactions_from_table(tables) if tables else []
        
        # Combine transactions (prefer table data if available)
        all_transactions = transactions_from_tables if transactions_from_tables else transactions_from_text
        
        # Convert to dict format
        transaction_dicts = []
        for txn in all_transactions:
            transaction_dicts.append({
                'date': txn.date.isoformat(),
                'description': txn.description,
                'amount': txn.amount,
                'balance': txn.balance,
                'type': txn.transaction_type
            })
        
        logger.info(f"Extracted {len(transaction_dicts)} transactions from {pdf_path}")
        return transaction_dicts
        
    except Exception as e:
        logger.error(f"Error processing {pdf_path}: {e}")
        return []


def main(input_dir: str, output_dir: str) -> bool:
    """
    Main processing function.
    
    Args:
        input_dir: Directory containing PDF files
        output_dir: Directory to save processed transaction data
        
    Returns:
        True if successful, False otherwise
    """
    try:
        # Ensure output directory exists
        os.makedirs(output_dir, exist_ok=True)
        
        # Find PDF files
        if not os.path.exists(input_dir):
            logger.error(f"Input directory does not exist: {input_dir}")
            return False
        
        pdf_files = [f for f in os.listdir(input_dir) if f.lower().endswith('.pdf')]
        
        if not pdf_files:
            logger.warning(f"No PDF files found in {input_dir}")
            return False
        
        logger.info(f"Found {len(pdf_files)} PDF files to process")
        
        # Initialize processors
        extractor = PDFExtractor()
        parser = TransactionParser()
        
        # Process each PDF
        all_transactions = []
        
        for pdf_file in pdf_files:
            pdf_path = os.path.join(input_dir, pdf_file)
            transactions = process_pdf_file(pdf_path, extractor, parser)
            
            if transactions:
                # Save individual file results
                output_file = os.path.join(output_dir, f"{os.path.splitext(pdf_file)[0]}_transactions.json")
                with open(output_file, 'w') as f:
                    json.dump(transactions, f, indent=2)
                
                all_transactions.extend(transactions)
        
        if all_transactions:
            # Save combined results
            combined_file = os.path.join(output_dir, "all_transactions.json")
            with open(combined_file, 'w') as f:
                json.dump(all_transactions, f, indent=2)
            
            logger.info(f"Successfully processed {len(pdf_files)} files with {len(all_transactions)} total transactions")
            logger.info(f"Results saved to: {output_dir}")
            return True
        else:
            logger.warning("No transactions extracted from any PDF files")
            return False
            
    except Exception as e:
        logger.error(f"Processing failed: {e}")
        return False


if __name__ == '__main__':
    # Command line interface
    if len(sys.argv) != 3:
        print("Usage: python process_statements.py <input_dir> <output_dir>")
        sys.exit(1)
    
    input_dir = sys.argv[1]
    output_dir = sys.argv[2]
    
    success = main(input_dir, output_dir)
    sys.exit(0 if success else 1)