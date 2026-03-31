"""
PDF processing script - Extract transactions from bank statement PDFs.
"""

import os
import sys
import json
import logging
from datetime import datetime
from typing import List, Dict

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.pdf_extractor import PDFExtractor
from src.parsers import ParserFactory

logger = logging.getLogger(__name__)


def process_pdf_file(pdf_path: str, extractor: PDFExtractor) -> dict:
    """Process a single PDF file and return transactions with currency info."""
    logger.info(f"Processing: {pdf_path}")
    
    try:
        # Extract text from PDF
        text = extractor.extract_text(pdf_path)
        tables = extractor.extract_tables(pdf_path)
        
        if not text and not tables:
            logger.warning(f"No text or tables extracted from {pdf_path}")
            return {'transactions': [], 'currency': {'symbol': '£', 'iso_code': 'GBP', 'confidence': 'low', 'sources': ['default']}}
        
        # Detect currency from PDF text
        currency_info = extractor.detect_currency_from_text(text)
        logger.info(f"Detected currency: {currency_info}")
        
        # Create appropriate parser based on statement content
        parser = ParserFactory.create_parser(text)
        bank_type = ParserFactory.detect_bank(text)
        logger.info(f"Detected bank: {bank_type}")
        
        # Parse transactions - use PDF parsing for HSBC enhanced parser
        if bank_type == 'hsbc' and hasattr(parser, 'parse_pdf'):
            logger.info(f"Using enhanced PDF parsing for {bank_type}")
            all_transactions = parser.parse_pdf(pdf_path)
        else:
            logger.info(f"Using text-based parsing for {bank_type}")
            all_transactions = parser.parse_transactions(text)
        
        # Convert to dict format
        transaction_dicts = []
        for txn in all_transactions:
            transaction_dict = {
                'date': txn.date.isoformat(),
                'description': txn.description,
                'amount': txn.amount,
                'balance': txn.balance,  # Preserve None/null values for transactions without balance data
                'type': txn.transaction_type,
                'currency_symbol': currency_info['symbol'],  # Add detected currency
                'currency_code': currency_info['iso_code']
            }
            
            # Add new fields if available
            if hasattr(txn, 'payment_method') and txn.payment_method:
                transaction_dict['payment_method'] = txn.payment_method
            if hasattr(txn, 'reference') and txn.reference:
                transaction_dict['reference'] = txn.reference
                
            transaction_dicts.append(transaction_dict)
        
        logger.info(f"Extracted {len(transaction_dicts)} transactions from {pdf_path}")
        return {
            'transactions': transaction_dicts,
            'currency': currency_info
        }
        
    except Exception as e:
        logger.error(f"Error processing {pdf_path}: {e}")
        return {
            'transactions': [], 
            'currency': {'symbol': '£', 'iso_code': 'GBP', 'confidence': 'low', 'sources': ['error_fallback']}
        }


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
        all_currency_info = []
        
        for pdf_file in pdf_files:
            pdf_path = os.path.join(input_dir, pdf_file)
            result = process_pdf_file(pdf_path, extractor)
            
            if result['transactions']:
                # Save individual file results (with currency info)
                output_file = os.path.join(output_dir, f"{os.path.splitext(pdf_file)[0]}_transactions.json")
                with open(output_file, 'w') as f:
                    json.dump(result, f, indent=2)
                
                all_transactions.extend(result['transactions'])
                all_currency_info.append({
                    'file': pdf_file,
                    'currency': result['currency']
                })
        
        if all_transactions:
            # Determine primary currency (most confident detection)
            primary_currency = {'symbol': '£', 'iso_code': 'GBP', 'confidence': 'low', 'sources': ['default']}
            if all_currency_info:
                # Find currency with highest confidence
                high_confidence = [info for info in all_currency_info if info['currency']['confidence'] == 'high']
                if high_confidence:
                    primary_currency = high_confidence[0]['currency']
                else:
                    medium_confidence = [info for info in all_currency_info if info['currency']['confidence'] == 'medium']
                    if medium_confidence:
                        primary_currency = medium_confidence[0]['currency']
            
            # Save combined results with currency metadata
            combined_data = {
                'transactions': all_transactions,
                'currency': primary_currency,
                'currency_detection_details': all_currency_info,
                'processed_files': len(pdf_files),
                'total_transactions': len(all_transactions)
            }
            
            combined_file = os.path.join(output_dir, "all_transactions.json")
            with open(combined_file, 'w') as f:
                json.dump(combined_data, f, indent=2)
            
            logger.info(f"Successfully processed {len(pdf_files)} files with {len(all_transactions)} total transactions")
            logger.info(f"Primary currency detected: {primary_currency['symbol']} ({primary_currency['iso_code']}) with {primary_currency['confidence']} confidence")
            logger.info(f"Results saved to: {output_dir}")
            
            # Run basic balance validation
            try:
                from validate_balances import validate_all_files
                logger.info("Running balance validation...")
                validation_results = validate_all_files(input_dir, summarize=True)
                if validation_results:
                    total_errors = sum(result['error_count'] for result in validation_results)
                    if total_errors > 0:
                        logger.warning(f"Balance validation found {total_errors} potential parsing issues")
                    else:
                        logger.info("Balance validation passed - all balances match!")
            except ImportError:
                logger.debug("Balance validation not available (validate_balances module not found)")
            except Exception as e:
                logger.warning(f"Balance validation failed: {e}")
            
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