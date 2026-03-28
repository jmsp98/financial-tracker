#!/usr/bin/env python3
"""
Test UK merchant categorization with synthetic UK transaction data.
Validates that the updated config properly categorizes UK merchants.
"""

import sys
import os
import yaml

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from categorizer import RuleBasedCategorizer


def load_config():
    """Load the updated configuration."""
    with open('config.yaml', 'r') as f:
        return yaml.safe_load(f)


def test_uk_categorization():
    """Test categorization with realistic UK transactions."""
    
    print("=== UK Merchant Categorization Test ===")
    print()
    
    # Load updated config
    config = load_config()
    categorizer = RuleBasedCategorizer(config)
    
    # Realistic UK transactions based on HSBC patterns
    uk_transactions = [
        # Groceries
        ("VIS TESCO STORES 2586 LONDON", -25.50, "tesco"),
        ("))) SAINSBURY'S LOCAL OXFORD", -15.75, "sainsburys"),
        ("VIS ASDA SUPERMARKET", -45.20, "asda"),
        ("MORRISONS DAILY", -8.50, "morrisons"),
        ("ALDI STORES LIMITED", -22.30, "aldi"),
        
        # Dining
        ("))) COSTA COFFEE LONDON", -4.50, "costa"),
        ("VIS GREGGS PLC", -3.20, "greggs"),
        ("PRET A MANGER", -6.80, "pret"),
        ("VIS NANDO'S RESTAURANT", -18.95, "nandos"),
        ("DELIVEROO", -12.50, "deliveroo"),
        
        # Transportation  
        ("VIS SHELL PETROL STATION", -55.00, "shell"),
        ("TFL TRAVEL CHARGE", -8.50, "tfl"),
        ("VIS BP CONNECT", -48.75, "bp"),
        ("UBER TRIP", -12.30, "uber"),
        
        # Utilities
        ("DD BRITISH GAS", -89.45, "british gas"),
        ("DD OCTOPUS ENERGY", -65.20, "octopus energy"),
        ("DD THAMES WATER", -35.50, "thames water"),
        
        # Bills
        ("DD BT GROUP PLC", -45.00, "bt"),
        ("DD SKY SUBSCRIPTION", -55.00, "sky"),
        ("VIS VIRGIN MEDIA", -42.00, "virgin media"),
        
        # Shopping
        ("VIS AMAZON.CO.UK", -29.99, "amazon"),
        ("VIS JOHN LEWIS", -89.50, "john lewis"),
        ("VIS NEXT RETAIL", -45.00, "next"),
        ("VIS ZARA OXFORD", -65.00, "zara"),
        ("))) BOOTS UK", -15.50, "boots"),
        
        # Entertainment
        ("VIS SPOTIFY LIMITED", -12.99, "spotify"),
        ("DD NETFLIX SERVICES", -15.99, "netflix"),
        ("VIS ODEON CINEMAS", -12.50, "odeon"),
        
        # Healthcare
        ("VIS BOOTS PHARMACY", -8.50, "boots pharmacy"),
        ("SUPERDRUG STORES", -12.30, "superdrug"),
        
        # Income/Credits
        ("CR SALARY PAYMENT", 2500.00, "salary"),
        ("TFR INTERNET TRANSFER", 500.00, "transfer"),
        ("CR REFUND AMAZON", 29.99, "refund"),
        ("CR EMPLOYER_CO RESE", 45.00, "employer_co"),
    ]
    
    print("Testing categorization of UK merchants...")
    
    # Expected categorizations
    expected_categories = {
        "tesco": "groceries",
        "sainsburys": "groceries", 
        "asda": "groceries",
        "morrisons": "groceries",
        "aldi": "groceries",
        "costa": "dining",
        "greggs": "dining",
        "pret": "dining",
        "nandos": "dining",
        "deliveroo": "dining",
        "shell": "transportation",
        "tfl": "transportation",
        "bp": "transportation",
        "uber": "transportation",
        "british gas": "utilities",
        "octopus energy": "utilities", 
        "thames water": "utilities",
        "bt": "bills",
        "sky": "bills",
        "virgin media": "bills",
        "amazon": "shopping",
        "john lewis": "shopping",
        "next": "shopping",
        "zara": "shopping",
        "boots": "shopping",  # General shopping, not healthcare for this context
        "spotify": "entertainment",
        "netflix": "entertainment",
        "odeon": "entertainment",
        "boots pharmacy": "healthcare",
        "superdrug": "healthcare",
        "salary": "income",
        "transfer": "income",
        "refund": "income", 
        "employer_co": "income",
    }
    
    correct = 0
    total = len(uk_transactions)
    
    print()
    for desc, amount, merchant_key in uk_transactions:
        category = categorizer.categorize_transaction(desc, amount, merchant_key)
        expected = expected_categories.get(merchant_key, "other")
        
        status = "✓" if category == expected else "❌"
        print(f"{status} {desc[:40]:<40} -> {category:<12} (expected: {expected})")
        
        if category == expected:
            correct += 1
    
    accuracy = (correct / total) * 100
    print()
    print(f"=== Results ===")
    print(f"Correctly categorized: {correct}/{total} ({accuracy:.1f}%)")
    
    # Category breakdown
    category_counts = {}
    for desc, amount, merchant_key in uk_transactions:
        category = categorizer.categorize_transaction(desc, amount, merchant_key)
        category_counts[category] = category_counts.get(category, 0) + 1
    
    print()
    print("Category distribution:")
    for category, count in sorted(category_counts.items()):
        print(f"  {category}: {count} transactions")
    
    # Validation checks
    print()
    print("=== Validation Checks ===")
    
    checks_passed = 0
    total_checks = 4
    
    if accuracy >= 85:
        print("✓ High categorization accuracy (≥85%)")
        checks_passed += 1
    else:
        print(f"❌ Categorization accuracy too low: {accuracy:.1f}% (should be ≥85%)")
    
    if "other" not in category_counts or category_counts["other"] <= 2:
        print("✓ Few uncategorized transactions") 
        checks_passed += 1
    else:
        print(f"❌ Too many uncategorized: {category_counts.get('other', 0)} (should be ≤2)")
    
    if len(category_counts) >= 6:
        print("✓ Good category distribution (≥6 categories)")
        checks_passed += 1
    else:
        print(f"❌ Poor category distribution: {len(category_counts)} categories (should be ≥6)")
    
    # Check specific UK patterns
    uk_patterns_found = 0
    for desc, amount, merchant_key in uk_transactions:
        category = categorizer.categorize_transaction(desc, amount, merchant_key)
        if merchant_key in ["tesco", "costa", "tfl", "british gas"] and category != "other":
            uk_patterns_found += 1
    
    if uk_patterns_found >= 3:
        print("✓ UK-specific patterns recognized")
        checks_passed += 1
    else:
        print("❌ UK-specific patterns not properly recognized")
    
    print()
    if checks_passed == total_checks:
        print("🎉 UK categorization optimization successful!")
        return True
    else:
        print(f"🔧 Categorization needs improvement ({checks_passed}/{total_checks} checks passed)")
        return False


if __name__ == '__main__':
    success = test_uk_categorization()
    print()
    
    if success:
        print("✅ Financial tracker is optimized for UK banking patterns!")
        print("   Categories updated for HSBC, Tesco, Costa, TfL, British Gas, etc.")
    else:
        print("⚠️  Consider adding more UK merchant keywords to config.yaml")
    
    sys.exit(0 if success else 1)