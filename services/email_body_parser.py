import re
import logging
from typing import Dict, Optional, List
from datetime import datetime
from decimal import Decimal
import pdfplumber

logger = logging.getLogger(__name__)

class EmailBodyParser:
    """Parse invoice data from email body content and PDF attachments"""
    
    def __init__(self):
        # Common invoice patterns
        self.amount_patterns = [
            r'\$[\d,]+\.?\d*',  # $1,234.56
            r'USD[\s]*[\d,]+\.?\d*',  # USD 1,234.56
            r'Total[\s]*:?[\s]*\$?[\d,]+\.?\d*',  # Total: $1,234.56
            r'Amount[\s]*:?[\s]*\$?[\d,]+\.?\d*',  # Amount: $1,234.56
            r'Balance[\s]*:?[\s]*\$?[\d,]+\.?\d*',  # Balance: $1,234.56
        ]
        
        self.invoice_number_patterns = [
            r'Invoice[\s]*#?[\s]*([A-Z0-9\-]+)',  # Invoice #INV-123
            r'Invoice[\s]*Number[\s]*:?[\s]*([A-Z0-9\-]+)',  # Invoice Number: INV-123
            r'#([A-Z0-9\-]+)',  # #INV-123
            r'Invoice[\s]*([A-Z0-9\-]+)',  # Invoice INV-123
        ]
        
        self.date_patterns = [
            r'(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})',  # MM/DD/YYYY
            r'(\d{4}[/-]\d{1,2}[/-]\d{1,2})',  # YYYY/MM/DD
            r'(\w+\s+\d{1,2},?\s+\d{4})',  # January 15, 2024
        ]
        
        self.due_date_patterns = [
            r'Due[\s]*Date[\s]*:?[\s]*(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})',
            r'Payment[\s]*Due[\s]*:?[\s]*(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})',
            r'Due[\s]*(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})',
        ]
        
        self.vendor_patterns = [
            r'From[\s]*:?[\s]*([^\n\r]+)',
            r'Sender[\s]*:?[\s]*([^\n\r]+)',
            r'Bill[\s]*From[\s]*:?[\s]*([^\n\r]+)',
        ]
    
    def parse_invoice_from_body(self, email_body: str, email_subject: str, email_sender: str) -> Optional[Dict]:
        """Parse invoice data from email body"""
        try:
            # Clean email body
            clean_body = self._clean_email_body(email_body)
            
            # Extract data
            amount = self._extract_amount(clean_body, email_subject)
            invoice_number = self._extract_invoice_number(clean_body, email_subject)
            invoice_date = self._extract_date(clean_body, email_subject)
            due_date = self._extract_due_date(clean_body)
            vendor_name = self._extract_vendor(clean_body, email_sender)
            
            # Only return if at least amount, invoice_number, and invoice_date are present
            if not (amount and invoice_number and invoice_date):
                logger.info(f"Skipping email as invoice: missing required fields. Subject: {email_subject}, Sender: {email_sender}")
                return None
            
            if not vendor_name:
                vendor_name = self._extract_vendor_from_sender(email_sender)
            
            logger.info(f"Parsed invoice data: vendor={vendor_name}, amount={amount}, invoice_number={invoice_number}")
            
            return {
                "vendor_name": vendor_name,
                "invoice_number": invoice_number,
                "invoice_date": invoice_date,
                "due_date": due_date,
                "amount": float(amount),
                "total_amount": float(amount),
                "currency": "USD",
                "source": "email_body",
                "confidence": self._calculate_confidence(amount, invoice_number, vendor_name)
            }
            
        except Exception as e:
            logger.error(f"Error parsing email body: {str(e)}")
            return None
    
    def _clean_email_body(self, body: str) -> str:
        """Clean email body for parsing"""
        # Remove HTML tags
        body = re.sub(r'<[^>]+>', ' ', body)
        # Remove extra whitespace
        body = re.sub(r'\s+', ' ', body)
        # Remove common email signatures
        body = re.sub(r'--\s*\n.*', '', body, flags=re.DOTALL)
        return body.strip()
    
    def _extract_amount(self, body: str, subject: str) -> Optional[Decimal]:
        """Extract amount from email body or subject"""
        # Search in body first
        for pattern in self.amount_patterns:
            matches = re.findall(pattern, body, re.IGNORECASE)
            if matches:
                try:
                    # Clean the amount string
                    amount_str = re.sub(r'[^\d.]', '', matches[0])
                    return Decimal(amount_str)
                except:
                    continue
        
        # Search in subject
        for pattern in self.amount_patterns:
            matches = re.findall(pattern, subject, re.IGNORECASE)
            if matches:
                try:
                    amount_str = re.sub(r'[^\d.]', '', matches[0])
                    return Decimal(amount_str)
                except:
                    continue
        
        return None
    
    def _extract_invoice_number(self, body: str, subject: str) -> Optional[str]:
        """Extract invoice number from email body or subject"""
        # Search in body first
        for pattern in self.invoice_number_patterns:
            matches = re.findall(pattern, body, re.IGNORECASE)
            if matches:
                return matches[0].strip()
        
        # Search in subject
        for pattern in self.invoice_number_patterns:
            matches = re.findall(pattern, subject, re.IGNORECASE)
            if matches:
                return matches[0].strip()
        
        return None
    
    def _extract_date(self, body: str, subject: str) -> Optional[datetime]:
        """Extract invoice date from email body or subject"""
        # Search in body first
        for pattern in self.date_patterns:
            matches = re.findall(pattern, body, re.IGNORECASE)
            if matches:
                try:
                    return self._parse_date(matches[0])
                except:
                    continue
        
        # Search in subject
        for pattern in self.date_patterns:
            matches = re.findall(pattern, subject, re.IGNORECASE)
            if matches:
                try:
                    return self._parse_date(matches[0])
                except:
                    continue
        
        return None
    
    def _extract_due_date(self, body: str) -> Optional[datetime]:
        """Extract due date from email body"""
        for pattern in self.due_date_patterns:
            matches = re.findall(pattern, body, re.IGNORECASE)
            if matches:
                try:
                    return self._parse_date(matches[0])
                except:
                    continue
        
        return None
    
    def _extract_vendor(self, body: str, sender: str) -> Optional[str]:
        """Extract vendor name from email body or use sender"""
        for pattern in self.vendor_patterns:
            matches = re.findall(pattern, body, re.IGNORECASE)
            if matches:
                return matches[0].strip()
        
        # Use sender email domain as fallback
        if '@' in sender:
            domain = sender.split('@')[1]
            return domain.split('.')[0].title()
        
        return None
    
    def _parse_date(self, date_str: str) -> datetime:
        """Parse various date formats"""
        # Try different date formats
        date_formats = [
            '%m/%d/%Y', '%m/%d/%y',
            '%Y/%m/%d', '%y/%m/%d',
            '%B %d, %Y', '%B %d %Y',
            '%b %d, %Y', '%b %d %Y'
        ]
        
        for fmt in date_formats:
            try:
                return datetime.strptime(date_str.strip(), fmt)
            except:
                continue
        
        raise ValueError(f"Could not parse date: {date_str}")
    
    def _calculate_confidence(self, amount: Optional[Decimal], invoice_number: Optional[str], vendor_name: Optional[str]) -> float:
        """Calculate confidence score for parsed data"""
        confidence = 0.0
        
        if amount:
            confidence += 0.4
        if invoice_number:
            confidence += 0.3
        if vendor_name:
            confidence += 0.2
        if amount and invoice_number:
            confidence += 0.1
        
        return min(confidence, 1.0) 

    def _extract_vendor_from_sender(self, sender: str) -> str:
        """Extract vendor name from sender email"""
        if not sender:
            return "Unknown Vendor"
        
        # Try to extract name from "Name <email@domain.com>" format
        if '<' in sender and '>' in sender:
            name_part = sender.split('<')[0].strip()
            if name_part and len(name_part) > 2:
                return name_part
        
        # Use domain as fallback
        if '@' in sender:
            domain = sender.split('@')[1]
            return domain.split('.')[0].title()
        
        return "Unknown Vendor" 

    def parse_invoice_from_pdf(self, pdf_path: str, email_subject: str, email_sender: str) -> Optional[Dict]:
        """Extract invoice data from a PDF file (attachment)"""
        try:
            # First, try with pdfplumber
            try:
                with pdfplumber.open(pdf_path) as pdf:
                    text = "\n".join(page.extract_text() or "" for page in pdf.pages)
                if text and text.strip():
                    logger.info(f"Extracted text from PDF: {pdf_path} (first 200 chars): {text[:200]}")
                    # Use the same parsing logic as email body
                    return self.parse_invoice_from_body(text, email_subject, email_sender)
                else:
                    logger.info(f"No text extracted from PDF using pdfplumber: {pdf_path}")
            except Exception as pdf_error:
                logger.warning(f"pdfplumber failed for {pdf_path}: {str(pdf_error)}")
                
                # Fallback to PyPDF2 for corrupted PDFs
                try:
                    import PyPDF2
                    with open(pdf_path, 'rb') as file:
                        pdf_reader = PyPDF2.PdfReader(file)
                        text = ""
                        for page in pdf_reader.pages:
                            try:
                                text += page.extract_text() or ""
                            except Exception as page_error:
                                logger.warning(f"Failed to extract text from page in {pdf_path}: {str(page_error)}")
                                continue
                        
                        if text and text.strip():
                            logger.info(f"Extracted text from PDF using PyPDF2 fallback: {pdf_path} (first 200 chars): {text[:200]}")
                            return self.parse_invoice_from_body(text, email_subject, email_sender)
                        else:
                            logger.info(f"No text extracted from PDF using PyPDF2: {pdf_path}")
                            
                except ImportError:
                    logger.warning("PyPDF2 not available for fallback PDF parsing")
                except Exception as fallback_error:
                    logger.warning(f"PyPDF2 fallback also failed for {pdf_path}: {str(fallback_error)}")
            
            # If PDF parsing fails completely, try to extract basic info from filename/metadata
            logger.info(f"Could not extract text from PDF {pdf_path}, attempting metadata extraction")
            return self._extract_from_metadata(pdf_path, email_subject, email_sender)
            
        except Exception as e:
            logger.error(f"Complete failure parsing PDF {pdf_path}: {str(e)}")
            return None
            
    def _extract_from_metadata(self, pdf_path: str, email_subject: str, email_sender: str) -> Optional[Dict]:
        """Extract basic invoice info from email metadata when PDF parsing fails"""
        try:
            import os
            filename = os.path.basename(pdf_path)
            
            # Extract basic info from email metadata
            vendor_name = self._extract_vendor_from_sender(email_sender)
            
            # Try to extract amount from email subject if present
            amount_match = re.search(r'[\$](\d{1,3}(?:,\d{3})*(?:\.\d{2})?)', email_subject)
            amount = float(amount_match.group(1).replace(',', '')) if amount_match else 0.0
            
            return {
                "vendor_name": vendor_name,
                "total_amount": amount,
                "invoice_number": filename.replace('.pdf', ''),
                "description": f"Invoice from {vendor_name}",
                "currency": "USD",
                "amount": amount,
                "invoice_date": None,  # Will be set from email date
                "source": "metadata_fallback"
            }
        except Exception as e:
            logger.error(f"Failed to extract metadata from {pdf_path}: {str(e)}")
            return None 