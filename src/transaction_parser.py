"""
Transaction parser for bank statement data.
"""

import re
from datetime import datetime
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass
import logging

try:
    import pandas as pd
    HAS_PANDAS = True
except ImportError:
    HAS_PANDAS = False

logger = logging.getLogger(__name__)


@dataclass
class Transaction:
    """Represents a single bank transaction."""
    date: datetime
    description: str
    amount: float
    balance: Optional[float] = None
    transaction_type: Optional[str] = None  # 'debit' or 'credit'


class TransactionParser:
    """Parse transactions from bank statement text."""
    
    def __init__(self):
        # Common date patterns
        self.date_patterns = [
            r'\d{2}/\d{2}/\d{4}',  # MM/DD/YYYY
            r'\d{2}-\d{2}-\d{4}',  # MM-DD-YYYY
            r'\d{4}-\d{2}-\d{2}',  # YYYY-MM-DD
            r'\d{2}/\d{2}/\d{2}',  # MM/DD/YY
            r'\d{2}-\d{2}-\d{2}',  # MM-DD-YY
            r'\d{1,2}\s+\w{3}\s+\d{4}',  # 1 Jan 2024
        ]
        
        # Money amount patterns
        self.amount_patterns = [
            r'\$?[\d,]+\.\d{2}',  # $1,234.56 or 1,234.56
            r'\$?[\d,]+',  # $1,234 or 1,234
            r'\(\$?[\d,]+\.\d{2}\)',  # ($1,234.56) for negative amounts
            r'\(\$?[\d,]+\)',  # ($1,234) for negative amounts
        ]
        
        # Common bank statement line patterns
        self.transaction_patterns = [
            # Date + Description + Amount + Balance
            r'(\d{2}/\d{2}/\d{4})\s+(.+?)\s+([\$\(\)\d,\.-]+)\s+([\$\(\)\d,\.-]+)',
            # Date + Description + Debit + Credit + Balance  
            r'(\d{2}/\d{2}/\d{4})\s+(.+?)\s+([\$\(\)\d,\.-]*)\s+([\$\(\)\d,\.-]*)\s+([\$\(\)\d,\.-]+)',
            # Alternative date format
            r'(\d{2}-\d{2}-\d{4})\s+(.+?)\s+([\$\(\)\d,\.-]+)\s+([\$\(\)\d,\.-]+)',
        ]
    
    def clean_amount(self, amount_str: str) -> float:
        """
        Convert amount string to float.
        
        Args:
            amount_str: String representation of amount
            
        Returns:
            Float amount (negative for debits in parentheses)
        """
        if not amount_str or amount_str.strip() == '':
            return 0.0
        
        # Remove whitespace
        amount_str = amount_str.strip()
        
        # Handle parentheses (negative amounts)
        is_negative = amount_str.startswith('(') and amount_str.endswith(')')
        
        # Remove currency symbols and parentheses
        cleaned = re.sub(r'[\$\(\),]', '', amount_str)
        
        try:
            amount = float(cleaned)
            return -amount if is_negative else amount
        except ValueError:
            logger.warning(f"Could not parse amount: {amount_str}")
            return 0.0
    
    def parse_date(self, date_str: str) -> Optional[datetime]:
        """
        Parse date string to datetime object.
        
        Args:
            date_str: String representation of date
            
        Returns:
            Parsed datetime or None if parsing fails
        """
        date_formats = [
            '%m/%d/%Y',
            '%m-%d-%Y',
            '%Y-%m-%d',
            '%m/%d/%y',
            '%m-%d-%y',
            '%d %b %Y',
            '%d %B %Y',
        ]
        
        for fmt in date_formats:
            try:
                return datetime.strptime(date_str.strip(), fmt)
            except ValueError:
                continue
        
        logger.warning(f"Could not parse date: {date_str}")
        return None
    
    def parse_transactions_from_text(self, text: str) -> List[Transaction]:
        """
        Parse transactions from extracted text.
        
        Args:
            text: Raw text from PDF
            
        Returns:
            List of Transaction objects
        """
        transactions = []
        lines = text.split('\n')
        
        # Try HSBC format first (multi-line format)
        hsbc_transactions = self.parse_hsbc_format(lines)
        if hsbc_transactions:
            transactions.extend(hsbc_transactions)
            return transactions
        
        # Fallback to standard single-line patterns
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # Try different transaction patterns
            for pattern in self.transaction_patterns:
                match = re.match(pattern, line)
                if match:
                    try:
                        groups = match.groups()
                        
                        # Basic pattern: date, description, amount, balance
                        if len(groups) >= 3:
                            date_str = groups[0]
                            description = groups[1].strip()
                            amount_str = groups[2] if len(groups) > 2 else ""
                            balance_str = groups[3] if len(groups) > 3 else ""
                            
                            date = self.parse_date(date_str)
                            if date:
                                amount = self.clean_amount(amount_str)
                                balance = self.clean_amount(balance_str) if balance_str else None
                                
                                transaction = Transaction(
                                    date=date,
                                    description=description,
                                    amount=amount,
                                    balance=balance,
                                    transaction_type='debit' if amount < 0 else 'credit'
                                )
                                transactions.append(transaction)
                                break
                    except Exception as e:
                        logger.warning(f"Error parsing line: {line}, Error: {e}")
        
        # Sort transactions by date
        transactions.sort(key=lambda x: x.date)
        
        return transactions
    
    def parse_hsbc_format(self, lines: List[str]) -> List[Transaction]:
        """
        Parse HSBC statement format which has multi-line transactions.
        
        Args:
            lines: List of text lines from PDF
            
        Returns:
            List of Transaction objects
        """
        transactions = []
        
        # Find the start of transaction data
        transaction_start = -1
        for i, line in enumerate(lines):
            if 'Payment type and details' in line or ('Date' in line and '£Paid out' in line):
                transaction_start = i + 1
                break
        
        if transaction_start == -1:
            return []
        
        # Process transactions line by line
        i = transaction_start
        current_transaction = None
        
        while i < len(lines):
            line = lines[i].strip()
            
            # Skip empty lines and section breaks
            if not line or line in ['A', 'BALANCECARRIEDFORWARD', 'BALANCEBROUGHTFORWARD']:
                i += 1
                continue
            
            # Check if this line starts a new transaction (has a date pattern)
            date_match = re.match(r'(\d{1,2}\s+\w{3}\s+\d{2})', line)
            
            if date_match:
                # Save previous transaction if exists
                if current_transaction:
                    transactions.append(current_transaction)
                
                # Start new transaction
                date_str = date_match.group(1)
                date = self.parse_date_hsbc(date_str)
                
                if date:
                    # Extract the rest of the line after the date
                    remaining = line[len(date_str):].strip()
                    
                    # Look for amounts and balance at the end of this or subsequent lines
                    description_parts = []
                    balance = None
                    paid_out = 0.0
                    paid_in = 0.0
                    
                    # Check if amounts are on this line
                    amounts_on_this_line = self.extract_amounts_from_line(remaining)
                    if amounts_on_this_line:
                        remaining, paid_out, paid_in, balance = amounts_on_this_line
                    
                    description_parts.append(remaining)
                    
                    # Look ahead for continuation lines and amounts
                    j = i + 1
                    while j < len(lines) and not re.match(r'\d{1,2}\s+\w{3}\s+\d{2}', lines[j].strip()):
                        next_line = lines[j].strip()
                        
                        if not next_line or next_line in ['BALANCECARRIEDFORWARD', 'BALANCEBROUGHTFORWARD']:
                            break
                        
                        # Check if this line has amounts
                        amounts_on_next_line = self.extract_amounts_from_line(next_line)
                        if amounts_on_next_line:
                            next_line, paid_out, paid_in, balance = amounts_on_next_line
                        
                        if next_line:  # Only add non-empty descriptions
                            description_parts.append(next_line)
                        
                        j += 1
                    
                    # Create transaction
                    description = ' '.join(description_parts).strip()
                    
                    # Calculate net amount (paid_in is positive, paid_out is negative)
                    amount = paid_in - paid_out
                    
                    current_transaction = Transaction(
                        date=date,
                        description=description,
                        amount=amount,
                        balance=balance,
                        transaction_type='credit' if amount > 0 else 'debit'
                    )
                    
                    i = j  # Skip to after the transaction
                else:
                    i += 1
            else:
                i += 1
        
        # Add the last transaction
        if current_transaction:
            transactions.append(current_transaction)
        
        return transactions
    
    def extract_amounts_from_line(self, line: str) -> Optional[Tuple[str, float, float, Optional[float]]]:
        """
        Extract amounts from a line, returning (remaining_text, paid_out, paid_in, balance).
        
        Args:
            line: Line of text that may contain amounts
            
        Returns:
            Tuple of (remaining_text, paid_out, paid_in, balance) or None if no amounts found
        """
        # Look for patterns like "87.41", "1,948.15" at the end of lines
        amount_pattern = r'(.*?)\s+([\d,]+\.?\d*)\s*([\d,]+\.?\d*)?\s*([\d,]+\.?\d*)?$'
        match = re.match(amount_pattern, line)
        
        if match:
            remaining_text = match.group(1).strip()
            amounts = [match.group(i) for i in range(2, 5) if match.group(i)]
            
            # Convert amounts to floats
            float_amounts = []
            for amount_str in amounts:
                if amount_str:
                    cleaned = re.sub(r'[,]', '', amount_str)
                    try:
                        float_amounts.append(float(cleaned))
                    except ValueError:
                        continue
            
            # Determine which amounts are paid_out, paid_in, and balance
            if len(float_amounts) == 1:
                # Could be paid_out or balance
                # If remaining text suggests expense, treat as paid_out
                if any(word in remaining_text.lower() for word in ['vis', 'dd', ')))', 'tesco', 'amazon']):
                    return remaining_text, float_amounts[0], 0.0, None
                else:
                    # Likely balance
                    return remaining_text, 0.0, 0.0, float_amounts[0]
            elif len(float_amounts) == 2:
                # First is likely paid_out, second is balance
                return remaining_text, float_amounts[0], 0.0, float_amounts[1]
            elif len(float_amounts) == 3:
                # paid_out, paid_in, balance
                return remaining_text, float_amounts[0], float_amounts[1], float_amounts[2]
        
        return None
    
    def parse_date_hsbc(self, date_str: str) -> Optional[datetime]:
        """
        Parse HSBC date format (e.g., "05 Jan 26").
        
        Args:
            date_str: Date string in HSBC format
            
        Returns:
            Parsed datetime or None if parsing fails
        """
        try:
            # Handle format like "05 Jan 26" - convert to full year
            parts = date_str.strip().split()
            if len(parts) == 3:
                day, month, year = parts
                # Convert 2-digit year to 4-digit year
                if len(year) == 2:
                    year_int = int(year)
                    # Assume 20xx for years 00-50, 19xx for 51-99
                    if year_int <= 50:
                        year = f"20{year}"
                    else:
                        year = f"19{year}"
                
                full_date_str = f"{day} {month} {year}"
                return datetime.strptime(full_date_str, '%d %b %Y')
        except Exception as e:
            logger.warning(f"Could not parse HSBC date: {date_str}, Error: {e}")
        
        return None
    
    def parse_transactions_from_table(self, tables: List[List[List[str]]]) -> List[Transaction]:
        """
        Parse transactions from extracted tables.
        
        Args:
            tables: List of tables from PDF
            
        Returns:
            List of Transaction objects
        """
        transactions = []
        
        for table in tables:
            if not table or len(table) < 2:
                continue
            
            # Try to identify header row and data rows
            header_row = table[0] if table else []
            data_rows = table[1:] if len(table) > 1 else []
            
            # Look for common column headers
            date_col = None
            desc_col = None  
            amount_col = None
            balance_col = None
            
            for i, header in enumerate(header_row):
                if header and isinstance(header, str):
                    header_lower = header.lower()
                    if 'date' in header_lower:
                        date_col = i
                    elif 'description' in header_lower or 'desc' in header_lower:
                        desc_col = i
                    elif 'amount' in header_lower:
                        amount_col = i
                    elif 'balance' in header_lower:
                        balance_col = i
            
            # Parse data rows
            for row in data_rows:
                if len(row) < 2:
                    continue
                
                try:
                    date_str = row[date_col] if date_col is not None and date_col < len(row) else row[0]
                    description = row[desc_col] if desc_col is not None and desc_col < len(row) else row[1]
                    amount_str = row[amount_col] if amount_col is not None and amount_col < len(row) else (row[2] if len(row) > 2 else "")
                    balance_str = row[balance_col] if balance_col is not None and balance_col < len(row) else (row[3] if len(row) > 3 else "")
                    
                    date = self.parse_date(date_str)
                    if date and description:
                        amount = self.clean_amount(amount_str)
                        balance = self.clean_amount(balance_str) if balance_str else None
                        
                        transaction = Transaction(
                            date=date,
                            description=description.strip(),
                            amount=amount,
                            balance=balance,
                            transaction_type='debit' if amount < 0 else 'credit'
                        )
                        transactions.append(transaction)
                
                except Exception as e:
                    logger.warning(f"Error parsing table row: {row}, Error: {e}")
        
        # Sort transactions by date
        transactions.sort(key=lambda x: x.date)
        
        return transactions
    
    def transactions_to_dataframe(self, transactions: List[Transaction]):
        """
        Convert transactions to pandas DataFrame.
        
        Args:
            transactions: List of Transaction objects
            
        Returns:
            DataFrame with transaction data or list of dicts if pandas not available
        """
        data = []
        for txn in transactions:
            data.append({
                'date': txn.date,
                'description': txn.description,
                'amount': txn.amount,
                'balance': txn.balance,
                'type': txn.transaction_type
            })
        
        if HAS_PANDAS:
            return pd.DataFrame(data)
        else:
            logger.warning("pandas not available, returning list of dictionaries")
            return data