#!/usr/bin/env python3
"""
Test the new advanced HSBC parser against current balance validation errors.
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from parsers.advanced_hsbc_parser import AdvancedHSBCParser
import logging
import json
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_advanced_parser():
    """Test the advanced parser on HSBC PDFs."""
    
    parser = AdvancedHSBCParser()
    
    pdf_files = [
        "data/raw/2026-02-04_Statement.pdf", 
        "data/raw/2026-03-04_Statement.pdf"
    ]
    
    all_results = {}
    
    for pdf_file in pdf_files:
        logger.info(f"\n{'='*80}")
        logger.info(f"TESTING ADVANCED PARSER ON: {pdf_file}")
        logger.info(f"{'='*80}")
        
        try:
            # Parse using the new advanced method
            transactions = parser.parse_transactions_from_pdf(pdf_file)
            
            logger.info(f"Extracted {len(transactions)} transactions")
            
            if transactions:
                # Show summary
                date_range = f"{transactions[0].date.date()} to {transactions[-1].date.date()}"
                logger.info(f"Date range: {date_range}")
                
                # Show sample transactions
                logger.info("Sample transactions:")
                for i, txn in enumerate(transactions[:5]):
                    logger.info(f"  {i+1}. {txn.date.strftime('%Y-%m-%d')} | {txn.payment_method} | {txn.description} | {txn.amount} | Bal: {txn.balance}")
                
                if len(transactions) > 5:
                    logger.info(f"  ... and {len(transactions) - 5} more")
                
                # Calculate balance validation metrics
                validation_results = validate_transactions(transactions)
                all_results[pdf_file] = validation_results
                
                # Show last few transactions
                logger.info("Last few transactions:")
                for i, txn in enumerate(transactions[-3:]):
                    logger.info(f"  {len(transactions)-2+i}. {txn.date.strftime('%Y-%m-%d')} | {txn.payment_method} | {txn.description} | {txn.amount} | Bal: {txn.balance}")
            
        except Exception as e:
            logger.error(f"Error processing {pdf_file}: {e}")
            all_results[pdf_file] = {"error": str(e)}
    
    # Summary
    logger.info(f"\n{'='*80}")
    logger.info("ADVANCED PARSER TEST SUMMARY")
    logger.info(f"{'='*80}")
    
    for pdf_file, results in all_results.items():
        logger.info(f"\nFile: {pdf_file}")
        if "error" in results:
            logger.info(f"  ❌ Error: {results['error']}")
        else:
            logger.info(f"  ✅ Transactions: {results['transaction_count']}")
            logger.info(f"  ✅ Balance validation: {results['balance_validation']}")
            logger.info(f"  ✅ Date range: {results['date_range']}")
            logger.info(f"  ✅ Payment methods: {results['payment_methods']}")

def validate_transactions(transactions):
    """Basic validation of extracted transactions."""
    if not transactions:
        return {"transaction_count": 0}
    
    # Count by payment method
    payment_methods = {}
    for txn in transactions:
        method = txn.payment_method or "Unknown"
        payment_methods[method] = payment_methods.get(method, 0) + 1
    
    # Check for balance progression
    balance_errors = 0
    prev_balance = None
    for txn in transactions:
        if txn.balance is not None:
            if prev_balance is not None:
                expected_balance = prev_balance + txn.amount
                if abs(expected_balance - txn.balance) > 0.01:  # Allow for rounding
                    balance_errors += 1
            prev_balance = txn.balance
    
    # Check date progression
    date_errors = 0
    prev_date = None
    for txn in transactions:
        if prev_date and txn.date < prev_date:
            date_errors += 1
        prev_date = txn.date
    
    return {
        "transaction_count": len(transactions),
        "balance_validation": f"{balance_errors} balance calculation errors",
        "date_range": f"{transactions[0].date.date()} to {transactions[-1].date.date()}",
        "payment_methods": dict(payment_methods),
        "date_errors": date_errors
    }

if __name__ == "__main__":
    test_advanced_parser()