#!/usr/bin/env python3
"""
Advanced HSBC parser using pdfplumber word-level extraction.

This parser extracts words from PDF pages with their x/y coordinates,
then assigns each word to the correct column (Date, Payment Type, Details,
Paid Out, Paid In, Balance) based on fixed x-position boundaries that are
consistent across all HSBC statement pages.
"""

import pdfplumber
import re
import logging
from collections import defaultdict
from datetime import datetime
from typing import List, Optional, Tuple

from .base_parser import BaseBankParser, Transaction

logger = logging.getLogger(__name__)

# HSBC Payment Method Code Mappings (Complete UK Banking List)
PAYMENT_METHOD_MEANINGS = {
    # Payments & transfers
    'FP': 'Faster Payment',
    'FPS': 'Faster Payment Service',
    'FPI': 'Faster Payment In',
    'FPO': 'Faster Payment Out',
    'TRF': 'Transfer',
    'TFR': 'Transfer',
    'BP': 'Bill Payment',
    'OBP': 'Open Banking Payment',
    'IBP': 'Inter-branch Payment',
    'ITL': 'International Transfer',
    'CHAPS': 'Same-day Large Transfer',
    'CHP': 'Same-day Large Transfer',
    
    # Regular payments
    'DD': 'Direct Debit',
    'DDR': 'Direct Debit Return',
    'SO': 'Standing Order',
    'STO': 'Standing Order',
    'BACS': 'Salary or Business Payment',
    
    # Card & retail
    'POS': 'Card Payment at Shop',
    'VIS': 'Visa Transaction',
    'MC': 'Mastercard Transaction',
    ')))': 'Contactless Payment',
    'CSH': 'Cash',
    'ATM': 'Cash Machine',
    'CDM': 'Cash Deposit Machine',
    
    # Credits & adjustments
    'CR': 'Credit',
    'DR': 'Debit',
    'REV': 'Reversal',
    'COR': 'Correction',
    'INT': 'Interest',
    'CHG': 'Charge',
    'REF': 'Refund',
    
    # Government & income
    'DWP': 'Department for Work and Pensions',
    'SAL': 'Salary',
    'DIV': 'Dividend',
    'CWP': 'Cold Weather Payment',
    
    # Banking channels
    'TEL': 'Telephone Banking',
    'OTR': 'Online Banking Transaction',
    'SBT': 'Screen-based Transaction',
    'TLR': 'Teller Transaction',
    'POC': 'Post Office Counter',
    
    # Legacy/Additional codes
    'CHQ': 'Cheque',
    'FEE': 'Bank Fee',
    'MSC': 'Miscellaneous',
    'PAY': 'Payment In',
    'BGC': 'Bank Giro Credit',
    'CPT': 'Card Payment Terminal',
    'DEB': 'Debit Card Payment',
}

# Payment Method Categories
PAYMENT_CATEGORIES = {
    'Faster Payments': ['FP', 'FPS', 'FPI', 'FPO'],
    'Transfers': ['TRF', 'TFR', 'IBP', 'ITL', 'CHAPS', 'CHP'],
    'Bill Payments': ['BP', 'OBP'],
    'Regular Payments': ['DD', 'DDR', 'SO', 'STO', 'BACS'],
    'Card Payments': ['POS', 'VIS', 'MC', '))))', 'CPT', 'DEB'],
    'Cash': ['CSH', 'ATM', 'CDM'],
    'Credits & Adjustments': ['CR', 'DR', 'REV', 'COR', 'INT', 'CHG', 'REF'],
    'Income': ['DWP', 'SAL', 'DIV', 'CWP', 'PAY', 'BGC'],
    'Banking Channels': ['TEL', 'OTR', 'SBT', 'TLR', 'POC'],
    'Traditional': ['CHQ', 'FEE', 'MSC']
}

# HSBC statement column boundaries (x-coordinates in points).
# Verified identical across all 6 PDFs, all pages (within ±1pt).
# Amount columns are right-aligned; ranges derived from actual word positions:
#   Paid Out: left 354.8-376.1, right 386.8-390.1
#   Paid In:  left 438.5-458.0, right 470.1-472.0
#   Balance:  left 504.8-545.3, right 542.6-557.3
# Gaps between columns: PaidOut-PaidIn = 48pt, PaidIn-Balance = 33pt.
COL_DATE_MAX_X = 110       # Date column: x0 < 110
COL_DESC_MIN_X = 110       # Description (payment type + details): 110 <= x0 < 340
COL_DESC_MAX_X = 340
COL_PAID_OUT_MIN_X = 340   # Paid out: 340 <= x0 < 410
COL_PAID_OUT_MAX_X = 410
COL_PAID_IN_MIN_X = 410    # Paid in: 410 <= x0 < 490
COL_PAID_IN_MAX_X = 490
COL_BALANCE_MIN_X = 490    # Balance: x0 >= 490


class AdvancedHSBCParser(BaseBankParser):
    """
    HSBC parser using pdfplumber word-level extraction with x-position
    column assignment. Includes balance validation against end-of-day
    balance values from the statement.
    """
    
    def get_bank_name(self) -> str:
        return "HSBC"
    
    def get_bank_patterns(self) -> List[str]:
        """HSBC identifiers for bank detection."""
        return [
            "HSBC", 
            "Contact tel 03457 404 404",
            "www.hsbc.co.uk", 
            "Your Statement",
            "International Bank Account Number"
        ]
    
    def get_payment_method_meaning(self, code: str) -> str:
        """Get human-readable meaning for HSBC payment method code."""
        return PAYMENT_METHOD_MEANINGS.get(code, f"Unknown ({code})")
    
    def get_payment_category(self, code: str) -> str:
        """Categorize HSBC payment method into broader groups."""
        for category, codes in PAYMENT_CATEGORIES.items():
            if code in codes:
                return category
        return 'Unknown'
    
    def parse_transactions_from_text(self, text: str) -> List[Transaction]:
        """
        This parser uses direct PDF word extraction, not text parsing.
        """
        logger.warning("AdvancedHSBCParser uses PDF word extraction. Use parse_transactions_from_pdf() instead.")
        return []
    
    def parse_transactions_from_table(self, tables: List[List[List[str]]]) -> List[Transaction]:
        """Not used -- this parser extracts directly from PDF."""
        return []
    
    def parse_transactions_from_pdf(self, pdf_path: str) -> List[Transaction]:
        """
        Parse transactions from PDF using pdfplumber word extraction.
        
        Each word's x-coordinate determines which column it belongs to:
        Date, Payment Type, Details, Paid Out, Paid In, or Balance.
        """
        logger.info(f"Parsing HSBC PDF with pdfplumber word extraction: {pdf_path}")
        
        try:
            # Step 1: Extract structured rows from all pages
            structured_rows = self._extract_rows_from_pdf(pdf_path)
            logger.info(f"Extracted {len(structured_rows)} structured rows from PDF")
            
            # Step 2: Group rows into transactions
            transaction_groups = self._group_rows_into_transactions(structured_rows)
            logger.info(f"Grouped into {len(transaction_groups)} transaction groups")
            
            # Step 3: Parse each group into a Transaction
            transactions = []
            current_date = None
            for group in transaction_groups:
                # Even for skipped groups (e.g. BALANCE BROUGHT FORWARD),
                # preserve any date for subsequent dateless transactions
                for row in group:
                    if row['date'].strip():
                        parsed = self._parse_hsbc_date(row['date'].strip())
                        if parsed:
                            current_date = parsed
                
                txn = self._parse_transaction_from_rows(group, current_date)
                if txn:
                    transactions.append(txn)
                    current_date = txn.date
            
            # Step 4: Validate with balance data
            transactions = self._validate_balances(transactions, structured_rows)
            
            # Sort and filter valid
            transactions.sort(key=lambda x: x.date)
            valid = [t for t in transactions if self.validate_transaction(t)]
            
            logger.info(f"Advanced HSBC parser extracted {len(valid)} valid transactions")
            if valid:
                logger.info(f"Date range: {valid[0].date.date()} to {valid[-1].date.date()}")
            
            return valid
            
        except Exception as e:
            logger.error(f"Error in advanced HSBC parsing: {e}")
            import traceback
            traceback.print_exc()
            return []
    
    # -------------------------------------------------------------------------
    # Step 1: Extract structured rows from PDF
    # -------------------------------------------------------------------------
    
    def _extract_rows_from_pdf(self, pdf_path: str) -> List[dict]:
        """
        Extract words from each page, group by y-position into rows,
        assign each word to a column by x-position.
        
        Payment type codes and merchant/detail text share the same visual
        column (110-340 x range), so they are captured together as
        'description'. The payment code is extracted in post-processing.
        
        Returns a list of row dicts:
        {
            'date': str,           # Date text (e.g. "05 Dec 25")
            'description': str,    # Combined payment type + details text
            'paid_out': str,       # Amount string or empty
            'paid_in': str,        # Amount string or empty
            'balance': str,        # Balance amount string or empty
            'page': int,           # Page number (1-indexed)
            'y': float,            # Y position for ordering
        }
        """
        all_rows = []
        
        with pdfplumber.open(pdf_path) as pdf:
            for page_num, page in enumerate(pdf.pages):
                words = page.extract_words(
                    keep_blank_chars=True,
                    x_tolerance=2,
                    y_tolerance=2
                )
                
                if not words:
                    continue
                
                # Group words by y-position (within 5pt tolerance)
                y_groups = defaultdict(list)
                for w in words:
                    y_key = round(w['top'] / 5) * 5
                    y_groups[y_key].append(w)
                
                # Process each row
                for y_key in sorted(y_groups.keys()):
                    row_words = sorted(y_groups[y_key], key=lambda w: w['x0'])
                    
                    # Assign words to columns based on x-position
                    date_parts = []
                    desc_parts = []
                    paid_out_parts = []
                    paid_in_parts = []
                    balance_parts = []
                    
                    for w in row_words:
                        x0 = w['x0']
                        text = w['text'].strip()
                        if not text:
                            continue
                        
                        if x0 < COL_DATE_MAX_X:
                            date_parts.append(text)
                        elif x0 < COL_DESC_MAX_X:
                            desc_parts.append(text)
                        elif x0 < COL_PAID_OUT_MAX_X:
                            paid_out_parts.append(text)
                        elif x0 < COL_PAID_IN_MAX_X:
                            paid_in_parts.append(text)
                        else:  # x0 >= COL_BALANCE_MIN_X
                            balance_parts.append(text)
                    
                    # Skip completely empty rows
                    if not any([date_parts, desc_parts,
                                paid_out_parts, paid_in_parts, balance_parts]):
                        continue
                    
                    row = {
                        'date': ' '.join(date_parts),
                        'description': ' '.join(desc_parts),
                        'paid_out': ' '.join(paid_out_parts),
                        'paid_in': ' '.join(paid_in_parts),
                        'balance': ' '.join(balance_parts),
                        'page': page_num + 1,
                        'y': y_key,
                    }
                    
                    # Only keep rows that are part of the transaction table area
                    if self._is_transaction_row(row):
                        all_rows.append(row)
        
        return all_rows
    
    def _is_transaction_row(self, row: dict) -> bool:
        """
        Check if a row belongs to the transaction table.
        Filters out header/footer/address/info content.
        """
        desc = row['description'].strip()
        all_text = f"{row['date']} {desc} {row['paid_out']} {row['paid_in']} {row['balance']}"
        
        has_date = bool(row['date'].strip())
        has_desc = bool(desc)
        has_amount = bool(row['paid_out'].strip() or row['paid_in'].strip())
        has_balance = bool(row['balance'].strip())
        
        # BALANCE BROUGHT/CARRIED FORWARD rows -- always keep
        if 'BALANCE' in all_text.upper() and ('BROUGHT' in all_text.upper() or 'CARRIED' in all_text.upper()):
            return True
        
        # Rows with a date plus any other content
        if has_date and (has_desc or has_amount or has_balance):
            return True
        
        # Rows with description plus financial data
        if has_desc and (has_amount or has_balance):
            return True
        
        # Continuation rows: description only (location, reference, etc.)
        if has_desc and not has_date:
            # Skip known non-transaction content (exact substring match)
            skip_phrases = [
                'Contact tel', 'see reverse', 'Text phone', 'www.hsbc',
                'Your Statement', 'Account Nam', 'used by deaf',
                'Your Bank Account', 'Payment type and details',
                'Pay m e nt', 't y pe and de t ails',
                'Sortcode', 'Sheet Num', 'S ortco de', 'S he e t',
                'Acco unt Num', 'Interest and Charges', 'Business Banking',
                'Personal Banking', 'Credit Interest', 'Overdraft interest',
                'individual price', 'apply interest', 'Details of our',
                'accrues during',
            ]
            desc_lower = desc.lower()
            if any(pat.lower() in desc_lower for pat in skip_phrases):
                return False
            # Skip standalone month names / header words (word-boundary match)
            # Only skip if the ENTIRE description is just a month or "details"
            standalone_skip = {
                'december', 'january', 'february', 'march', 'april',
                'may', 'june', 'july', 'august', 'september',
                'october', 'november', 'details',
            }
            if desc_lower in standalone_skip:
                return False
            return True
        
        return False
    
    # -------------------------------------------------------------------------
    # Step 2: Group rows into transactions
    # -------------------------------------------------------------------------
    
    def _group_rows_into_transactions(self, rows: List[dict]) -> List[List[dict]]:
        """
        Group structured rows into transaction groups.
        
        A new transaction starts when we see:
        1. A date in the date column
        2. A payment method code in the payment_type column
        3. A BALANCE BROUGHT/CARRIED FORWARD indicator
        
        Continuation rows (location, reference) belong to the preceding transaction.
        """
        groups = []
        i = 0
        
        while i < len(rows):
            row = rows[i]
            
            # Check if this starts a new transaction
            is_new = self._is_transaction_start(row)
            
            if is_new:
                current_group = [row]
                
                # Collect continuation rows
                j = i + 1
                while j < len(rows):
                    next_row = rows[j]
                    if self._is_transaction_start(next_row):
                        break
                    current_group.append(next_row)
                    j += 1
                
                groups.append(current_group)
                i = j
            else:
                # Orphaned continuation row -- skip
                i += 1
        
        return groups
    
    def _is_transaction_start(self, row: dict) -> bool:
        """Check if a row starts a new transaction."""
        desc = row['description'].strip()
        all_text = f"{row['date']} {desc}"
        
        # BALANCE BROUGHT/CARRIED FORWARD
        if 'BALANCE' in all_text.upper() and ('BROUGHT' in all_text.upper() or 'CARRIED' in all_text.upper()):
            return True
        
        # Has a date
        if row['date'].strip() and self._looks_like_transaction_date(row['date'].strip()):
            return True
        
        # Description starts with a payment method code
        if desc and self._desc_starts_with_payment_code(desc):
            return True
        
        return False
    
    def _desc_starts_with_payment_code(self, desc: str) -> bool:
        """Check if description text starts with a known payment method code."""
        if not desc:
            return False
        if desc.startswith(')))'):
            return True
        first_word = desc.split()[0] if desc.split() else ''
        if first_word.upper() in PAYMENT_METHOD_MEANINGS:
            return True
        return False
    
    def _extract_payment_code(self, desc: str) -> Tuple[str, str]:
        """
        Extract leading payment method code from description text.
        
        Returns (payment_code, remaining_description).
        E.g. "DD AMERICAN EXPRESS" -> ("DD", "AMERICAN EXPRESS")
             "))) TESCO STORES 6292" -> (")))", "TESCO STORES 6292")
             "LONDON" -> ("", "LONDON")
        """
        if not desc:
            return ('', '')
        
        # Handle ))) contactless prefix
        if desc.startswith(')))'):
            remaining = desc[3:].strip()
            return (')))', remaining)
        
        parts = desc.split(None, 1)
        first_word = parts[0] if parts else ''
        rest = parts[1] if len(parts) > 1 else ''
        
        if first_word.upper() in PAYMENT_METHOD_MEANINGS:
            return (first_word, rest)
        
        return ('', desc)
    
    # -------------------------------------------------------------------------
    # Step 3: Parse transaction groups into Transaction objects
    # -------------------------------------------------------------------------
    
    def _parse_transaction_from_rows(self, group: List[dict], current_date: Optional[datetime]) -> Optional[Transaction]:
        """
        Parse a transaction group (1-3 rows) into a Transaction object.
        
        Row structure from HSBC statements:
        - Row 1: date (if first txn of day), payment_type + merchant name in description
        - Row 2: location/reference in description, paid_out or paid_in, balance (if last txn of day)
        - Row 3 (rare): additional reference info
        """
        if not group:
            return None
        
        # Collect data from all rows
        date_text = ''
        desc_parts = []
        paid_out_str = ''
        paid_in_str = ''
        balance_str = ''
        
        for row in group:
            if row['date'].strip():
                date_text = row['date'].strip()
            if row['description'].strip():
                desc_parts.append(row['description'].strip())
            if row['paid_out'].strip():
                paid_out_str = row['paid_out'].strip()
            if row['paid_in'].strip():
                paid_in_str = row['paid_in'].strip()
            # Take the last balance value (end-of-day balance appears on last row)
            if row['balance'].strip():
                balance_str = row['balance'].strip()
        
        full_description = ' '.join(desc_parts)
        
        # Skip BALANCE BROUGHT/CARRIED FORWARD entries
        all_text = f"{date_text} {full_description}"
        if self._is_page_boundary_row(all_text):
            return None
        
        if not full_description:
            return None
        
        # Extract payment code from the FIRST line only (line 1 = main description)
        # Lines 2+ are reference/location details shown separately in the dashboard
        first_line = desc_parts[0] if desc_parts else ''
        reference_lines = desc_parts[1:] if len(desc_parts) > 1 else []
        reference_text = ' '.join(reference_lines).strip() if reference_lines else None
        
        payment_type, merchant_text = self._extract_payment_code(first_line)
        
        # Parse date
        transaction_date = None
        if date_text:
            transaction_date = self._parse_hsbc_date(date_text)
        if not transaction_date:
            transaction_date = current_date
        if not transaction_date:
            logger.warning(f"No date for transaction: {full_description[:50]}")
            return None
        
        # Parse amounts -- column position guarantees correct sign
        paid_out = self._parse_amount(paid_out_str)
        paid_in = self._parse_amount(paid_in_str)
        balance = self._parse_amount(balance_str)
        
        if paid_out:
            amount = -paid_out  # Paid out = debit = negative
            transaction_type = 'debit'
        elif paid_in:
            amount = paid_in   # Paid in = credit = positive
            transaction_type = 'credit'
        else:
            return None  # No amount found
        
        # Build description from first line only
        raw_description = full_description
        
        # Clean description using base parser method (first line only)
        cleaned_description, extracted_payment = self.clean_transaction_description(
            merchant_text if merchant_text else first_line,
            payment_type if payment_type else None
        )
        
        final_payment_method = payment_type if payment_type else extracted_payment
        
        # Extract merchant and location from full text (all lines) for accuracy
        merchant, location = self.extract_merchant_and_location(
            ' '.join(filter(None, [cleaned_description, reference_text]))
        )
        
        return Transaction(
            date=transaction_date,
            description=cleaned_description,
            amount=amount,
            balance=balance,
            transaction_type=transaction_type,
            payment_method=final_payment_method,
            merchant=merchant,
            location=location,
            raw_description=raw_description,
            reference=reference_text
        )
    
    # -------------------------------------------------------------------------
    # Step 4: Balance validation
    # -------------------------------------------------------------------------
    
    def _validate_balances(self, transactions: List[Transaction], structured_rows: List[dict]) -> List[Transaction]:
        """
        Validate transactions against statement balance data.
        
        Uses the opening balance (first BALANCE BROUGHT FORWARD) and
        end-of-day balance values to verify transaction signs are correct.
        Logs warnings for any mismatches.
        """
        # Extract opening and closing balances from structured rows
        opening_balance = None
        closing_balance = None
        
        for row in structured_rows:
            all_text = f"{row['date']} {row['description']}"
            if 'BALANCE' in all_text.upper() and 'BROUGHT' in all_text.upper():
                if opening_balance is None:
                    opening_balance = self._parse_amount(row['balance'])
            if 'BALANCE' in all_text.upper() and 'CARRIED' in all_text.upper():
                closing_balance = self._parse_amount(row['balance'])
        
        if opening_balance is None:
            logger.warning("Could not find opening balance for validation")
            return transactions
        
        closing_str = f"{closing_balance:.2f}" if closing_balance else "N/A"
        logger.info(f"Balance validation: opening={opening_balance:.2f}, closing={closing_str}")
        
        # Walk through transactions with running balance
        running = opening_balance
        mismatches = 0
        
        for txn in transactions:
            running += txn.amount
            
            if txn.balance is not None:
                expected = txn.balance
                if abs(running - expected) > 0.02:
                    mismatches += 1
                    logger.warning(
                        f"Balance mismatch after '{txn.description[:40]}': "
                        f"computed={running:.2f}, expected={expected:.2f}, "
                        f"diff={running - expected:.2f}"
                    )
        
        # Final validation against closing balance
        if closing_balance is not None:
            if abs(running - closing_balance) < 0.02:
                logger.info(f"Balance validation PASSED: final={running:.2f} matches closing={closing_balance:.2f}")
            else:
                net = sum(t.amount for t in transactions)
                logger.warning(
                    f"Balance validation FAILED: opening={opening_balance:.2f} + net={net:.2f} = "
                    f"{opening_balance + net:.2f}, expected closing={closing_balance:.2f}"
                )
        
        if mismatches == 0:
            logger.info("All end-of-day balance checkpoints passed")
        else:
            logger.warning(f"{mismatches} balance checkpoint(s) failed")
        
        return transactions
    
    # -------------------------------------------------------------------------
    # Helper methods
    # -------------------------------------------------------------------------
    
    def _looks_like_transaction_date(self, text: str) -> bool:
        """Check if text looks like a transaction date."""
        if not text or not isinstance(text, str):
            return False
        date_patterns = [
            r'\d{1,2}\s+[A-Za-z]{3}\s+\d{2}',  # "05 Feb 26"
            r'\d{1,2}/\d{1,2}/\d{2,4}',          # "05/02/26"
            r'\d{4}-\d{2}-\d{2}'                  # "2026-02-05"
        ]
        return any(re.search(pattern, text) for pattern in date_patterns)
    
    def _parse_hsbc_date(self, text: str) -> Optional[datetime]:
        """Parse HSBC date format (e.g. '05 Jan 26' or '05 Jan 2026')."""
        if not text:
            return None
        text = text.strip()
        
        match = re.match(r'(\d{1,2})\s+([A-Za-z]{3})\s+(\d{2,4})', text)
        if not match:
            return None
        
        day, month_abbr, year_str = match.groups()
        if len(year_str) == 2:
            year = int(f"20{year_str}")
        else:
            year = int(year_str)
        
        try:
            return datetime.strptime(f"{day} {month_abbr} {year}", "%d %b %Y")
        except ValueError as e:
            logger.warning(f"Failed to parse date '{text}': {e}")
            return None
    
    def _is_page_boundary_row(self, text: str) -> bool:
        """Check if text is a page boundary (not transaction data)."""
        boundary_indicators = [
            'BALANCE BROUGHT FORWARD',
            'BALANCE CARRIED FORWARD',
            'BALANCEBROUGHTFORWARD',
            'BALANCECARRIEDFORWARD',
            'BALANCECARRIED',
            'BALANCEBROUGHT',
        ]
        text_upper = text.upper()
        return any(indicator in text_upper for indicator in boundary_indicators)
    
    def _parse_amount(self, text: str) -> Optional[float]:
        """Parse monetary amount from text."""
        if not text or text.strip() == '' or text.strip() == 'nan':
            return None
        text = str(text).replace('£', '').replace(',', '').strip()
        try:
            return float(text)
        except (ValueError, TypeError):
            return None
    

