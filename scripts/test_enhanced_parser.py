#!/usr/bin/env python3
"""
Test the enhanced HSBC parser with comprehensive payment method meanings.
"""

import sys
import os
sys.path.append('src')

from parsers.advanced_hsbc_parser import AdvancedHSBCParser, PAYMENT_METHOD_MEANINGS, PAYMENT_CATEGORIES

def test_enhanced_parser():
    """Test the enhanced parser with payment method meanings."""
    
    print("🧪 TESTING ENHANCED HSBC PARSER")
    print("=" * 60)
    
    pdf_path = "data/raw/sample_statement.pdf"  # Use sample data for testing
    
    if not os.path.exists(pdf_path):
        print("❌ PDF file not found:", pdf_path)
        return
    
    parser = AdvancedHSBCParser()
    
    print(f"📄 Processing: {pdf_path}")
    print(f"🔍 Using {len(PAYMENT_METHOD_MEANINGS)} payment method mappings")
    print(f"📊 With {len(PAYMENT_CATEGORIES)} categories")
    
    # Parse transactions
    transactions = parser.parse_transactions_from_pdf(pdf_path)
    
    print(f"\n📈 PARSING RESULTS:")
    print(f"  Total transactions extracted: {len(transactions)}")
    
    if not transactions:
        print("❌ No transactions found!")
        return
    
    # Test payment method meanings
    print(f"\n💳 PAYMENT METHOD ANALYSIS:")
    print("-" * 50)
    
    method_stats = {}
    category_stats = {}
    
    for txn in transactions:
        method = txn.payment_method
        if method:
            # Test our new helper methods
            meaning = parser.get_payment_method_meaning(method)
            category = parser.get_payment_category(method)
            
            # Count stats
            if method not in method_stats:
                method_stats[method] = {'count': 0, 'meaning': meaning, 'category': category}
            method_stats[method]['count'] += 1
            
            if category not in category_stats:
                category_stats[category] = 0
            category_stats[category] += 1
    
    print(f"{'Code':<8} | {'Count':<6} | {'Category':<18} | {'Meaning'}")
    print("-" * 70)
    
    for method in sorted(method_stats.keys()):
        stats = method_stats[method]
        print(f"{method:<8} | {stats['count']:<6} | {stats['category']:<18} | {stats['meaning']}")
    
    # Category breakdown
    print(f"\n📊 PAYMENT CATEGORY BREAKDOWN:")
    print("-" * 40)
    
    for category in sorted(category_stats.keys()):
        count = category_stats[category]
        percentage = (count / len(transactions)) * 100
        print(f"  {category:<18}: {count:>3} transactions ({percentage:>5.1f}%)")
    
    # Show examples of enhanced descriptions
    print(f"\n📋 EXAMPLE TRANSACTIONS WITH ENHANCED MEANINGS:")
    print("-" * 55)
    
    shown_methods = set()
    for txn in transactions[:20]:  # Show first 20 as examples
        if txn.payment_method and txn.payment_method not in shown_methods:
            meaning = parser.get_payment_method_meaning(txn.payment_method)
            category = parser.get_payment_category(txn.payment_method)
            date_str = txn.date.strftime('%d %b')
            
            print(f"  {txn.payment_method} → {meaning}")
            print(f"    {date_str}: {txn.description[:40]}... (£{abs(txn.amount):.2f})")
            print(f"    Category: {category}")
            print()
            
            shown_methods.add(txn.payment_method)
            
            # Stop after showing 8 different methods
            if len(shown_methods) >= 8:
                break
    
    # Test specific method lookups
    print(f"🔍 TESTING PAYMENT METHOD LOOKUPS:")
    print("-" * 40)
    
    test_methods = ['VIS', '))))', 'DD', 'CR', 'FPO', 'SO', 'UNKNOWN']
    for method in test_methods:
        meaning = parser.get_payment_method_meaning(method)
        category = parser.get_payment_category(method)
        print(f"  {method:<8} → {meaning:<25} [{category}]")

def test_new_payment_methods():
    """Test recognition of new payment method codes."""
    
    print(f"\n🆕 TESTING NEW PAYMENT METHOD RECOGNITION:")
    print("=" * 50)
    
    parser = AdvancedHSBCParser()
    
    # Test some new codes that weren't in the original list
    new_test_codes = [
        'FPI',  # Faster Payment In
        'BACS', # Salary or business payment
        'CHAPS', # Same-day large transfer
        'DWP',  # Department for Work and Pensions
        'REV',  # Reversal
        'POC',  # Post Office counter
    ]
    
    for code in new_test_codes:
        meaning = parser.get_payment_method_meaning(code)
        category = parser.get_payment_category(code)
        print(f"  {code:<6} → {meaning:<30} [{category}]")
    
    # Test that our detection still works
    test_text_samples = [
        "05 Feb 26\nFPI\nSALARY PAYMENT",
        "BACS PAYMENT FROM EMPLOYER",
        "CHAPS\nLARGE TRANSFER",
        "DWP UNIVERSAL CREDIT"
    ]
    
    print(f"\n🔍 TESTING TEXT DETECTION:")
    print("-" * 30)
    
    for text in test_text_samples:
        has_payment = parser._looks_like_payment_method(text)
        extracted = parser._extract_payment_method_from_text(text)
        print(f"  Text: {text[:30]}")
        print(f"  Detected: {has_payment}, Extracted: {extracted}")
        if extracted:
            meaning = parser.get_payment_method_meaning(extracted)
            print(f"  Meaning: {meaning}")
        print()

if __name__ == "__main__":
    test_enhanced_parser()
    test_new_payment_methods()
    
    print(f"\n✅ ENHANCEMENT TESTING COMPLETE!")
    print(f"📊 Total payment methods supported: {len(PAYMENT_METHOD_MEANINGS)}")
    print(f"🗂️  Total categories: {len(PAYMENT_CATEGORIES)}")