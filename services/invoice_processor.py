import re
import logging
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from email.utils import parsedate_to_datetime
from dotenv import load_dotenv
from services.email_scanner import EnhancedEmailScanner as EmailScanner
from services.local_storage import LocalStorageService
from services.email_body_parser import EmailBodyParser
from services.gemini_invoice_processor import GeminiInvoiceProcessor
from core.database import mongodb, connect_to_mongo
from models.invoice import InvoiceModel, InvoiceStatus
from models.invoice_validation import InvoiceValidationService, ValidationResult
from bson import ObjectId
import signal
import threading
import time
import asyncio
from datetime import datetime
from typing import Optional, Dict
from email.utils import parsedate_to_datetime
import logging

# Set up logging
logger = logging.getLogger(__name__)

class InvoiceProcessor:
    """Main invoice processing service"""
    
    def __init__(self, email_scanner=None):
        """Initialize the invoice processor with required services"""
        # Import here to avoid circular imports
        from .email_scanner import EnhancedEmailScanner
        
        # Use provided scanner or create new one
        if email_scanner:
            self.email_scanner = email_scanner
        else:
            # Create default scanner
            gemini_api_key = os.getenv("DEEPSEEK_API_KEY")
            self.email_scanner = EnhancedEmailScanner(gemini_api_key=gemini_api_key)
            
        self.local_storage_service = LocalStorageService()
        
        # Initialize Gemini processor with better logging
        gemini_api_key = os.getenv("DEEPSEEK_API_KEY")
        logger.info(f"🔑 Initializing InvoiceProcessor...")
        logger.info(f"🔑 DEEPSEEK_API_KEY present: {bool(gemini_api_key and len(gemini_api_key) > 10)}")
        
        if gemini_api_key:
            logger.info(f"🔑 Attempting to create GeminiInvoiceProcessor with API key: {gemini_api_key[:10]}...")
            self.gemini_processor = GeminiInvoiceProcessor(gemini_api_key)
            logger.info(f"✅ Gemini processor initialized successfully")
        else:
            self.gemini_processor = None
            logger.error("❌ CRITICAL: DEEPSEEK_API_KEY not found - invoice extraction will fail!")
            logger.error("❌ Please set DEEPSEEK_API_KEY environment variable")
        
        logger.info(f"📊 InvoiceProcessor initialized - Gemini available: {self.gemini_processor is not None}")
        
        # Initialize validation service
        self.validation_service = None
        
        # Ensure database connection
        try:
            if mongodb is None or mongodb.db is None:
                logger.warning("Database connection not established, attempting to connect...")
                # We can't await here in __init__, so we'll handle this in the async methods
        except Exception as e:
            logger.error(f"Database connection check failed: {e}")
        
        self.email_body_parser = EmailBodyParser()
        
        self._stop_requested = threading.Event()
        
        # Set up signal handler for graceful shutdown (only in main thread)
        try:
            if threading.current_thread() is threading.main_thread():
                signal.signal(signal.SIGINT, self._signal_handler)
                signal.signal(signal.SIGTERM, self._signal_handler)
        except ValueError:
            # Signal handlers can only be set in main thread - ignore in background tasks
            logger.debug("Skipping signal handler setup in background thread")
    
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals gracefully"""
        logger.info(f"🛑 Received signal {signum}, stopping email processing...")
        self._stop_requested.set()
    
    def stop_processing(self):
        """Manually stop email processing"""
        logger.info("🛑 Manual stop requested for email processing")
        self._stop_requested.set()
    
    def _check_stop_requested(self):
        """Check if stop was requested"""
        return self._stop_requested.is_set()
    
    async def process_user_emails(self, user_id: str, email_account_id: str, group_emails: Optional[List[str]] = None) -> Dict:
        """
        SIMPLIFIED: Redirect to user preferred vendors approach
        This method is kept for backward compatibility but now uses the new approach
        """
        logger.info(f"🎯 Processing emails using NEW user preferred vendors approach")
        logger.info(f"   User: {user_id}")
        logger.info(f"   Email Account: {email_account_id}")
        
        # Use the new user preferred vendors approach
        return await self.process_user_preferred_vendors(
            user_id=user_id,
            email_account_id=email_account_id
        )
    
    async def _process_single_invoice(self, user_id: str, email_account_id: str, email_data: Dict, source_type: str = "email", source_group_id: Optional[str] = None, source_group_email: Optional[str] = None) -> Optional[Dict]:
        """
        SIMPLIFIED: Process email directly with Gemini - no pre-filtering
        """
        try:
            message_id = email_data.get('message_id', '')
            subject = email_data.get('subject', 'no subject')
            sender = email_data.get('sender', 'unknown')
            
            logger.info("="*80)
            logger.info(f"📧 PROCESSING EMAIL:")
            logger.info(f"  - Message ID: {message_id}")
            logger.info(f"  - Subject: {subject}")
            logger.info(f"  - Sender: {sender}")
            logger.info("="*80)
            
            # Filter out payment notifications (not actual invoices)
            payment_notification_keywords = [
                "payment received", "payment confirmation", "payment notification",
                "unsuccessful payment", "payment failed", "transaction confirmation",
                "payment processed", "billing notification"
            ]
            
            subject_lower = subject.lower()
            if any(keyword in subject_lower for keyword in payment_notification_keywords):
                logger.info(f"⏭️ Skipping payment notification email: {subject[:50]}...")
                return None
            
            # NO PRE-FILTERING for invoices - Send directly to Gemini
            if not self.gemini_processor:
                logger.error("❌ NO GEMINI PROCESSOR AVAILABLE")
                return None
            
            invoice_info = None
            processing_source = "unknown"
            
            # Try PDF processing first if available
            if email_data.get("attachments"):
                pdf_attachments = [att for att in email_data["attachments"] if att["mime_type"] == "application/pdf"]
                
                if pdf_attachments:
                    logger.info(f"📎 Found {len(pdf_attachments)} PDF attachment(s)")
                    
                    for attachment in pdf_attachments:
                        file_content = self.email_scanner.download_attachment(
                            email_data["message_id"],
                            attachment["id"]
                        )
                        
                        if file_content:
                            pdf_result = self.gemini_processor.process_pdf_attachment(
                                file_content,
                                attachment["filename"]
                            )
                            
                            if not pdf_result.get('error'):
                                invoice_info = pdf_result
                                processing_source = "gemini_pdf"
                                logger.info(f"✅ PDF processed successfully")
                                break
            
            # If no PDF or PDF failed, try email content
            if not invoice_info:
                logger.info("📤 Sending email content to Gemini AI...")
                
                gemini_result = self.gemini_processor.process_email_content(
                    email_data.get('body', ''),
                    subject
                )
                
                if not gemini_result.get('error'):
                    invoice_info = gemini_result
                    processing_source = "gemini_email"
                    logger.info("✅ GEMINI: This IS an invoice")
                    logger.info(f"   Vendor: {invoice_info.get('vendor_name')}")
                    logger.info(f"   Amount: ${invoice_info.get('total_amount')}")
                    logger.info(f"   Invoice #: {invoice_info.get('invoice_number')}")
                    logger.info(f"   Confidence: {invoice_info.get('confidence_score')}")
                else:
                    logger.info("❌ GEMINI: This is NOT an invoice")
                    logger.info(f"   Reason: {gemini_result.get('error', 'Unknown')}")
                    logger.info(f"   Email snippet: {email_data.get('snippet', '')[:100]}...")
                    
                    # Even if Gemini fails, try to extract invoice info from email content
                    # This ensures we don't miss text-based invoices
                    logger.info("🔄 Attempting fallback extraction for text-based invoice...")
                    fallback_info = self.process_text_based_invoice(email_data)
                    
                    if fallback_info and fallback_info.get('vendor_name') and fallback_info.get('total_amount'):
                        invoice_info = fallback_info
                        processing_source = "fallback_regex"
                        logger.info("✅ Fallback extraction successful - creating invoice from email content")
                        logger.info(f"   Vendor: {fallback_info.get('vendor_name')}")
                        logger.info(f"   Amount: ${fallback_info.get('total_amount')}")
                    else:
                        logger.info("❌ Fallback extraction also failed - no invoice data found")
                        return None
            
            # Save the invoice
            if invoice_info:
                return await self._save_gemini_invoice(
                    user_id,
                    email_account_id,
                    email_data,
                    invoice_info,
                    invoice_info.get('vendor_name', 'Unknown')
                )
            
            return None
            
        except Exception as e:
            logger.error(f"Error processing invoice: {str(e)}")
            return None
    
    def _extract_invoice_info(self, email_data: Dict) -> Optional[Dict]:
        """Extract invoice information from email"""
        try:
            subject = email_data.get("subject", "").lower()
            body = email_data.get("body", "").lower()
            
            # Extract vendor name with fallback
            vendor_name = self._extract_vendor_name(subject, body)
            if not vendor_name:
                # Fallback vendor name extraction
                vendor_name = self._extract_vendor_name_from_email(email_data)
            
            # Extract amounts with fallback
            amounts = self._extract_amounts(body)
            if not amounts:
                # Default amounts if none found
                amounts = {
                    "total": 0.0,
                    "subtotal": 0.0,
                    "tax": 0.0,
                    "currency": "USD"
                }
            
            # Extract dates with fallback
            invoice_date = self._extract_invoice_date(email_data.get("date", ""))
            if not invoice_date:
                invoice_date = datetime.utcnow()
            
            due_date = self._extract_due_date(body)
            
            # Extract invoice number
            invoice_number = self._extract_invoice_number(subject, body)
            
            # Determine category
            category = self._categorize_invoice(vendor_name, subject, body)
            
            return {
                "vendor_name": vendor_name,
                "invoice_number": invoice_number,
                "invoice_date": invoice_date,
                "due_date": due_date,
                "amount": amounts.get("subtotal", 0.0),
                "tax_amount": amounts.get("tax", 0.0),
                "total_amount": amounts.get("total", 0.0),
                "currency": amounts.get("currency", "USD"),
                "category": category,
                "tags": self._extract_tags(vendor_name, subject, body)
            }
            
        except Exception as e:
            logger.error(f"Error extracting invoice info: {str(e)}")
            # Return minimal valid data instead of None
            return {
                "vendor_name": "Unknown Vendor",
                "invoice_number": None,
                "invoice_date": datetime.utcnow(),
                "due_date": None,
                "amount": 0.0,
                "tax_amount": 0.0,
                "total_amount": 0.0,
                "currency": "USD",
                "category": "other",
                "tags": []
            }

    def process_text_based_invoice(self, email_data: Dict) -> Optional[Dict]:
        """Process text-based invoice from email content (no PDF attachment)"""
        try:
            logger.info(f"📧 Processing text-based invoice from email: {email_data.get('subject', 'No subject')}")
            
            # Use Gemini AI to extract invoice data from email content
            if self.gemini_processor:
                subject = email_data.get("subject", "")
                body = email_data.get("body", "")
                
                # Process with Gemini AI
                invoice_info = self.gemini_processor.process_email_content(body, subject)
                
                if invoice_info and not invoice_info.get('error'):
                    logger.info(f"✅ Gemini successfully extracted invoice data: {invoice_info.get('vendor_name', 'Unknown')}")
                    return invoice_info
                else:
                    logger.warning(f"⚠️ Gemini processing failed, falling back to regex extraction")
            
            # Fallback to regex-based extraction
            return self._extract_invoice_info(email_data)
            
        except Exception as e:
            logger.error(f"Error processing text-based invoice: {str(e)}")
            # Fallback to basic extraction
            return self._extract_invoice_info(email_data)

    async def save_text_invoice_to_drive(self, user_id: str, email_account_id: str, email_data: Dict, invoice_info: Dict) -> Optional[Dict]:
        """Save text-based invoice to inviter's Google Drive using new structure"""
        try:
            from services.drive_service import DriveService
            from services.inviter_service import inviter_service
            
            # Find the inviter user for this email account
            logger.info(f"🔍 Finding inviter for text invoice: {email_account_id}")
            inviter_info = await inviter_service.get_inviter_user_for_email_account(email_account_id)
            
            if not inviter_info:
                logger.error(f"❌ Could not find inviter for email account: {email_account_id}")
                logger.warning(f"⚠️ Skipping Drive storage for text invoice - no inviter found")
                return None
            
            inviter_user_id = inviter_info["user_id"]
            inviter_email = inviter_info.get("email", "Unknown")
            logger.info(f"✅ Found inviter: {inviter_email} (ID: {inviter_user_id})")
            print('inviter_info=========================================iiii', inviter_info)
            print('inviter_user_id=========================================iiii', inviter_user_id)
            print('inviter_email=========================================iiii', inviter_email)
            # Get the inviter's email account for Drive authentication
            inviter_email_account = await mongodb.db["email_accounts"].find_one({
                "user_id": inviter_user_id
            })
            print('inviter_email_account=========================================iiii', inviter_email_account)
            if not inviter_email_account:
                logger.error(f"❌ Could not find inviter's email account for Drive access")
                logger.warning(f"   Inviter User ID: {inviter_user_id}")
                logger.warning(f"   Inviter Email: {inviter_email}")
                return None
            
            if not inviter_email_account.get('access_token'):
                logger.error(f"❌ Inviter's email account has no access token")
                logger.warning(f"   Inviter Email: {inviter_email}")
                logger.warning(f"   Account Status: {inviter_email_account.get('status', 'Unknown')}")
                return None
            
            # Get the scanned email account for folder naming
            scanned_email_account = await mongodb.db["email_accounts"].find_one({
                "_id": ObjectId(email_account_id)
            })
            
            scanned_email = scanned_email_account.get('email') if scanned_email_account else "unknown@email.com"
            
            logger.info(f"📧 Using inviter's email account: {inviter_email}")
            logger.info(f"📧 Scanned email: {scanned_email}")
            
            drive_service = DriveService()
            if drive_service.authenticate(inviter_email_account['access_token'], inviter_email_account.get('refresh_token')):
                logger.info(f"✅ Google Drive authentication successful for inviter: {inviter_email}")
                
                # Save invoice to inviter's Google Drive using new structure
                # Text invoices have no PDF, so pass None for local_file_info
                drive_file_info = await drive_service.save_scanned_email_invoice_new_structure(
                    email_account_id,  # Pass email account ID to find inviter
                    invoice_info.get('vendor_name', 'Unknown'),
                    email_data,
                    invoice_info,
                    None,  # No local file for text-based invoices
                    scanned_email  # Pass scanned email for folder naming
                )
                
                if drive_file_info:
                    logger.info(f"✅ Text invoice saved to inviter's Google Drive: {drive_file_info.get('drive_file_name')}")
                    logger.info(f"   📧 Scanned Email: {scanned_email}")
                    logger.info(f"   👤 Inviter User ID: {drive_file_info.get('inviter_user_id')}")
                    logger.info(f"   📁 Folder Structure: {drive_file_info.get('folder_structure')}")
                    logger.info(f"   📅 Month Folder: {drive_file_info.get('month_folder')}")
                    return drive_file_info
                else:
                    logger.warning("⚠️ Failed to save text invoice to inviter's Google Drive")
            else:
                logger.warning("⚠️ Could not authenticate with Google Drive for inviter")
                logger.warning(f"   Inviter Email: {inviter_email}")
                
        except Exception as e:
            logger.error(f"❌ Error saving text invoice to inviter's Google Drive: {str(e)}")
        
        return None
    
    def _extract_vendor_name(self, subject: str, body: str) -> Optional[str]:
        """Extract vendor name from email"""
        # Common patterns for vendor names
        patterns = [
            r'from\s+([A-Za-z\s&]+?)(?:\s+invoice|\s+receipt|\s+bill)',
            r'invoice\s+from\s+([A-Za-z\s&]+)',
            r'receipt\s+from\s+([A-Za-z\s&]+)',
            r'bill\s+from\s+([A-Za-z\s&]+)',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, subject + " " + body)
            if match:
                vendor = match.group(1).strip()
                if len(vendor) > 2:  # Filter out very short names
                    return vendor.title()
        
        # Fallback: extract from subject
        subject_words = subject.split()
        if len(subject_words) > 2:
            return " ".join(subject_words[:3]).title()
        
        return None
    
    def _extract_amounts(self, body: str) -> Optional[Dict]:
        """Extract monetary amounts from email body"""
        # Currency patterns
        currency_patterns = [
            r'\$(\d+(?:,\d{3})*(?:\.\d{2})?)',  # $1,234.56
            r'USD\s*(\d+(?:,\d{3})*(?:\.\d{2})?)',  # USD 1,234.56
            r'(\d+(?:,\d{3})*(?:\.\d{2})?)\s*dollars',  # 1,234.56 dollars
        ]
        
        amounts = []
        for pattern in currency_patterns:
            matches = re.findall(pattern, body)
            amounts.extend([float(match.replace(',', '')) for match in matches])
        
        if not amounts:
            return None
        
        # Sort amounts (usually total is the largest)
        amounts.sort(reverse=True)
        
        return {
            "total": amounts[0],
            "subtotal": amounts[1] if len(amounts) > 1 else amounts[0],
            "tax": amounts[2] if len(amounts) > 2 else 0,
            "currency": "USD"
        }
    
    def _extract_invoice_date(self, email_date_str: str) -> Optional[datetime]:
        """Extract invoice date from email date string"""
        if not email_date_str:
            return None
        
        try:
            # parsedate_to_datetime can handle various formats, including RFC 2822
            return parsedate_to_datetime(email_date_str)
        except Exception:
            logger.warning(f"Could not parse date string: {email_date_str}")
            return None
    
    def _extract_due_date(self, body: str) -> Optional[datetime]:
        """Extract due date"""
        # Due date patterns
        due_patterns = [
            r'due\s+date[:\s]*(\d{1,2})/(\d{1,2})/(\d{4})',
            r'due\s+date[:\s]*(\d{1,2})-(\d{1,2})-(\d{4})',
            r'payment\s+due[:\s]*(\d{1,2})/(\d{1,2})/(\d{4})',
        ]
        
        for pattern in due_patterns:
            match = re.search(pattern, body)
            if match:
                try:
                    return datetime(int(match.group(3)), int(match.group(1)), int(match.group(2)))
                except ValueError:
                    continue
        
        return None
    
    def _extract_invoice_number(self, subject: str, body: str) -> Optional[str]:
        """Extract invoice number"""
        # Invoice number patterns (case-insensitive)
        patterns = [
            r'invoice\s*#?\s*([A-Z0-9-]+)',
            r'invoice\s+number[:\s]*([A-Z0-9-]+)',
            r'#([A-Z0-9-]+)',
            r'IN-\d{3}-\d{3}-\d{3}',  # Specific Atlassian format
        ]
        
        combined_text = subject + " " + body
        for pattern in patterns:
            match = re.search(pattern, combined_text, re.IGNORECASE)
            if match:
                invoice_num = match.group(1) if match.groups() else match.group(0)
                logger.info(f"Extracted invoice number: {invoice_num} using pattern: {pattern}")
                return invoice_num
        
        logger.warning(f"No invoice number found in subject: {subject[:50]}...")
        return None
    
    def _categorize_invoice(self, vendor_name: str, subject: str, body: str) -> str:
        """Categorize invoice based on vendor and content"""
        text = (vendor_name + " " + subject + " " + body).lower()
        
        categories = {
            "utilities": ["electric", "gas", "water", "internet", "phone", "cable", "utility"],
            "services": ["service", "consulting", "maintenance", "repair", "cleaning"],
            "products": ["product", "equipment", "supplies", "materials", "hardware"],
            "software": ["software", "saas", "subscription", "license", "app"],
            "transportation": ["uber", "lyft", "taxi", "transport", "delivery"],
        }
        
        for category, keywords in categories.items():
            if any(keyword in text for keyword in keywords):
                return category
        
        return "other"
    
    def _extract_tags(self, vendor_name: str, subject: str, body: str) -> List[str]:
        """Extract tags from invoice"""
        tags = []
        text = (vendor_name + " " + subject + " " + body).lower()
        
        # Add vendor-based tags
        if any(word in vendor_name.lower() for word in ["inc", "corp", "llc", "ltd"]):
            tags.append("business")
        
        # Add content-based tags
        if "urgent" in text or "overdue" in text:
            tags.append("urgent")
        
        if "recurring" in text or "monthly" in text:
            tags.append("recurring")
        
        return tags
    
    async def _upload_invoice_attachments(self, user_id: str, vendor_name: str, email_data: Dict, scanned_email: str = None, invoice_date: str = None) -> Optional[Dict]:
        """Save invoice attachments locally with new structure"""
        try:
            if not email_data.get("attachments"):
                return None
            
            # Get the first PDF or image attachment
            for attachment in email_data["attachments"]:
                if attachment["mime_type"] in ["application/pdf", "image/jpeg", "image/png"]:
                    # Download attachment
                    message_id = email_data.get("message_id", "")
                    if not message_id:
                        logger.warning(f"⚠️ No message_id found in email_data, skipping attachment download")
                        continue
                    
                    file_content = self.email_scanner.download_attachment(
                        message_id,
                        attachment["id"]
                    )
                    
                    if file_content:
                        # Use new folder structure if scanned_email is provided
                        if scanned_email:
                            # Get month name from invoice date
                            from services.local_storage import get_month_name_from_date
                            month_name = get_month_name_from_date(invoice_date or email_data.get('date', ''))
                            
                            # Save with new structure
                            local_info = self.local_storage_service.save_invoice_file_new_structure(
                                scanned_email,
                                month_name,
                                vendor_name,
                                file_content,
                                attachment["filename"]
                            )
                            
                            if local_info:
                                return {
                                    'file_id': attachment["id"],
                                    'file_path': local_info['file_path'],
                                    'filename': local_info['filename'],
                                    'file_name': local_info['filename'],
                                    'size': attachment.get('size', 0),
                                    'folder_structure': local_info['folder_structure'],
                                    'month_folder': local_info['month_folder']
                                }
                        else:
                            # Fallback to legacy structure
                            local_info = self.local_storage_service.save_invoice_file(
                                user_id,
                                vendor_name,
                                file_content,
                                attachment["filename"],
                                scanned_email
                            )
                            
                            if local_info:
                                return {
                                    'file_id': attachment["id"],
                                    'file_path': local_info['file_path'],
                                    'filename': local_info['filename'],
                                    'file_name': local_info['filename'],
                                    'size': local_info['size'],
                                    'folder_id': None
                                }
            
            return None
            
        except Exception as e:
            logger.error(f"Error saving attachments locally: {str(e)}")
            return None 
    
    def _ensure_required_fields(self, invoice_info: Dict, email_data: Dict) -> Dict:
        """Ensure all required fields have valid values with fallbacks"""
        try:
            # Ensure vendor_name exists
            if not invoice_info.get("vendor_name"):
                invoice_info["vendor_name"] = self._extract_vendor_name_from_email(email_data)
            
            # Ensure invoice_date exists
            if not invoice_info.get("invoice_date"):
                email_date = email_data.get("date")
                if email_date:
                    invoice_info["invoice_date"] = self._extract_invoice_date(email_date) or datetime.utcnow()
                else:
                    invoice_info["invoice_date"] = datetime.utcnow()
            
            # Ensure amount and total_amount exist
            if not invoice_info.get("amount") or invoice_info["amount"] <= 0:
                invoice_info["amount"] = 0.0
            
            if not invoice_info.get("total_amount") or invoice_info["total_amount"] <= 0:
                invoice_info["total_amount"] = invoice_info.get("amount", 0.0)
            
            # Ensure currency exists
            if not invoice_info.get("currency"):
                invoice_info["currency"] = "USD"
            
            # Ensure tax_amount exists
            if not invoice_info.get("tax_amount"):
                invoice_info["tax_amount"] = 0.0
            
            # Ensure category exists
            if not invoice_info.get("category"):
                invoice_info["category"] = "other"
            
            # Ensure tags exists
            if not invoice_info.get("tags"):
                invoice_info["tags"] = []
            
            return invoice_info
            
        except Exception as e:
            logger.error(f"Error ensuring required fields: {str(e)}")
            # Return minimal valid data
            return {
                "vendor_name": "Unknown Vendor",
                "invoice_date": datetime.utcnow(),
                "amount": 0.0,
                "total_amount": 0.0,
                "currency": "USD",
                "tax_amount": 0.0,
                "category": "other",
                "tags": []
            }
    
    def _extract_vendor_name_from_email(self, email_data: Dict) -> str:
        """Extract vendor name from email data as fallback"""
        try:
            # Try to extract from sender
            sender = email_data.get("sender", "")
            if sender:
                # Extract email domain or name
                if "<" in sender and ">" in sender:
                    # Format: "Name <email@domain.com>"
                    name_part = sender.split("<")[0].strip()
                    if name_part:
                        return name_part
                elif "@" in sender:
                    # Format: "email@domain.com"
                    domain = sender.split("@")[1].split(".")[0]
                    return domain.title()
            
            # Fallback to subject
            subject = email_data.get("subject", "")
            if subject:
                words = subject.split()
                if len(words) >= 2:
                    return " ".join(words[:2]).title()
            
            return "Unknown Vendor"
            
        except Exception as e:
            logger.error(f"Error extracting vendor name from email: {str(e)}")
            return "Unknown Vendor"
    
    async def _try_pdf_extraction(self, user_id: str, email_data: Dict) -> Optional[Dict]:
        """Try to extract invoice data from PDF attachments"""
        try:
            if not email_data.get("attachments"):
                return None
            
            for attachment in email_data["attachments"]:
                if attachment["mime_type"] == "application/pdf":
                    # Download PDF
                    file_content = self.email_scanner.download_attachment(
                        email_data["message_id"],
                        attachment["id"]
                    )
                    
                    if file_content:
                        # Try Gemini PDF processing first
                        if self.gemini_processor:
                            try:
                                pdf_result = self.gemini_processor.process_pdf_attachment(
                                    file_content,
                                    attachment["filename"]
                                )
                                
                                if not pdf_result.get('error'):
                                    logger.info(f"✅ Gemini PDF processing successful")
                                    return pdf_result
                            except Exception as e:
                                logger.warning(f"Gemini PDF processing failed: {e}")
                        
                        # Fallback to traditional PDF parsing
                        try:
                            local_info = self.local_storage_service.save_invoice_file(
                                user_id,
                                email_data.get("sender", "Unknown Vendor"),
                                file_content,
                                attachment["filename"]
                            )
                            
                            if local_info:
                                pdf_path = local_info["file_path"]
                                pdf_invoice_data = self.email_body_parser.parse_invoice_from_pdf(
                                    pdf_path,
                                    email_data.get("subject", ""),
                                    email_data.get("sender", "")
                                )
                                
                                if pdf_invoice_data:
                                    logger.info(f"✅ Traditional PDF parsing successful")
                                    return pdf_invoice_data
                        except Exception as e:
                            logger.warning(f"Traditional PDF parsing failed: {e}")
                            continue
            
            return None
            
        except Exception as e:
            logger.error(f"Error in PDF extraction: {str(e)}")
            return None
    
    def _clean_and_validate_invoice_data(self, invoice_info: Dict, email_data: Dict) -> Optional[Dict]:
        """Clean and validate invoice data before saving"""
        try:
            # Ensure required fields exist with fallbacks
            invoice_info = self._ensure_required_fields(invoice_info, email_data)
            
            # Extract and validate key fields with proper null handling
            vendor_name = (invoice_info.get('vendor_name') or '').strip()
            amount = invoice_info.get('amount', 0.0)
            total_amount = invoice_info.get('total_amount', 0.0)
            invoice_number = (invoice_info.get('invoice_number') or '').strip()
            invoice_date = invoice_info.get('invoice_date')
            
            # Relaxed validation rules - be more permissive for legitimate cases
            if not vendor_name or len(vendor_name.strip()) < 2:
                logger.info(f"Invalid vendor name: '{vendor_name}'")
                return None
            
            # Allow $0.00 amounts for legitimate cases (free trials, credits, refunds)
            if not isinstance(amount, (int, float)) or amount < 0 or amount > 10000000:
                logger.info(f"Invalid amount: {amount}")
                return None
            
            if not isinstance(total_amount, (int, float)) or total_amount < 0 or total_amount > 10000000:
                logger.info(f"Invalid total_amount: {total_amount}")
                return None
            
            # Be more flexible with invoice numbers - allow null for payment confirmations
            # Only reject if invoice_number is explicitly invalid (not just missing)
            if invoice_number is not None and invoice_number != "null" and len(invoice_number.strip()) < 1:
                logger.info(f"Invalid invoice_number: '{invoice_number}'")
                # Don't return None - just set a generated invoice number
                invoice_number = f"PAYMENT-{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}"
                logger.info(f"Generated invoice number for payment confirmation: {invoice_number}")
            
            if not isinstance(invoice_date, datetime):
                logger.info(f"Invalid invoice_date: {invoice_date}")
                return None
            
            # Clean and normalize data
            cleaned_info = {
                "vendor_name": vendor_name.title() if vendor_name.islower() else vendor_name,
                "invoice_number": invoice_number,
                "invoice_date": invoice_date,
                "due_date": invoice_info.get("due_date"),
                "amount": float(amount),
                "total_amount": float(total_amount),
                "tax_amount": float(invoice_info.get("tax_amount", 0.0)),
                "currency": invoice_info.get("currency", "USD").upper(),
                "category": invoice_info.get("category", "other").lower(),
                "tags": invoice_info.get("tags", [])
            }
            
            logger.info(f"✅ Data validation passed: vendor={cleaned_info['vendor_name']}, amount=${cleaned_info['total_amount']}")
            
            return cleaned_info
            
        except Exception as e:
            logger.error(f"Error cleaning and validating invoice data: {str(e)}")
            return None

    async def process_user_preferred_vendors(self, user_id: str, email_account_id: str, days_back: int = 30) -> Dict:
        """
        FAST TARGETED SCANNING FOR USER-SELECTED VENDORS:
        1. Get user's selected vendors from preferences
        2. For each vendor, build targeted email search
        3. Send emails directly to Gemini
        4. Save only invoices (is_invoice: true)
        5. Move to next vendor
        """
        logger.info(f"🎯 STARTING USER PREFERRED VENDOR SCANNING")
        logger.info(f"   User: {user_id}")
        logger.info(f"   Email Account: {email_account_id}")
        
        # Create progress tracking document
        progress_id = await mongodb.db["sync_progress"].insert_one({
            "email_account_id": email_account_id,
            "user_id": user_id,
            "status": "initializing",
            "started_at": datetime.utcnow(),
            "current_action": "Loading user preferences...",
            "vendors_processed": 0,
            "total_vendors": 0,
            "emails_processed": 0,
            "invoices_found": 0,
            "progress_percentage": 0
        })
        
        async def update_progress(**kwargs):
            """Helper to update progress"""
            await mongodb.db["sync_progress"].update_one(
                {"_id": progress_id.inserted_id},
                {"$set": {**kwargs, "updated_at": datetime.utcnow()}}
            )
        
        try:
            # Get user preferences
            await update_progress(current_action="Loading user preferences...")
            preferences = await mongodb.db["user_vendor_preferences"].find_one({
                "user_id": user_id
            })
            
            if not preferences or not preferences.get("selected_vendors"):
                await update_progress(status="error", current_action="No vendors selected")
                return {
                    "success": False,
                    "error": "No vendors selected. Please select vendors first.",
                    "processed_count": 0,
                    "invoices_found": 0
                }
            
            selected_vendors = preferences["selected_vendors"]
            
            # Use provided days_back parameter, or fall back to user preferences, or default to 30
            scan_settings = preferences.get("scan_settings", {"days_back": days_back})
            effective_days_back = days_back if days_back != 30 else scan_settings.get("days_back", 30)
            
            logger.info(f"📋 Found {len(selected_vendors)} selected vendors")
            logger.info(f"📅 Scanning emails from last {effective_days_back} days ({effective_days_back//30} months)")
            await update_progress(
                status="processing",
                total_vendors=len(selected_vendors),
                current_action=f"Processing {len(selected_vendors)} vendors (last {effective_days_back} days)..."
            )
            
            # Get email account
            await update_progress(current_action="Connecting to email account...")
            email_account = await mongodb.db["email_accounts"].find_one({
                "_id": ObjectId(email_account_id),
                "user_id": user_id
            })
            
            if not email_account:
                await update_progress(status="error", current_action="Email account not found")
                return {"success": False, "error": "Email account not found"}
            
            # Authenticate with Gmail
            await update_progress(current_action="Authenticating with Gmail...")
            if not self.email_scanner.authenticate(
                email_account.get("access_token", ""),
                email_account.get("refresh_token")
            ):
                await update_progress(status="error", current_action="Failed to authenticate")
                return {"success": False, "error": "Failed to authenticate with Gmail"}
            
            processed_count = 0
            total_invoices = 0
            errors = []
            
            # Process each selected vendor
            for vendor_index, vendor_info in enumerate(selected_vendors):
                vendor_name = vendor_info["vendor_name"]
                vendor_domains = vendor_info.get("email_domains", [])
                
                progress_pct = int((vendor_index / len(selected_vendors)) * 100)
                await update_progress(
                    current_vendor=vendor_name,
                    vendors_processed=vendor_index,
                    progress_percentage=progress_pct,
                    current_action=f"Processing {vendor_name}..."
                )
                
                logger.info(f"\n{'='*60}")
                logger.info(f"🏢 Processing vendor {vendor_index + 1}/{len(selected_vendors)}: {vendor_name}")
                logger.info(f"   Domains: {vendor_domains}")
                
                if not vendor_domains:
                    logger.warning(f"⚠️ No email domains for vendor {vendor_name}")
                    continue
                
                # Build targeted Gmail search query with better targeting
                # Include both exact domains and vendor name mentions for broader coverage
                domain_queries = [f"from:{domain}" for domain in vendor_domains]
                vendor_name_query = f'"{vendor_name}"'
                
                # Combine domain and vendor name searches
                vendor_query = f"({' OR '.join(domain_queries)} OR {vendor_name_query})"
                since_date = (datetime.utcnow() - timedelta(days=effective_days_back)).strftime('%Y/%m/%d')
                
                # Add invoice-related keywords to filter results
                invoice_keywords = "invoice OR bill OR payment OR receipt OR subscription OR charge"
                final_query = f"({vendor_query}) AND ({invoice_keywords}) after:{since_date}"
                
                logger.info(f"🔍 Gmail query: {final_query}")
                logger.info(f"   Full query length: {len(final_query)} chars")
                await update_progress(current_action=f"Searching {vendor_name} emails...")
                
                try:
                    # Search for vendor emails
                    messages = self.email_scanner.service.users().messages().list(
                        userId='me',
                        q=final_query,
                        maxResults=100  # Increased to find more invoices
                    ).execute()
                    
                    email_messages = messages.get('messages', [])
                    logger.info(f"📧 Found {len(email_messages)} emails for {vendor_name}")
                    
                    vendor_processed = 0
                    vendor_invoices = 0
                    
                    # Process each email
                    for email_index, msg in enumerate(email_messages):
                        await update_progress(
                            current_action=f"Processing {vendor_name} email {email_index + 1}/{len(email_messages)}..."
                        )
                        
                        try:
                            # Get full email data
                            full_message = self.email_scanner.service.users().messages().get(
                                userId='me',
                                id=msg['id']
                            ).execute()
                            
                            email_data = self.email_scanner._parse_email_message(full_message)
                            if not email_data:
                                logger.warning(f"⚠️ Could not parse email {msg['id']}")
                                continue
                            
                            # 📧 LOG EMAIL DETAILS
                            subject = email_data.get('subject', 'No Subject')
                            sender = email_data.get('sender', 'Unknown Sender')
                            message_id = email_data.get('message_id', msg['id'])
                            
                            logger.info(f"\n{'='*60}")
                            logger.info(f"📧 SCANNING EMAIL:")
                            logger.info(f"   📨 Subject: {subject[:80]}{'...' if len(subject) > 80 else ''}")
                            logger.info(f"   👤 Sender: {sender}")
                            logger.info(f"   🔗 Message ID: {message_id}")
                            logger.info(f"   🏢 Target Vendor: {vendor_name}")
                            logger.info(f"{'='*60}")
                            
                            # Get the email date
                            email_date_str = email_data.get('date', '')
                            email_date = parsedate_to_datetime(email_date_str) if email_date_str else None
                            
                            # Log the email date
                            if email_date:
                                print(f"Email date: {email_date}")
                            else:
                                print(f"Could not parse email date: {email_date_str}")
                            
                            # Check if already processed by email ID
                            existing_by_email = await mongodb.db["invoices"].find_one({
                                "user_id": user_id,
                                "email_message_id": email_data.get("message_id", "")
                            })
                            
                            if existing_by_email:
                                logger.info(f"⏭️ SKIPPED: Email already processed")
                                logger.info(f"   📄 Existing invoice: {existing_by_email.get('vendor_name')} - {existing_by_email.get('invoice_number')}")
                                continue
                            
                            # 🤖 SEND TO GEMINI AND VALIDATION
                            logger.info(f"🤖 SENDING TO GEMINI AI...")
                            gemini_result = await self._process_single_invoice(
                                user_id=user_id,
                                email_account_id=email_account_id,
                                email_data=email_data
                            )
                            
                            if gemini_result and gemini_result.get("success"):
                                invoice_num = gemini_result.get('invoice_number', 'No #')
                                amount = gemini_result.get('total_amount', 0)
                                logger.info(f"✅ INVOICE SAVED SUCCESSFULLY!")
                                logger.info(f"   📄 Invoice: {invoice_num}")
                                logger.info(f"   💰 Amount: ${amount}")
                                logger.info(f"   🏢 Vendor: {vendor_name}")
                                vendor_invoices += 1
                                total_invoices += 1
                            else:
                                logger.info(f"⏭️ SKIPPED: Not an invoice or validation failed")
                                logger.info(f"   📝 Reason: Gemini classification or validation rules")
                            
                            vendor_processed += 1
                            processed_count += 1
                            
                        except Exception as e:
                            error_msg = f"Error processing email for {vendor_name}: {str(e)}"
                            logger.error(error_msg)
                            errors.append(error_msg)
                            continue
                    
                    logger.info(f"✅ Completed {vendor_name}: {vendor_processed} emails processed, {vendor_invoices} invoices found")
                    
                except Exception as e:
                    error_msg = f"Error searching emails for {vendor_name}: {str(e)}"
                    logger.error(error_msg)
                    errors.append(error_msg)
                    continue
            
            # Cleanup progress tracking
            await self._cleanup_progress(progress_id.inserted_id)
            
            logger.info(f"\n{'='*60}")
            logger.info(f"🎉 SCANNING COMPLETED")
            logger.info(f"   Vendors processed: {len(selected_vendors)}")
            logger.info(f"   Emails processed: {processed_count}")
            logger.info(f"   Invoices found: {total_invoices}")
            logger.info(f"   Errors: {len(errors)}")
            
            return {
                "success": True,
                "message": f"Scanning completed. {total_invoices} invoices found from {len(selected_vendors)} vendors.",
                "processed_count": processed_count,
                "invoices_found": total_invoices,
                "vendors_processed": len(selected_vendors),
                "errors": errors
            }
            
        except Exception as e:
            await self._cleanup_progress(progress_id.inserted_id)
            logger.error(f"Error in user preferred vendor processing: {str(e)}")
            return {
                "success": False,
                "error": f"Processing failed: {str(e)}",
                "processed_count": 0,
                "invoices_found": 0
            }
    
    async def _cleanup_progress(self, progress_id):
        """Clean up progress document after 5 minutes"""
        await asyncio.sleep(300)  # 5 minutes
        await mongodb.db["sync_progress"].delete_one({"_id": progress_id})

    @staticmethod
    def parse_date_safe(date_str: str) -> datetime:
        """Safely parse a date string in various formats to a datetime object."""
        try:
            # Try different date formats
            formats = [
                '%Y-%m-%d',           # 2025-01-15
                '%Y-%m-%d %H:%M:%S',  # 2025-01-15 10:00:00
                '%d/%m/%Y',           # 15/01/2025
                '%m/%d/%Y',           # 01/15/2025
                '%Y-%m-%dT%H:%M:%S',  # 2025-01-15T10:00:00
                '%Y-%m-%dT%H:%M:%SZ', # 2025-01-15T10:00:00Z
            ]
            
            for fmt in formats:
                try:
                    return datetime.strptime(date_str, fmt)
                except ValueError:
                    continue
            
            # If no format matches, try to extract just the date part
            if ' ' in date_str:
                date_part = date_str.split(' ')[0]
                return datetime.strptime(date_part, '%Y-%m-%d')
            
            raise ValueError(f"Unsupported date format: {date_str}")
            
        except Exception as e:
            logger.warning(f"⚠️ Invalid date format: {date_str}, using UTC now. Error: {str(e)}")
            return datetime.utcnow()

    async def _save_gemini_invoice(self, user_id: str, email_account_id: str, email_data: Dict, gemini_result: Dict, vendor_name: str) -> Optional[Dict]:
        """Save invoice data from Gemini result with validation"""
        try:
            # Initialize validation service if not already done
            if not self.validation_service:
                await connect_to_mongo()
                self.validation_service = InvoiceValidationService(mongodb.db["invoices"])
            
            # Prepare invoice data for validation
            invoice_data = {
                "user_id": user_id,
                "vendor_name": gemini_result.get('vendor_name') or email_data.get('sender', '').split('@')[-1].split('.')[0],
                "invoice_number": gemini_result.get('invoice_number'),
                "total_amount": gemini_result.get('total_amount', 0),
                "invoice_date": gemini_result.get('invoice_date'),
                "email_message_id": email_data.get('message_id', ''),
                "email_subject": email_data.get('subject', ''),
                "email_sender": email_data.get('sender', ''),
                "confidence_score": gemini_result.get('confidence_score', 0.5)
            }
            
            # VALIDATE BEFORE SAVING - Apply all rules
            validation_result = await self.validation_service.validate_invoice(invoice_data, user_id)
            
            if not validation_result.should_save:
                logger.warning(f"🚫 VALIDATION FAILED - Not saving invoice:")
                logger.warning(f"   📨 Subject: {invoice_data.get('email_subject', 'Unknown')[:60]}...")
                logger.warning(f"   👤 Sender: {invoice_data.get('email_sender', 'Unknown')}")
                logger.warning(f"   🏢 Vendor: {invoice_data.get('vendor_name', 'Unknown')}")
                logger.warning(f"   📄 Invoice #: {invoice_data.get('invoice_number', 'None')}")
                for error in validation_result.errors:
                    logger.warning(f"   ❌ {error}")
                return None
            
            if validation_result.warnings:
                logger.warning(f"⚠️ VALIDATION WARNINGS:")
                for warning in validation_result.warnings:
                    logger.warning(f"   ⚠️ {warning}")
            
            if validation_result.requires_manual_review:
                logger.info(f"👀 Invoice requires manual review - setting status to PENDING")
            
            logger.info(f"✅ VALIDATION PASSED - Document classified as: {validation_result.classification}")
            logger.info(f"📝 Proceeding to save invoice to database")
            # Handle invoice number with smart fallback
            invoice_number = gemini_result.get('invoice_number')
            if not invoice_number or invoice_number in ['null', 'None', '']:
                # Generate meaningful invoice number based on email content
                vendor_name = gemini_result.get('vendor_name', 'Unknown')
                amount = gemini_result.get('total_amount', 0)
                date_str = datetime.utcnow().strftime('%Y%m%d')
                invoice_number = f"AUTO-{vendor_name[:3].upper()}-{date_str}-{int(amount*100)}"
                logger.info(f"🔄 Generated invoice number: {invoice_number} (Gemini returned: {gemini_result.get('invoice_number')})")
            
            # Handle dates
            invoice_date = gemini_result.get('invoice_date')
            if isinstance(invoice_date, str):
                try:
                    invoice_date = datetime.strptime(invoice_date, '%Y-%m-%d')
                except:
                    invoice_date = datetime.utcnow()
            elif not invoice_date:
                invoice_date = datetime.utcnow()
            
            # Extract vendor name from Gemini result or email sender
            extracted_vendor_name = gemini_result.get('vendor_name') or email_data.get('sender', '').split('@')[-1].split('.')[0]
            
            # Get email account information early for folder naming
            email_account = None
            try:
                email_account = await mongodb.db["email_accounts"].find_one({
                    "_id": ObjectId(email_account_id)
                })
                
                if email_account:
                    logger.info(f"📧 Found email account: {email_account.get('email', 'Unknown')}")
                    logger.info(f"   Account ID: {email_account.get('_id')}")
                    logger.info(f"   User ID: {email_account.get('user_id')}")
                    logger.info(f"   Provider: {email_account.get('provider')}")
                    logger.info(f"   Status: {email_account.get('status')}")
                    
                    # Verify this account belongs to the correct user
                    if email_account.get('user_id') != user_id:
                        logger.error(f"❌ Email account user_id mismatch!")
                        logger.error(f"   Expected user_id: {user_id}")
                        logger.error(f"   Found user_id: {email_account.get('user_id')}")
                        logger.error(f"   Skipping Drive storage to prevent wrong account usage")
                        email_account = None
                    else:
                        logger.info(f"✅ Email account user_id verified correctly")
                else:
                    logger.warning(f"⚠️ Email account not found by ID: {email_account_id}")
            except Exception as e:
                logger.error(f"❌ Error looking up email account: {str(e)}")
                email_account = None
            
            # Save any PDF attachments
            local_file_info = None
            if email_data.get('attachments'):
                local_file_info = await self._upload_invoice_attachments(
                    user_id, 
                    extracted_vendor_name,
                    email_data,
                    email_account.get('email') if email_account else None,  # Pass scanned email account address for folder naming
                    gemini_result.get('invoice_date')  # Pass invoice date for month folder
                )
            
            # Save to Google Drive (only for invoices with PDF attachments)
            drive_file_info = None
            try:
                from services.drive_service import DriveService
                from services.inviter_service import inviter_service
                
                logger.info(f"🚀 Attempting to save invoice to Google Drive...")
                logger.info(f"   User ID: {user_id}")
                logger.info(f"   Email Account ID: {email_account_id}")
                logger.info(f"   Vendor: {extracted_vendor_name}")
                
                # Find the inviter user for this email account
                logger.info(f"🔍 Finding inviter for email account: {email_account_id}")
                inviter_info = await inviter_service.get_inviter_user_for_email_account(email_account_id)
                
                if not inviter_info:
                    logger.error(f"❌ Could not find inviter for email account: {email_account_id}")
                    logger.warning(f"⚠️ Skipping Drive storage - no inviter found")
                else:
                    inviter_user_id = inviter_info["user_id"]
                    inviter_email = inviter_info.get("email", "Unknown")
                    logger.info(f"✅ Found inviter: {inviter_email} (ID: {inviter_user_id})")
                    
                    # Get the inviter's email account for Drive authentication
                    inviter_email_account = await mongodb.db["email_accounts"].find_one({
                        "user_id": inviter_user_id
                    })
                    if not inviter_email_account:
                        logger.error(f"❌ Could not find inviter's email account for Drive access")
                        logger.warning(f"   Inviter User ID: {inviter_user_id}")
                        logger.warning(f"   Inviter Email: {inviter_email}")
                    elif not inviter_email_account.get('access_token'):
                        logger.error(f"❌ Inviter's email account has no access token")
                        logger.warning(f"   Inviter Email: {inviter_email}")
                        logger.warning(f"   Account Status: {inviter_email_account.get('status', 'Unknown')}")
                    else:
                        logger.info(f"📧 Using inviter's email account: {inviter_email}")
                        logger.info(f"   Access Token: {'Present' if inviter_email_account.get('access_token') else 'Missing'}")
                        logger.info(f"   Refresh Token: {'Present' if inviter_email_account.get('refresh_token') else 'Missing'}")
                        
                        drive_service = DriveService()
                        logger.info(f"🔐 Authenticating with Google Drive for inviter: {inviter_email}")
                        
                        auth_result = drive_service.authenticate(
                            inviter_email_account['access_token'], 
                            inviter_email_account.get('refresh_token')
                        )
                        
                        if auth_result:
                            logger.info(f"✅ Google Drive authentication successful for inviter: {inviter_email}")
                            
                            # Save invoice to inviter's Google Drive using new structure
                            logger.info(f"📁 Saving invoice to inviter's Google Drive using new structure...")
                            logger.info(f"   Inviter Email: {inviter_email}")
                            logger.info(f"   Scanned Email: {email_account.get('email') if email_account else 'Unknown'}")
                            
                            drive_file_info = await drive_service.save_scanned_email_invoice_new_structure(
                                email_account_id,  # Pass email account ID to find inviter
                                extracted_vendor_name,
                                email_data,
                                gemini_result,
                                local_file_info,  # Pass local file info for PDF uploads
                                email_account.get('email') if email_account else None  # Pass scanned email account address for folder naming
                            )
                            
                            if drive_file_info:
                                logger.info(f"✅ Invoice saved to inviter's Google Drive successfully!")
                                logger.info(f"   📧 Scanned Email: {email_account.get('email')}")
                                logger.info(f"   👤 Inviter User ID: {drive_file_info.get('inviter_user_id')}")
                                logger.info(f"   📄 File Name: {drive_file_info.get('drive_file_name')}")
                                logger.info(f"   📁 Folder Structure: {drive_file_info.get('folder_structure')}")
                                logger.info(f"   📅 Month Folder: {drive_file_info.get('month_folder')}")
                                logger.info(f"   🔗 Drive File ID: {drive_file_info.get('drive_file_id')}")
                            else:
                                logger.warning("⚠️ Failed to save invoice to inviter's Google Drive - no file info returned")
                        else:
                            logger.warning("⚠️ Google Drive authentication failed for inviter")
                            logger.warning(f"   Inviter Email: {inviter_email}")
                            logger.warning(f"   Access Token: {inviter_email_account['access_token'][:20]}...")
                            logger.warning(f"   Refresh Token: {'Present' if inviter_email_account.get('refresh_token') else 'Missing'}")
                        
            except Exception as e:
                logger.error(f"❌ Error saving to Google Drive: {str(e)}")
                logger.error(f"   Exception type: {type(e).__name__}")
                import traceback
                logger.error(f"   Traceback: {traceback.format_exc()}")
                # Continue with local storage even if Drive fails
            
            # Log Drive storage result
            if drive_file_info:
                logger.info(f"✅ Invoice successfully saved to Google Drive")
                logger.info(f"   📄 Drive File: {drive_file_info.get('drive_file_name')}")
                logger.info(f"   📁 Drive Folder: {drive_file_info.get('folder_structure')}")
            else:
                if local_file_info:
                    logger.info(f"📝 Invoice saved locally only (Drive storage failed or skipped)")
                else:
                    logger.info(f"📝 Text-based invoice - no PDF to save to Drive")
            
            # Create invoice model with confidence score and validation status
            confidence_score = gemini_result.get('confidence_score', 0.5)
            due_date_raw = gemini_result.get('due_date')
            due_date = InvoiceProcessor.parse_date_safe(due_date_raw) if isinstance(due_date_raw, str) else due_date_raw or datetime.utcnow()
            # Determine status based on validation result and confidence
            if validation_result.requires_manual_review or confidence_score < 0.7:
                status = InvoiceStatus.PENDING
            else:
                status = InvoiceStatus.PROCESSED
            
            invoice_model = InvoiceModel(
                user_id=user_id,
                email_account_id=email_account_id,
                vendor_name=extracted_vendor_name,
                invoice_number=invoice_number,
                invoice_date=invoice_date,
                due_date=due_date,
                amount=gemini_result.get('amount', gemini_result.get('total_amount', 0)),
                currency=gemini_result.get('currency', 'USD'),
                tax_amount=gemini_result.get('tax_amount', 0),
                total_amount=gemini_result.get('total_amount', 0),
                status=status,
                category=gemini_result.get('category', 'other'),
                email_subject=email_data.get('subject', ''),
                email_sender=email_data.get('sender', ''),
                email_date=parsedate_to_datetime(email_data.get('date', '')) if email_data.get('date') else None,
                email_message_id=email_data.get('message_id', ''),
                local_file_path=local_file_info.get('file_path') if local_file_info else None,
                local_file_name=local_file_info.get('filename') if local_file_info else None,
                drive_file_id=drive_file_info.get('drive_file_id') if drive_file_info else None,
                drive_file_name=drive_file_info.get('drive_file_name') if drive_file_info else None,
                drive_folder_id=drive_file_info.get('drive_folder_id') if drive_file_info else None,
                drive_view_link=drive_file_info.get('web_view_link') if drive_file_info else None,  # Store Drive view link
                processed_at=datetime.utcnow(),
                processing_source='gemini_vendor_search'
            )
            
            # Note: Duplicate checking is now handled by validation service above
            
            # Insert to database
            invoice_dict = invoice_model.model_dump(by_alias=True)
            if invoice_dict.get("_id") is None:
                del invoice_dict["_id"]
            
            # Add extra validation fields
            invoice_dict['confidence_score'] = confidence_score
            invoice_dict['needs_review'] = validation_result.requires_manual_review or confidence_score < 0.7
            invoice_dict['validation_warnings'] = validation_result.warnings
            invoice_dict['document_classification'] = validation_result.classification
            
            result = await mongodb.db["invoices"].insert_one(invoice_dict)
            
            logger.info(f"✅ INVOICE SAVED SUCCESSFULLY: {result.inserted_id}")
            logger.info(f"   📋 Classification: {validation_result.classification}")
            logger.info(f"   🎯 Confidence: {confidence_score}")
            logger.info(f"   👀 Needs Review: {validation_result.requires_manual_review}")
            invoice_dict['_id'] = result.inserted_id
            
            return invoice_dict
            
        except Exception as e:
            logger.error(f"Error saving Gemini invoice: {str(e)}")
            return None
