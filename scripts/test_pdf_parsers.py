#!/usr/bin/env python3
"""
Test different PDF parsing approaches to compare accuracy and extract structure.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

import pdfplumber
import PyPDF2
import pymupdf  # fitz
import tabula
import pandas as pd
from typing import List, Dict
import re

def test_pdfplumber_extraction(pdf_path: str) -> str:
    """Test pdfplumber (current approach)."""
    print("=" * 60)
    print("TESTING PDFPLUMBER (current approach)")
    print("=" * 60)
    
    text = ""
    with pdfplumber.open(pdf_path) as pdf:
        for page_num, page in enumerate(pdf.pages, 1):
            print(f"\nPage {page_num} text:")
            page_text = page.extract_text()
            if page_text:
                text += page_text + "\n"
                # Show first few lines to see structure
                lines = page_text.split('\n')[:10]
                for line in lines:
                    if line.strip():
                        print(f"  {repr(line)}")
                        
            # Also try table extraction
            tables = page.extract_tables()
            if tables:
                print(f"\nPage {page_num} tables found: {len(tables)}")
                for i, table in enumerate(tables):
                    print(f"  Table {i+1}: {len(table)} rows x {len(table[0]) if table else 0} cols")
                    if table and len(table) > 0:
                        for row_idx, row in enumerate(table[:3]):  # First 3 rows
                            print(f"    Row {row_idx}: {row}")
    
    return text

def test_pymupdf_extraction(pdf_path: str) -> str:
    """Test PyMuPDF (fitz) - often better for structured documents."""
    print("=" * 60)
    print("TESTING PYMUPDF (fitz)")
    print("=" * 60)
    
    doc = pymupdf.open(pdf_path)
    text = ""
    
    for page_num in range(len(doc)):
        page = doc[page_num]
        print(f"\nPage {page_num + 1}:")
        
        # Standard text extraction
        page_text = page.get_text()
        text += page_text + "\n"
        
        # Show first few lines
        lines = page_text.split('\n')[:10]
        for line in lines:
            if line.strip():
                print(f"  Text: {repr(line)}")
        
        # Try block-based extraction (preserves layout better)
        blocks = page.get_text("blocks")
        print(f"  Found {len(blocks)} text blocks")
        for i, block in enumerate(blocks[:5]):  # First 5 blocks
            if len(block) >= 5 and isinstance(block[4], str):
                block_text = block[4].strip()
                if block_text:
                    print(f"    Block {i}: {repr(block_text[:100])}")
        
        # Try extracting tables
        try:
            tables = page.find_tables()
            if tables:
                print(f"  Found {len(tables)} tables")
                for i, table in enumerate(tables):
                    print(f"    Table {i}: {table.bbox} - {len(table.extract())} rows")
        except:
            print("  No table detection support")
    
    doc.close()
    return text

def test_tabula_extraction(pdf_path: str):
    """Test tabula-py for table extraction."""
    print("=" * 60)
    print("TESTING TABULA (table-focused)")
    print("=" * 60)
    
    try:
        # Extract all tables
        dfs = tabula.read_pdf(pdf_path, pages='all', multiple_tables=True)
        print(f"Found {len(dfs)} tables across all pages")
        
        for i, df in enumerate(dfs):
            print(f"\nTable {i+1}:")
            print(f"  Shape: {df.shape}")
            print(f"  Columns: {list(df.columns)}")
            print("  First few rows:")
            print(df.head(3).to_string(index=False))
            
            # Look for transaction-like data
            if any('date' in str(col).lower() for col in df.columns):
                print("  → This looks like it contains date information!")
            if any(col for col in df.columns if str(col).lower() in ['amount', 'paid', 'balance']):
                print("  → This looks like it contains financial data!")
                
    except Exception as e:
        print(f"Tabula extraction failed: {e}")

def analyze_transaction_patterns(text: str, parser_name: str):
    """Analyze text for transaction patterns."""
    print(f"\n--- TRANSACTION ANALYSIS for {parser_name} ---")
    
    # Look for date patterns
    date_pattern = r'\d{1,2}\s+\w{3}\s+\d{2}'
    dates = re.findall(date_pattern, text)
    print(f"Date patterns found: {len(dates)}")
    if dates:
        print(f"  Examples: {dates[:5]}")
    
    # Look for payment methods
    payment_methods = ['VIS', 'DD', ')))', 'CR', 'TFR']
    for method in payment_methods:
        count = len(re.findall(f'\\b{method}\\b', text))
        if count > 0:
            print(f"  {method}: {count} occurrences")
    
    # Look for monetary amounts
    amount_pattern = r'\d{1,3}(?:,\d{3})*\.\d{2}'
    amounts = re.findall(amount_pattern, text)
    print(f"Monetary amounts found: {len(amounts)}")
    if amounts:
        print(f"  Examples: {amounts[:10]}")
    
    # Look for specific transactions mentioned
    test_transactions = ['EMPLOYER_CO', 'INCOME_SOURCE.*PET.*GIFT', 'INTERNET TRANSFER']
    for txn in test_transactions:
        matches = re.findall(txn, text, re.IGNORECASE)
        if matches:
            print(f"  Found '{txn}': {len(matches)} times")

def main():
    # Test with the February PDF that should contain the Income_Source transactions
    pdf_path = "./data/raw/2026-02-04_Statement.pdf"
    
    if not os.path.exists(pdf_path):
        print(f"PDF not found: {pdf_path}")
        return
    
    print(f"Testing PDF parsing approaches on: {pdf_path}")
    print(f"File size: {os.path.getsize(pdf_path)} bytes")
    
    # Test each approach
    approaches = [
        ("PDFPlumber", test_pdfplumber_extraction),
        ("PyMuPDF", test_pymupdf_extraction),
    ]
    
    results = {}
    
    for name, func in approaches:
        try:
            text = func(pdf_path)
            results[name] = text
            analyze_transaction_patterns(text, name)
        except Exception as e:
            print(f"{name} failed: {e}")
            results[name] = ""
    
    # Test tabula separately
    test_tabula_extraction(pdf_path)
    
    print("\n" + "=" * 60)
    print("COMPARISON SUMMARY")
    print("=" * 60)
    
    for name, text in results.items():
        if text:
            lines = len(text.split('\n'))
            chars = len(text)
            print(f"{name:12}: {lines:4} lines, {chars:6} characters")
            
            # Check for the problematic Feb 10 transactions
            has_income_source = "INCOME_SOURCE" in text.upper()
            has_internet_transfer = "INTERNET TRANSFER" in text.upper()
            has_feb_10 = "10 Feb 26" in text
            
            print(f"            Feb 10: {has_feb_10}, Income_Source: {has_income_source}, Internet Transfer: {has_internet_transfer}")

if __name__ == "__main__":
    main()