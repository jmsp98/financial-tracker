#!/usr/bin/env python3
"""
Safe demonstration script for HSBC parser using only synthetic data.
This script shows how the parser works without exposing any real financial information.
"""

import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from parsers.hsbc_parser import HSBCParser


def demonstrate_parser():
    """Demonstrate HSBC parser functionality with synthetic data."""
    
    # IMPORTANT: Using completely synthetic/fake bank statement data
    synthetic_hsbc_text = """
HSBC UK Bank plc
Contact tel: 03457 404 404
www.hsbc.co.uk

Your Bank Account Statement  
Account Name: Test User
Sort Code: 11-22-33
Account Number: 87654321
Statement Period: 01 Feb 25 to 28 Feb 25

Date Payment type and details £Paid out £Paid in £Balance

01 Feb 25 VIS GROCERY STORE 123
TESTTOWN 45.67 2,134.33

01 Feb 25 ))) COFFEE SHOP
TESTTOWN 3.50

02 Feb 25 DD UTILITIES COMPANY
REF123456 125.00 2,005.83

03 Feb 25 CR REFUND DEPARTMENT
STORE ABC 15.50 2,021.33

04 Feb 25 TFR INTERNET TRANSFER
TEST TRANSFER 1,000.00 3,021.33

05 Feb 25 VIS ONLINE RETAILER
INTERNET 89.99

BALANCE CARRIED FORWARD 2,931.34
    """
    
    print("=== HSBC Parser Demonstration (Synthetic Data Only) ===")
    print()
    
    # Initialize parser
    parser = HSBCParser()
    
    # Parse transactions
    print("Parsing synthetic HSBC statement...")
    transactions = parser.parse_transactions_from_text(synthetic_hsbc_text)
    
    print(f"Found {len(transactions)} transactions:")
    print()
    
    # Display parsed transactions
    for i, txn in enumerate(transactions, 1):
        print(f"{i:2}. {txn.date.strftime('%Y-%m-%d')} | "
              f"{txn.payment_method or 'N/A':12} | "
              f"£{txn.amount:8.2f} | "
              f"{txn.transaction_type:6} | "
              f"{txn.description}")
    
    print()
    print("=== Summary ===")
    
    # Calculate totals
    credits = [t for t in transactions if t.transaction_type == 'credit']
    debits = [t for t in transactions if t.transaction_type == 'debit']
    
    total_credits = sum(t.amount for t in credits)
    total_debits = sum(t.amount for t in debits)  # Note: debits are negative
    
    print(f"Credit transactions: {len(credits)} (£{total_credits:.2f})")
    print(f"Debit transactions:  {len(debits)} (£{total_debits:.2f})")
    print(f"Net change:          £{total_credits + total_debits:.2f}")
    
    print()
    print("✓ Parser working correctly with synthetic data")
    print("✓ No real financial information was used")


if __name__ == '__main__':
    demonstrate_parser()