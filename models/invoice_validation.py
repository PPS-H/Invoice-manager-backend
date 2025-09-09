from typing import Optional, List, Dict, Any
from pydantic import BaseModel
from enum import Enum
import re
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class ValidationResult(BaseModel):
    is_valid: bool = True
    errors: List[str] = []
    warnings: List[str] = []
    classification: Optional[str] = None
    should_save: bool = True
    requires_manual_review: bool = False

class DocumentType(str, Enum):
    INVOICE = "invoice"
    PAYMENT_RECEIPT = "payment_receipt"
    PAYMENT_NOTIFICATION = "payment_notification"
    STATEMENT = "statement"
    UNKNOWN = "unknown"

class InvoiceValidationService:
    """Centralized validation service implementing all invoice validation rules"""
    
    # Payment notification keywords (Rule 5)
    PAYMENT_NOTIFICATION_KEYWORDS = [
        "payment processed", "payment notification", "billing notification",
        "unsuccessful payment", "payment failed", "transfi payment",
        "payment received", "payment confirmation"
    ]
    
    # Payment receipt keywords (Rule 4)
    PAYMENT_RECEIPT_KEYWORDS = [
        "payment receipt", "payment confirmation", "transaction confirmation",
        "billing receipt", "receipt for payment"
    ]
    
    # Invoice keywords (Rule 6)
    INVOICE_KEYWORDS = [
        "invoice", "bill", "statement", "amount due", "please pay",
        "billing statement", "monthly bill"
    ]
    
    # Vendor amount ranges (Rule 10)
    VENDOR_AMOUNT_RANGES = {
        "github": (5, 500),
        "datadog": (50, 10000),
        "atlassian": (10, 2000),
        "jira": (10, 2000),
        "slack": (5, 1000),
        "zoom": (10, 500),
        "aws": (1, 50000),
        "azure": (1, 50000)
    }
    
    def __init__(self, db_collection):
        self.db = db_collection
    
    async def validate_invoice(self, invoice_data: Dict[str, Any], user_id: str) -> ValidationResult:
        """Main validation method implementing all rules"""
        result = ValidationResult()
        
        # Rule 1: Check for duplicate invoice ID per vendor
        duplicate_check = await self._check_duplicate_invoice_id(
            invoice_data.get("invoice_number"),
            invoice_data.get("vendor_name"),
            user_id
        )
        if not duplicate_check:
            result.is_valid = False
            result.should_save = False
            result.errors.append(f"Duplicate invoice ID '{invoice_data.get('invoice_number')}' for vendor '{invoice_data.get('vendor_name')}'")
            return result
        
        # Rule 2: Check for duplicate email message ID
        email_duplicate_check = await self._check_duplicate_email_message(
            invoice_data.get("email_message_id"),
            user_id
        )
        if not email_duplicate_check:
            result.is_valid = False
            result.should_save = False
            result.errors.append(f"Email message already processed: {invoice_data.get('email_message_id')}")
            return result
        
        # Rule 3: Required fields validation
        required_fields_check = self._validate_required_fields(invoice_data)
        if not required_fields_check["valid"]:
            result.is_valid = False
            result.should_save = False
            result.errors.extend(required_fields_check["errors"])
            return result
        
        # Classification rules (Rules 4-6)
        classification = self._classify_document(
            invoice_data.get("email_subject", ""),
            invoice_data.get("email_sender", ""),
            invoice_data.get("vendor_name", "")
        )
        result.classification = classification
        
        # Only reject payment notifications (not receipts - those are valid)
        # Payment receipts from GitHub, Datadog etc. should be saved
        if classification == DocumentType.PAYMENT_NOTIFICATION:
            result.is_valid = False
            result.should_save = False
            result.errors.append(f"Document classified as {classification.value}, not a genuine invoice")
            return result
        
        # Business logic validations (Rules 10-12)
        business_validation = self._validate_business_logic(invoice_data)
        result.warnings.extend(business_validation["warnings"])
        if business_validation["requires_review"]:
            result.requires_manual_review = True
        
        # Gemini AI validations (Rules 13-15)
        ai_validation = self._validate_gemini_results(invoice_data)
        result.warnings.extend(ai_validation["warnings"])
        if ai_validation["requires_review"]:
            result.requires_manual_review = True
        if not ai_validation["valid"]:
            result.is_valid = False
            result.should_save = False
            result.errors.extend(ai_validation["errors"])
        
        return result
    
    async def _check_duplicate_invoice_id(self, invoice_number: str, vendor_name: str, user_id: str) -> bool:
        """Rule 1: Check if invoice_number + vendor_name combination already exists for user"""
        # If no invoice number provided, we can't check for duplicates - allow it to pass
        if not invoice_number or invoice_number in ['None', 'null', '']:
            logger.warning(f"⚠️ No invoice number provided for {vendor_name} - skipping duplicate check")
            return True  # Allow save since we can't check duplicates without an invoice number
        
        if not vendor_name:
            logger.warning(f"⚠️ No vendor name provided - skipping duplicate check")
            return True
        
        existing = await self.db.find_one({
            "user_id": user_id,
            "vendor_name": vendor_name,
            "invoice_number": invoice_number
        })
        
        return existing is None
    
    async def _check_duplicate_email_message(self, email_message_id: str, user_id: str) -> bool:
        """Rule 2: Check if email message already processed"""
        if not email_message_id:
            return False
        
        existing = await self.db.find_one({
            "user_id": user_id,
            "email_message_id": email_message_id
        })
        
        return existing is None
    
    def _validate_required_fields(self, invoice_data: Dict[str, Any]) -> Dict[str, Any]:
        """Rule 3: Validate required fields - relaxed for AI processing"""
        errors = []
        
        # Essential fields that must be present
        if not invoice_data.get("vendor_name"):
            errors.append("Missing required field: vendor_name")
        
        if not invoice_data.get("total_amount") or invoice_data.get("total_amount") <= 0:
            errors.append("Missing or invalid required field: total_amount")
        
        # Optional fields that can be missing (will be generated/handled later)
        # invoice_number - can be auto-generated if missing
        # invoice_date - can be set to email date if missing
        
        return {"valid": len(errors) == 0, "errors": errors}
    
    def _classify_document(self, email_subject: str, email_sender: str, vendor_name: str) -> DocumentType:
        """Rules 4-6: Classify document type based on subject and sender"""
        subject_lower = email_subject.lower()
        sender_lower = email_sender.lower()
        vendor_lower = vendor_name.lower()
        
        # Rule 5: Payment notification detection
        for keyword in self.PAYMENT_NOTIFICATION_KEYWORDS:
            if keyword in subject_lower:
                # Additional check: if from third-party payment processor
                if any(processor in sender_lower for processor in ["transfi", "stripe", "paypal", "square"]):
                    return DocumentType.PAYMENT_NOTIFICATION
        
        # Rule 4: Payment receipt detection
        for keyword in self.PAYMENT_RECEIPT_KEYWORDS:
            if keyword in subject_lower:
                return DocumentType.PAYMENT_RECEIPT
        
        # Rule 6: Genuine invoice detection
        for keyword in self.INVOICE_KEYWORDS:
            if keyword in subject_lower:
                # Check if sender is from vendor domain
                if vendor_lower in sender_lower or any(domain in sender_lower for domain in [
                    "billing@", "invoices@", "noreply@", "accounts@"
                ]):
                    return DocumentType.INVOICE
        
        return DocumentType.UNKNOWN
    
    def _validate_business_logic(self, invoice_data: Dict[str, Any]) -> Dict[str, Any]:
        """Rules 10-12: Business logic validations"""
        warnings = []
        requires_review = False
        
        # Rule 10: Amount reasonableness
        vendor_name = invoice_data.get("vendor_name", "").lower()
        total_amount = invoice_data.get("total_amount", 0)
        
        for vendor, (min_amount, max_amount) in self.VENDOR_AMOUNT_RANGES.items():
            if vendor in vendor_name:
                if total_amount < min_amount or total_amount > max_amount:
                    warnings.append(f"Amount ${total_amount} outside typical range ${min_amount}-${max_amount} for {vendor}")
                    requires_review = True
                break
        
        # Rule 11: Date validation
        invoice_date = invoice_data.get("invoice_date")
        if invoice_date:
            if isinstance(invoice_date, str):
                try:
                    invoice_date = datetime.fromisoformat(invoice_date.replace('Z', '+00:00'))
                except:
                    warnings.append("Invalid invoice date format")
                    requires_review = True
                    return {"warnings": warnings, "requires_review": requires_review}
            
            current_date = datetime.now()
            if invoice_date > current_date:
                warnings.append("Future invoice date detected")
                requires_review = True
            
            if invoice_date < current_date - timedelta(days=730):  # 2 years
                warnings.append("Very old invoice date (>2 years)")
                requires_review = True
        
        return {"warnings": warnings, "requires_review": requires_review}
    
    def _validate_gemini_results(self, invoice_data: Dict[str, Any]) -> Dict[str, Any]:
        """Rules 13-15: Gemini AI result validations"""
        warnings = []
        errors = []
        requires_review = False
        valid = True
        
        # Rule 13: Confidence threshold
        confidence_score = invoice_data.get("confidence_score", 0)
        if confidence_score < 0.5:
            valid = False
            errors.append(f"AI confidence too low: {confidence_score}")
        elif confidence_score < 0.7:
            warnings.append(f"Low AI confidence: {confidence_score}")
            requires_review = True
        
        # Rule 14: Sender-vendor consistency
        email_sender = invoice_data.get("email_sender", "")
        vendor_name = invoice_data.get("vendor_name", "")
        if vendor_name and email_sender:
            vendor_lower = vendor_name.lower()
            sender_lower = email_sender.lower()
            if vendor_lower not in sender_lower and not any(
                domain in sender_lower for domain in ["billing@", "invoices@", "noreply@"]
            ):
                warnings.append(f"Vendor '{vendor_name}' doesn't match email sender '{email_sender}'")
                requires_review = True
        
        # Rule 15: Invoice number format validation
        invoice_number = invoice_data.get("invoice_number", "")
        if invoice_number:
            # Check for auto-generated patterns
            if invoice_number.startswith("GEMINI-"):
                valid = False
                errors.append("Auto-generated invoice number detected")
            
            # Check for date-only patterns
            if re.match(r'^\d{8}$', invoice_number) or re.match(r'^\d{6}-\d{8}$', invoice_number):
                warnings.append("Suspicious invoice number format (date pattern)")
                requires_review = True
        
        return {
            "valid": valid,
            "errors": errors,
            "warnings": warnings,
            "requires_review": requires_review
        } 