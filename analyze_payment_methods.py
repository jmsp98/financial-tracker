#!/usr/bin/env python3
"""
HSBC Payment Method Code Mapping and Analysis
"""
import sys
import os
sys.path.append('src')

from parsers.advanced_hsbc_parser import AdvancedHSBCParser

def analyze_payment_methods():
    """Analyze payment methods and their meanings"""
    
    # HSBC Payment Method Code Mappings
    PAYMENT_METHOD_MAPPINGS = {
        'VIS': 'Visa Card Payment',
        'DD': 'Direct Debit',
        ')))': 'Contactless Payment (Chip & PIN/Contactless)',
        'CR': 'Credit (Money In)',
        'TFR': 'Transfer',
        'FPO': 'Fast Payment Outward',
        'CHQ': 'Cheque',
        'ATM': 'ATM Withdrawal',
        'BP': 'Bank Payment (Person-to-Person)',
        'OBP': 'Online Bank Payment',
        'SO': 'Standing Order',
        'INT': 'Interest',
        'FEE': 'Bank Fee',
        'MSC': 'Miscellaneous',
        'PAY': 'Salary/Payment In',
        'BGC': 'Bank Giro Credit',
        'CPT': 'Card Payment Terminal',
        'DEB': 'Debit Card Payment',
    }
    
    print("💳 HSBC PAYMENT METHOD CODE MAPPINGS")
    print("=" * 60)
    print(f"{'Code':<6} | {'Full Name':<40} | {'Type':<15}")
    print("-" * 65)
    
    # Categorize by type
    PAYMENT_CATEGORIES = {
        'Card Payments': ['VIS', '))))', 'DEB', 'CPT'],
        'Bank Transfers': ['TFR', 'FPO', 'BP', 'OBP'],
        'Automated Payments': ['DD', 'SO'],
        'Cash/ATM': ['ATM'],
        'Credits': ['CR', 'PAY', 'BGC', 'INT'],
        'Bank Operations': ['CHQ', 'FEE', 'MSC']
    }
    
    for category, codes in PAYMENT_CATEGORIES.items():
        print(f"\n🔸 {category.upper()}:")
        for code in codes:
            if code in PAYMENT_METHOD_MAPPINGS:
                meaning = PAYMENT_METHOD_MAPPINGS[code]
                print(f"  {code:<6} | {meaning:<40}")
    
    # Analyze actual data
    print(f"\n📊 ANALYSIS OF ACTUAL TRANSACTION DATA:")
    print("=" * 50)
    
    pdf_path = "data/raw/2026-03-04_Statement.pdf"
    parser = AdvancedHSBCParser()
    transactions = parser.parse_transactions_from_pdf(pdf_path)
    
    # Count and analyze payment methods in real data
    payment_stats = {}
    total_amount_by_method = {}
    
    for txn in transactions:
        method = txn.payment_method if txn.payment_method else "Unknown"
        
        if method not in payment_stats:
            payment_stats[method] = 0
            total_amount_by_method[method] = 0
        
        payment_stats[method] += 1
        total_amount_by_method[method] += abs(txn.amount)
    
    print(f"{'Code':<8} | {'Count':<6} | {'Total £':<10} | {'Meaning':<25} | {'Examples'}")
    print("-" * 85)
    
    # Show examples for each method found
    examples = {}
    for txn in transactions[:50]:  # Look through first 50 for examples
        method = txn.payment_method if txn.payment_method else "Unknown"
        if method not in examples:
            examples[method] = txn.description[:30] + "..."
    
    for method in sorted(payment_stats.keys()):
        count = payment_stats[method]
        total = total_amount_by_method[method]
        meaning = PAYMENT_METHOD_MAPPINGS.get(method, "Unknown")
        example = examples.get(method, "No example")
        
        print(f"{method:<8} | {count:<6} | £{total:<9.2f} | {meaning:<25} | {example}")
    
    # Show transaction patterns
    print(f"\n🔍 PAYMENT METHOD PATTERNS:")
    print("-" * 40)
    
    for method in sorted(payment_stats.keys()):
        meaning = PAYMENT_METHOD_MAPPINGS.get(method, "Unknown")
        count = payment_stats[method]
        percentage = (count / len(transactions)) * 100
        
        # Find representative transactions
        method_transactions = [txn for txn in transactions if txn.payment_method == method][:3]
        
        print(f"\n{method} ({meaning}):")
        print(f"  📊 {count} transactions ({percentage:.1f}% of total)")
        print(f"  💰 £{total_amount_by_method[method]:.2f} total value")
        print(f"  📋 Examples:")
        for i, txn in enumerate(method_transactions, 1):
            date_str = txn.date.strftime('%d %b')
            print(f"    {i}. {date_str} - {txn.description[:40]}... (£{abs(txn.amount):.2f})")

def add_payment_method_meanings_to_parser():
    """Show how we could enhance the parser with payment method meanings"""
    
    print(f"\n🔧 ENHANCING PARSER WITH PAYMENT METHOD MEANINGS:")
    print("=" * 55)
    
    enhancement_code = '''
# Add to AdvancedHSBCParser class:

PAYMENT_METHOD_MEANINGS = {
    'VIS': 'Visa Card Payment',
    'DD': 'Direct Debit', 
    ')))': 'Contactless Payment',
    'CR': 'Credit (Money In)',
    'TFR': 'Transfer',
    'FPO': 'Fast Payment Outward', 
    'CHQ': 'Cheque',
    'ATM': 'ATM Withdrawal',
    'BP': 'Bank Payment (Person-to-Person)',
    'OBP': 'Online Bank Payment',
    'SO': 'Standing Order'
}

def get_payment_method_meaning(self, code: str) -> str:
    """Get human-readable meaning for payment method code"""
    return self.PAYMENT_METHOD_MEANINGS.get(code, f"Unknown ({code})")

def get_payment_category(self, code: str) -> str:
    """Categorize payment method"""
    categories = {
        'Card Payment': ['VIS', '))))', 'DEB'],
        'Bank Transfer': ['TFR', 'FPO', 'BP', 'OBP'], 
        'Automated Payment': ['DD', 'SO'],
        'Credit': ['CR'],
        'Other': ['CHQ', 'ATM']
    }
    
    for category, codes in categories.items():
        if code in codes:
            return category
    return 'Unknown'
'''
    
    print(enhancement_code)
    
    print(f"\nThis would allow us to:")
    print(f"  ✅ Get friendly names: 'VIS' → 'Visa Card Payment'")
    print(f"  ✅ Categorize payments: 'DD' → 'Automated Payment'")
    print(f"  ✅ Better reporting and analysis")
    print(f"  ✅ User-friendly transaction descriptions")

if __name__ == "__main__":
    analyze_payment_methods()
    add_payment_method_meanings_to_parser()