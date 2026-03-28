"""
Test HSBC parser with synthetic bank statement data.
This ensures no real financial data is used in testing.
"""

import unittest
from datetime import datetime
import sys
import os

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from parsers.hsbc_parser import HSBCParser


class TestHSBCParser(unittest.TestCase):
    """Test HSBC parser with synthetic data only."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.parser = HSBCParser()
        
        # Synthetic HSBC statement text (no real financial data)
        self.sample_text = """
# HSBC UK Bank plc
Contact tel: 03457 404 404
www.hsbc.co.uk

Your Bank Account Statement
Account Name: John Doe
Sort Code: 12-34-56
Account Number: 12345678
Statement Period: 01 Jan 25 to 31 Jan 25

Date Payment type and details £Paid out £Paid in £Balance

05 Jan 25 VIS TESCO STORES 1234
LONDON 25.50 1,234.50

05 Jan 25 ))) COSTA COFFEE
LONDON 4.50

06 Jan 25 DD BRITISH GAS
12345678 89.45

07 Jan 25 CR SALARY PAYMENT
EMPLOYER LTD 2,500.00 3,640.55

08 Jan 25 VIS AMAZON.CO.UK
LONDON 19.99

09 Jan 25 ))) SAINSBURYS LOCAL
LONDON 8.75 3,611.81

10 Jan 25 TFR INTERNET TRANSFER
FROM SAVINGS 500.00 4,111.81

BALANCE CARRIED FORWARD 4,111.81
        """
    
    def test_bank_detection(self):
        """Test that HSBC bank is correctly detected."""
        self.assertEqual(self.parser.get_bank_name(), "HSBC")
        
        patterns = self.parser.get_bank_patterns()
        self.assertIn("HSBC", patterns)
        self.assertIn("www.hsbc.co.uk", patterns)
    
    def test_transaction_parsing(self):
        """Test parsing of synthetic transaction data."""
        transactions = self.parser.parse_transactions_from_text(self.sample_text)
        
        # Should extract multiple transactions
        self.assertGreater(len(transactions), 5)
        
        # Check specific transaction types
        debit_transactions = [t for t in transactions if t.transaction_type == 'debit']
        credit_transactions = [t for t in transactions if t.transaction_type == 'credit']
        
        self.assertGreater(len(debit_transactions), 0)
        self.assertGreater(len(credit_transactions), 0)
    
    def test_credit_transaction_detection(self):
        """Test that CR transactions are correctly identified as credits."""
        transactions = self.parser.parse_transactions_from_text(self.sample_text)
        
        # Find salary transaction (should be credit)
        salary_transactions = [t for t in transactions if 'SALARY' in t.description]
        self.assertGreater(len(salary_transactions), 0)
        
        salary_txn = salary_transactions[0]
        self.assertEqual(salary_txn.transaction_type, 'credit')
        self.assertGreater(salary_txn.amount, 0)
    
    def test_debit_transaction_amounts(self):
        """Test that debit transactions have negative amounts."""
        transactions = self.parser.parse_transactions_from_text(self.sample_text)
        
        # Find VIS transactions (should be debits)
        vis_transactions = [t for t in transactions if t.payment_method == 'VIS']
        self.assertGreater(len(vis_transactions), 0)
        
        for txn in vis_transactions:
            self.assertEqual(txn.transaction_type, 'debit')
            self.assertLess(txn.amount, 0)
    
    def test_payment_method_extraction(self):
        """Test extraction of different payment methods."""
        transactions = self.parser.parse_transactions_from_text(self.sample_text)
        
        payment_methods = {t.payment_method for t in transactions if t.payment_method}
        
        # Should detect various payment methods
        expected_methods = {'VIS', 'DD', 'CR', 'CONTACTLESS', 'TFR'}
        self.assertTrue(expected_methods.intersection(payment_methods))
    
    def test_no_real_data_exposure(self):
        """Verify test uses only synthetic data."""
        # This test documents that we use synthetic data only
        test_account_name = "John Doe"
        test_sort_code = "12-34-56"
        
        # These are clearly synthetic - no real person/account
        self.assertIn(test_account_name, self.sample_text)
        self.assertIn(test_sort_code, self.sample_text)


if __name__ == '__main__':
    unittest.main()