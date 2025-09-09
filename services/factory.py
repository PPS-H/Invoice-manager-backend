"""
Service Factory Module
Handles proper initialization of all services with correct dependencies
"""
import os
import logging
from typing import Optional

from .email_scanner import EnhancedEmailScanner
from .invoice_processor import InvoiceProcessor
from .gemini_invoice_processor import GeminiInvoiceProcessor

logger = logging.getLogger(__name__)


def create_email_scanner(gemini_api_key: Optional[str] = None) -> EnhancedEmailScanner:
    """
    Create and configure an email scanner instance
    """
    if not gemini_api_key:
        gemini_api_key = os.getenv("GEMINI_API_KEY")
        
    logger.info(f"🔧 Creating EmailScanner - API key present: {bool(gemini_api_key and len(gemini_api_key) > 10)}")
    
    return EnhancedEmailScanner(gemini_api_key=gemini_api_key)


def create_invoice_processor(email_scanner: Optional[EnhancedEmailScanner] = None) -> InvoiceProcessor:
    """
    Create and configure an invoice processor with all dependencies
    """
    # Create email scanner if not provided
    if not email_scanner:
        gemini_api_key = os.getenv("GEMINI_API_KEY")
        logger.info(f"🔧 Creating InvoiceProcessor - GEMINI_API_KEY present: {bool(gemini_api_key and len(gemini_api_key) > 10)}")
        email_scanner = create_email_scanner(gemini_api_key)
    
    # Create invoice processor
    processor = InvoiceProcessor(email_scanner=email_scanner)
    
    # Verify Gemini is available
    if processor.gemini_processor:
        logger.info("✅ InvoiceProcessor created with Gemini support")
    else:
        logger.error("❌ InvoiceProcessor created WITHOUT Gemini support - extraction will fail!")
    
    return processor


def create_gemini_processor(api_key: Optional[str] = None) -> Optional[GeminiInvoiceProcessor]:
    """
    Create Gemini processor with proper error handling
    """
    if not api_key:
        api_key = os.getenv("GEMINI_API_KEY")
    
    if not api_key:
        logger.error("❌ Cannot create Gemini processor - no API key provided")
        return None
    
    try:
        processor = GeminiInvoiceProcessor(api_key)
        logger.info("✅ Gemini processor created successfully")
        return processor
    except Exception as e:
        logger.error(f"❌ Failed to create Gemini processor: {str(e)}")
        return None 