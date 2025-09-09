import os
import logging
import hashlib
from typing import Optional, Dict
from datetime import datetime

logger = logging.getLogger(__name__)

def get_month_name_from_date(date_str: str) -> str:
    """Get month name from date string"""
    try:
        if isinstance(date_str, str):
            # Try different date formats
            for fmt in ['%Y-%m-%d', '%d/%m/%Y', '%m/%d/%Y', '%Y-%m-%d %H:%M:%S']:
                try:
                    date_obj = datetime.strptime(date_str.split(' ')[0], fmt)
                    return date_obj.strftime('%B_%Y')  # e.g., "January_2025"
                except ValueError:
                    continue
        return "Unknown_Month"
    except Exception:
        return "Unknown_Month"

class LocalStorageService:
    """Local file storage service for invoice attachments"""
    
    def __init__(self):
        self.base_path = "uploads"
        self._ensure_base_directory()
    
    def _ensure_base_directory(self):
        """Ensure the base upload directory exists"""
        os.makedirs(self.base_path, exist_ok=True)
    
    def create_invoice_manager_directory(self) -> str:
        """Create main 'Invoice Manager' directory"""
        invoice_manager_path = os.path.join(self.base_path, "Invoice Manager")
        os.makedirs(invoice_manager_path, exist_ok=True)
        return invoice_manager_path
    
    def create_invoices_directory(self) -> str:
        """Create 'Invoices' directory inside Invoice Manager"""
        invoice_manager_path = self.create_invoice_manager_directory()
        invoices_path = os.path.join(invoice_manager_path, "Invoices")
        os.makedirs(invoices_path, exist_ok=True)
        return invoices_path
    
    def create_email_directory(self, email_address: str) -> str:
        """Create email-specific directory inside Invoices"""
        invoices_path = self.create_invoices_directory()
        # Sanitize email address for directory name
        safe_email = self._sanitize_filename(email_address, max_length=50)
        email_path = os.path.join(invoices_path, safe_email)
        os.makedirs(email_path, exist_ok=True)
        return email_path
    
    def create_month_directory(self, email_address: str, month_name: str) -> str:
        """Create month-specific directory inside email directory"""
        email_path = self.create_email_directory(email_address)
        # Sanitize month name for directory name
        safe_month = self._sanitize_filename(month_name, max_length=50)
        month_path = os.path.join(email_path, safe_month)
        os.makedirs(month_path, exist_ok=True)
        return month_path
    
    def create_vendor_directory_in_month(self, email_address: str, month_name: str, vendor_name: str) -> str:
        """Create vendor-specific directory inside month directory"""
        month_path = self.create_month_directory(email_address, month_name)
        # Sanitize vendor name for directory name
        safe_vendor = self._sanitize_filename(vendor_name, max_length=50)
        vendor_path = os.path.join(month_path, safe_vendor)
        os.makedirs(vendor_path, exist_ok=True)
        return vendor_path
    
    def create_user_directory(self, user_id: str, scanned_email: str = None) -> str:
        """Create user-specific directory using scanned email if available, otherwise user_id (legacy method)"""
        # Use scanned email for folder naming if available, otherwise fallback to user_id
        folder_name = scanned_email if scanned_email else user_id
        # Sanitize the folder name for filesystem safety
        safe_folder_name = self._sanitize_filename(folder_name, max_length=50)
        user_path = os.path.join(self.base_path, "invoices", safe_folder_name)
        os.makedirs(user_path, exist_ok=True)
        return user_path
    
    def create_vendor_directory(self, user_id: str, vendor_name: str, scanned_email: str = None) -> str:
        """Create vendor-specific directory within user directory (legacy method)"""
        user_path = self.create_user_directory(user_id, scanned_email)
        # Sanitize vendor name for directory name
        safe_vendor_name = self._sanitize_filename(vendor_name, max_length=50)
        vendor_path = os.path.join(user_path, safe_vendor_name)
        os.makedirs(vendor_path, exist_ok=True)
        return vendor_path
    
    def _sanitize_filename(self, filename: str, max_length: int = 80) -> str:
        """Sanitize filename to be safe for filesystem and always short enough"""
        if not filename:
            return "unknown"
        # Remove or replace unsafe characters
        safe_chars = []
        for char in filename:
            if char.isalnum() or char in (' ', '.', '_', '-'):
                safe_chars.append(char)
            else:
                safe_chars.append('_')
        # Join and clean up
        safe_name = ''.join(safe_chars).strip()
        # Remove multiple spaces/underscores
        import re
        safe_name = re.sub(r'[_\s]+', '_', safe_name)
        # Truncate if too long
        if len(safe_name) > max_length:
            # Keep extension if present
            name_parts = safe_name.rsplit('.', 1)
            if len(name_parts) > 1:
                extension = '.' + name_parts[1]
                base_name = name_parts[0]
                # Leave room for extension
                max_base_length = max_length - len(extension)
                safe_name = base_name[:max_base_length] + extension
            else:
                safe_name = safe_name[:max_length]
        # If still too long, use a hash fallback
        if len(safe_name) > max_length:
            import hashlib
            file_hash = hashlib.md5(safe_name.encode()).hexdigest()[:8]
            safe_name = f"file_{file_hash}.dat"
        # Ensure it's not empty
        if not safe_name or safe_name == '.':
            safe_name = "unknown"
        return safe_name
    
    def save_invoice_file_new_structure(self, email_address: str, month_name: str, vendor_name: str, file_content: bytes, filename: str) -> Optional[Dict]:
        """Save invoice file locally with new folder structure"""
        try:
            vendor_path = self.create_vendor_directory_in_month(email_address, month_name, vendor_name)
            
            # Sanitize the filename
            safe_filename = self._sanitize_filename(filename)
            
            # Generate unique filename if needed
            base_name, ext = os.path.splitext(safe_filename)
            counter = 1
            final_filename = safe_filename
            
            while os.path.exists(os.path.join(vendor_path, final_filename)):
                final_filename = f"{base_name}_{counter}{ext}"
                counter += 1
                
                # Prevent infinite loop
                if counter > 1000:
                    # Use hash as fallback
                    file_hash = hashlib.md5(file_content).hexdigest()[:8]
                    final_filename = f"file_{file_hash}{ext}"
                    break
            
            # Save the file
            file_path = os.path.join(vendor_path, final_filename)
            with open(file_path, 'wb') as f:
                f.write(file_content)
            
            logger.info(f"✅ File saved locally with new structure: {file_path}")
            logger.info(f"   📁 Structure: uploads/Invoice Manager/Invoices/{email_address}/{month_name}/{vendor_name}/")
            
            return {
                'file_path': file_path,
                'filename': final_filename,
                'folder_structure': f"uploads/Invoice Manager/Invoices/{email_address}/{month_name}/{vendor_name}/",
                'month_folder': month_name
            }
            
        except Exception as e:
            logger.error(f"Error saving file with new structure: {str(e)}")
            return None

    def save_invoice_file(self, user_id: str, vendor_name: str, file_content: bytes, filename: str, scanned_email: str = None) -> Optional[Dict]:
        """Save invoice file locally (legacy method)"""
        try:
            vendor_path = self.create_vendor_directory(user_id, vendor_name, scanned_email)
            
            # Sanitize the filename
            safe_filename = self._sanitize_filename(filename)
            
            # Generate unique filename if needed
            base_name, ext = os.path.splitext(safe_filename)
            counter = 1
            final_filename = safe_filename
            
            while os.path.exists(os.path.join(vendor_path, final_filename)):
                final_filename = f"{base_name}_{counter}{ext}"
                counter += 1
                
                # Prevent infinite loop
                if counter > 1000:
                    # Use hash as fallback
                    file_hash = hashlib.md5(file_content).hexdigest()[:8]
                    final_filename = f"file_{file_hash}{ext}"
                    break
            
            file_path = os.path.join(vendor_path, final_filename)
            
            # Save file
            with open(file_path, 'wb') as f:
                f.write(file_content)
            
            return {
                'file_path': file_path,
                'filename': final_filename,
                'size': len(file_content),
                'created_at': datetime.utcnow()
            }
            
        except Exception as e:
            logger.error(f"Error saving file locally: {str(e)}")
            return None
    
    def get_file_path(self, user_id: str, vendor_name: str, filename: str, scanned_email: str = None) -> Optional[str]:
        """Get the full path to a saved file"""
        try:
            vendor_path = self.create_vendor_directory(user_id, vendor_name, scanned_email)
            file_path = os.path.join(vendor_path, filename)
            
            if os.path.exists(file_path):
                return file_path
            return None
            
        except Exception as e:
            logger.error(f"Error getting file path: {str(e)}")
            return None
    
    def delete_file(self, user_id: str, vendor_name: str, filename: str, scanned_email: str = None) -> bool:
        """Delete a saved file"""
        try:
            file_path = self.get_file_path(user_id, vendor_name, filename, scanned_email)
            if file_path and os.path.exists(file_path):
                os.remove(file_path)
                return True
            return False
            
        except Exception as e:
            logger.error(f"Error deleting file: {str(e)}")
            return False 