"""
Services module exports
"""

# Import factory functions
from .factory import (
    create_email_scanner,
    create_invoice_processor,
    create_gemini_processor
)

# Import main classes
from .email_scanner import EnhancedEmailScanner
from .invoice_processor import InvoiceProcessor
from .gemini_invoice_processor import GeminiInvoiceProcessor
from .email_body_parser import EmailBodyParser
from .local_storage import LocalStorageService
from .drive_service import DriveService

# Export factory functions as primary interface
__all__ = [
    # Factory functions (preferred)
    'create_email_scanner',
    'create_invoice_processor', 
    'create_gemini_processor',
    
    # Classes (for direct instantiation if needed)
    'EnhancedEmailScanner',
    'InvoiceProcessor',
    'GeminiInvoiceProcessor',
    'EmailBodyParser',
    'LocalStorageService',
    'DriveService'
] 