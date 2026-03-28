"""
HSBC-specific bank statement parser with proper transaction separation.
"""

import re
from typing import List, Optional, Tuple
from datetime import datetime
import logging

from .base_parser import BaseBankParser, Transaction

logger = logging.getLogger(__name__)


class HSBCParser(BaseBankParser):
    """Parser specifically designed for HSBC bank statement format."""
    
    def get_bank_name(self) -> str:
        return "HSBC"
    
    def get_bank_patterns(self) -> List[str]:
        return [
            "HSBC", 
            "Contact tel 03457 404 404",
            "www.hsbc.co.uk", 
            "HBUK",
            "International Bank Account Number",
            "GB23HBUK"
        ]
    
    def parse_transactions_from_text(self, text: str) -> List[Transaction]:
        """
        Parse HSBC transactions with proper separation and column awareness.
        
        HSBC format analysis:
        - Multi-line transactions starting with date
        - Payment indicators: VIS, DD, ))), CR
        - Column structure: Date | Description | £Paid out | £Paid in | £Balance
        """
        lines = text.split('\n')
        
        # Find transaction section
        transaction_start = self._find_transaction_start(lines)
        if transaction_start == -1:
            logger.warning("Could not find transaction section in HSBC statement")
            return []
        
        # Parse transactions
        transactions = []
        i = transaction_start
        
        while i < len(lines):
            line = lines[i].strip()
            
            # Skip empty lines and section markers
            if not line or line in ['A', 'BALANCECARRIEDFORWARD', 'BALANCEBROUGHTFORWARD']:
                i += 1
                continue
            
            # Check if this line starts a new transaction (date pattern)
            date_match = re.match(r'(\d{1,2}\s+\w{3}\s+\d{2})', line)
            
            if date_match:
                # Parse this transaction and any sub-transactions
                parsed_transactions, next_i = self._parse_transaction_group(lines, i)
                transactions.extend(parsed_transactions)
                i = next_i
            else:
                i += 1
        
        # Validate and clean transactions
        valid_transactions = []
        for txn in transactions:
            if self.validate_transaction(txn):
                valid_transactions.append(txn)
        
        # Sort by date
        valid_transactions.sort(key=lambda x: x.date)
        
        logger.info(f"HSBC parser extracted {len(valid_transactions)} transactions")
        return valid_transactions
    
    def parse_transactions_from_table(self, tables: List[List[List[str]]]) -> List[Transaction]:
        """HSBC statements typically don't use clean tables, so fall back to text parsing."""
        return []
    
    def _find_transaction_start(self, lines: List[str]) -> int:
        """Find the line where transaction data starts."""
        for i, line in enumerate(lines):
            if 'Payment type and details' in line and '£Paid out' in line:
                # Transaction data starts after the header
                return i + 1
        return -1
    
    def _parse_transaction_group(self, lines: List[str], start_index: int) -> Tuple[List[Transaction], int]:
        """
        Parse a group of transactions starting at the given index.
        
        Returns:
            Tuple of (transactions_list, next_line_index)
        """
        transactions = []
        i = start_index
        
        # Extract date from first line
        first_line = lines[i].strip()
        date_match = re.match(r'(\d{1,2}\s+\w{3}\s+\d{2})', first_line)
        
        if not date_match:
            return [], i + 1
        
        date_str = date_match.group(1)
        transaction_date = self.parse_date_flexible(date_str)
        
        if not transaction_date:
            logger.warning(f"Could not parse date: {date_str}")
            return [], i + 1
        
        # Get remaining part of first line after date
        remaining_first_line = first_line[len(date_str):].strip()
        
        # Collect all lines until next date or end
        transaction_lines = [remaining_first_line] if remaining_first_line else []
        i += 1
        
        while i < len(lines):
            line = lines[i].strip()
            
            # Stop if we hit another transaction (starts with date)
            if re.match(r'\d{1,2}\s+\w{3}\s+\d{2}', line):
                break
            
            # Stop if we hit section markers
            if line in ['BALANCECARRIEDFORWARD', 'BALANCEBROUGHTFORWARD'] or not line:
                i += 1
                continue
            
            transaction_lines.append(line)
            i += 1
        
        # Now parse the transaction lines to separate individual transactions
        sub_transactions = self._separate_sub_transactions(transaction_lines, transaction_date)
        transactions.extend(sub_transactions)
        
        return transactions, i
    
    def _separate_sub_transactions(self, transaction_lines: List[str], date: datetime) -> List[Transaction]:
        """
        Separate multiple transactions that occurred on the same date.
        
        HSBC groups multiple transactions under one date entry. We need to split them
        based on payment type indicators and amount positions.
        """
        if not transaction_lines:
            return []
        
        # Join all lines and analyze for payment patterns
        full_text = ' '.join(transaction_lines)
        
        # Find all payment indicators and their positions
        payment_indicators = ['VIS ', 'DD ', '))) ', 'CR ']
        
        # Split based on payment indicators
        sub_transactions = []
        current_txn_parts = []
        current_payment_method = None
        
        i = 0
        while i < len(transaction_lines):
            line = transaction_lines[i].strip()
            
            # Check if this line starts with a payment indicator
            line_payment_method = self._get_payment_method(line)
            
            if line_payment_method and current_txn_parts:
                # Process previous transaction
                txn = self._create_transaction_from_parts(current_txn_parts, date, current_payment_method)
                if txn:
                    sub_transactions.append(txn)
                
                # Start new transaction
                current_txn_parts = [line]
                current_payment_method = line_payment_method
            else:
                # Continue current transaction
                current_txn_parts.append(line)
                if not current_payment_method:
                    current_payment_method = line_payment_method
            
            i += 1
        
        # Process final transaction
        if current_txn_parts:
            txn = self._create_transaction_from_parts(current_txn_parts, date, current_payment_method)
            if txn:
                sub_transactions.append(txn)
        
        # If we didn't find multiple transactions, treat as single transaction
        if not sub_transactions:
            txn = self._create_transaction_from_parts(transaction_lines, date, None)
            if txn:
                sub_transactions.append(txn)
        
        return sub_transactions
    
    def _get_payment_method(self, line: str) -> Optional[str]:
        """Extract payment method from line start."""
        line = line.strip()
        if line.startswith('VIS '):
            return 'VIS'
        elif line.startswith('DD '):
            return 'DD'
        elif line.startswith('))) '):
            return 'CONTACTLESS'
        elif line.startswith('CR '):
            return 'CR'
        return None
    
    def _create_transaction_from_parts(self, parts: List[str], date: datetime, payment_method: Optional[str]) -> Optional[Transaction]:
        """
        Create a transaction from a list of description parts.
        
        Args:
            parts: List of strings that make up this transaction
            date: Transaction date
            payment_method: Payment method if detected
            
        Returns:
            Transaction object or None if invalid
        """
        if not parts:
            return None
        
        # Join parts to create full description
        full_description = ' '.join(parts).strip()
        raw_description = full_description
        
        # Extract amounts and balance from the parts
        amounts = []
        balance = None
        cleaned_description_parts = []
        
        for part in parts:
            part = part.strip()
            if not part:
                continue
            
            # Look for amounts in this part
            part_amounts, part_text = self._extract_amounts_from_text(part)
            amounts.extend(part_amounts)
            
            if part_text.strip():
                cleaned_description_parts.append(part_text.strip())
        
        # Reconstruct clean description
        clean_description = ' '.join(cleaned_description_parts).strip()
        
        # Determine amount and balance
        transaction_amount = 0.0
        
        if len(amounts) == 1:
            # Single amount - could be paid out or balance
            if any(keyword in clean_description.upper() for keyword in ['VIS', 'DD', ')))']):
                # Likely a paid out amount (expense)
                transaction_amount = -abs(amounts[0])
            else:
                # Could be balance or paid in
                transaction_amount = amounts[0]
        elif len(amounts) == 2:
            # Two amounts - likely paid out and balance
            transaction_amount = -abs(amounts[0])  # First amount is usually paid out
            balance = abs(amounts[1])  # Second amount is usually balance
        elif len(amounts) == 3:
            # Three amounts - paid out, paid in, balance
            transaction_amount = amounts[1] - amounts[0]  # paid in - paid out
            balance = amounts[2]
        
        # Handle special cases
        if 'BALANCEBROUGHTFORWARD' in clean_description.upper():
            transaction_amount = 0.0
            balance = amounts[0] if amounts else None
        
        # Extract merchant and location
        merchant, location = self.extract_merchant_and_location(clean_description)
        
        # Determine transaction type
        transaction_type = 'credit' if transaction_amount >= 0 else 'debit'
        
        return Transaction(
            date=date,
            description=clean_description,
            amount=transaction_amount,
            balance=balance,
            transaction_type=transaction_type,
            payment_method=payment_method,
            merchant=merchant,
            location=location,
            raw_description=raw_description
        )
    
    def _extract_amounts_from_text(self, text: str) -> Tuple[List[float], str]:
        """
        Extract monetary amounts from text and return cleaned text.
        
        Returns:
            Tuple of (amounts_list, cleaned_text)
        """
        # Pattern for monetary amounts: 1,234.56 or 123.45
        amount_pattern = r'(?:£)?\s*(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)'
        
        amounts = []
        remaining_text = text
        
        for match in re.finditer(amount_pattern, text):
            amount_str = match.group(1)
            amount = self.clean_amount(amount_str)
            amounts.append(amount)
            # Remove this amount from the text
            remaining_text = remaining_text.replace(match.group(0), ' ', 1)
        
        # Clean up remaining text
        remaining_text = re.sub(r'\s+', ' ', remaining_text).strip()
        
        return amounts, remaining_text