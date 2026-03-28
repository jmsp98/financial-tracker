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
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.pdf_extractor import PDFExtractor
from src.parsers import ParserFactory

logger = logging.getLogger(__name__)


def process_pdf_file(pdf_path: str, extractor: PDFExtractor) -> List[dict]:
    """Process a single PDF file and return transactions."""
    logger.info(f"Processing: {pdf_path}")
    
    try:
        # Extract text from PDF
        text = extractor.extract_text(pdf_path)
        tables = extractor.extract_tables(pdf_path)
        
        if not text and not tables:
            logger.warning(f"No text or tables extracted from {pdf_path}")
            return []
        
        # Create appropriate parser based on statement content
        parser = ParserFactory.create_parser(text)
        bank_type = ParserFactory.detect_bank(text)
        logger.info(f"Detected bank: {bank_type}")
        
        # Parse transactions
        all_transactions = parser.parse_transactions(text)
        
        # Convert to dict format
        transaction_dicts = []
        for txn in all_transactions:
            transaction_dict = {
                'date': txn.date.isoformat(),
                'description': txn.description,
                'amount': txn.amount,
                'balance': txn.balance if txn.balance is not None else 0.0,
                'type': txn.transaction_type
            }
            
            # Add new fields if available
            if hasattr(txn, 'payment_method') and txn.payment_method:
                transaction_dict['payment_method'] = txn.payment_method
            if hasattr(txn, 'merchant') and txn.merchant:
                transaction_dict['merchant'] = txn.merchant
            if hasattr(txn, 'location') and txn.location:
                transaction_dict['location'] = txn.location
                
            transaction_dicts.append(transaction_dict)
        
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
        
        # Initialize extractor
        extractor = PDFExtractor()
        
        # Process each PDF
        all_transactions = []
        
        for pdf_file in pdf_files:
            pdf_path = os.path.join(input_dir, pdf_file)
            transactions = process_pdf_file(pdf_path, extractor)
            
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