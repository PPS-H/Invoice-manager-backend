import os
import io
from typing import Optional, Dict, List
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.http import MediaIoBaseUpload
import logging
from datetime import datetime
from services.inviter_service import inviter_service

logger = logging.getLogger(__name__)

def get_month_name_from_date(date_str: str) -> str:
    """Get month name from date string"""
    try:
        from datetime import datetime
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

class DriveService:
    """Google Drive service for file management"""
    
    def __init__(self):
        self.service = None
        self.credentials = None
        
    def authenticate(self, access_token: str, refresh_token: str = None) -> bool:
        """Authenticate with Google Drive API"""
        try:
            logger.info(f"🔐 Starting Google Drive authentication...")
            logger.info(f"   Access Token: {access_token[:20]}..." if access_token else "   Access Token: None")
            logger.info(f"   Refresh Token: {'Present' if refresh_token else 'Missing'}")
            
            # Check environment variables
            client_id = os.getenv("GOOGLE_CLIENT_ID")
            client_secret = os.getenv("GOOGLE_CLIENT_SECRET")
            
            if not client_id or not client_secret:
                logger.error("❌ Missing Google OAuth credentials in environment")
                logger.error(f"   GOOGLE_CLIENT_ID: {'Present' if client_id else 'Missing'}")
                logger.error(f"   GOOGLE_CLIENT_SECRET: {'Present' if client_secret else 'Missing'}")
                return False
            
            logger.info(f"✅ Google OAuth credentials found")
            
            self.credentials = Credentials(
                token=access_token,
                refresh_token=refresh_token,
                token_uri="https://oauth2.googleapis.com/token",
                client_id=client_id,
                client_secret=client_secret,
                scopes=['https://www.googleapis.com/auth/drive.file']
            )
            
            logger.info(f"🔑 Credentials object created")
            
            # Refresh token if needed
            if self.credentials.expired and self.credentials.refresh_token:
                logger.info(f"🔄 Token expired, attempting refresh...")
                try:
                    self.credentials.refresh(Request())
                    logger.info(f"✅ Token refreshed successfully")
                except Exception as refresh_error:
                    logger.error(f"❌ Token refresh failed: {str(refresh_error)}")
                    return False
            else:
                logger.info(f"✅ Token is valid (not expired)")
            
            logger.info(f"🏗️ Building Google Drive service...")
            self.service = build('drive', 'v3', credentials=self.credentials)
            logger.info(f"✅ Google Drive service built successfully")
            
            # Test the service with a simple API call
            try:
                about = self.service.about().get(fields="user").execute()
                user_email = about.get('user', {}).get('emailAddress', 'Unknown')
                logger.info(f"✅ Drive API test successful - User: {user_email}")
                return True
            except Exception as test_error:
                logger.error(f"❌ Drive API test failed: {str(test_error)}")
                return False
            
        except Exception as e:
            logger.error(f"❌ Google Drive authentication failed: {str(e)}")
            logger.error(f"   Exception type: {type(e).__name__}")
            import traceback
            logger.error(f"   Traceback: {traceback.format_exc()}")
            return False
    
    def create_invoice_manager_folder(self, inviter_user_id: str) -> Optional[str]:
        """Create or get main 'Invoice Manager' folder for inviter user"""
        try:
            folder_name = "Invoice Manager"
            
            # Check if folder already exists
            query = f"name='{folder_name}' and mimeType='application/vnd.google-apps.folder' and trashed=false"
            results = self.service.files().list(q=query).execute()
            
            if results['files']:
                logger.info(f"✅ Found existing Invoice Manager folder: {results['files'][0]['id']}")
                return results['files'][0]['id']
            
            # Create new folder
            folder_metadata = {
                'name': folder_name,
                'mimeType': 'application/vnd.google-apps.folder'
            }
            
            folder = self.service.files().create(
                body=folder_metadata,
                fields='id'
            ).execute()
            
            logger.info(f"✅ Created new Invoice Manager folder: {folder['id']}")
            return folder['id']
            
        except Exception as e:
            logger.error(f"Error creating Invoice Manager folder: {str(e)}")
            return None

    def create_invoices_folder(self, inviter_user_id: str) -> Optional[str]:
        """Create or get 'Invoices' folder inside Invoice Manager"""
        try:
            # First ensure Invoice Manager folder exists
            invoice_manager_folder_id = self.create_invoice_manager_folder(inviter_user_id)
            if not invoice_manager_folder_id:
                return None
            
            folder_name = "Invoices"
            
            # Check if Invoices folder already exists
            query = f"name='{folder_name}' and '{invoice_manager_folder_id}' in parents and mimeType='application/vnd.google-apps.folder' and trashed=false"
            results = self.service.files().list(q=query).execute()
            
            if results['files']:
                logger.info(f"✅ Found existing Invoices folder: {results['files'][0]['id']}")
                return results['files'][0]['id']
            
            # Create new Invoices folder
            folder_metadata = {
                'name': folder_name,
                'mimeType': 'application/vnd.google-apps.folder',
                'parents': [invoice_manager_folder_id]
            }
            
            folder = self.service.files().create(
                body=folder_metadata,
                fields='id'
            ).execute()
            
            logger.info(f"✅ Created new Invoices folder: {folder['id']}")
            return folder['id']
            
        except Exception as e:
            logger.error(f"Error creating Invoices folder: {str(e)}")
            return None

    def create_email_folder(self, inviter_user_id: str, email_address: str) -> Optional[str]:
        """Create or get email-specific folder inside Invoices"""
        try:
            # First ensure Invoices folder exists
            invoices_folder_id = self.create_invoices_folder(inviter_user_id)
            if not invoices_folder_id:
                return None
            
            # Sanitize email address for folder name
            safe_email = email_address.replace('@', '_at_').replace('.', '_dot_')
            folder_name = f"{email_address}"
            
            # Check if email folder already exists
            query = f"name='{folder_name}' and '{invoices_folder_id}' in parents and mimeType='application/vnd.google-apps.folder' and trashed=false"
            results = self.service.files().list(q=query).execute()
            
            if results['files']:
                logger.info(f"✅ Found existing email folder for {email_address}: {results['files'][0]['id']}")
                return results['files'][0]['id']
            
            # Create new email folder
            folder_metadata = {
                'name': folder_name,
                'mimeType': 'application/vnd.google-apps.folder',
                'parents': [invoices_folder_id]
            }
            
            folder = self.service.files().create(
                body=folder_metadata,
                fields='id'
            ).execute()
            
            logger.info(f"✅ Created new email folder for {email_address}: {folder['id']}")
            return folder['id']
            
        except Exception as e:
            logger.error(f"Error creating email folder for {email_address}: {str(e)}")
            return None

    def create_month_folder(self, inviter_user_id: str, email_address: str, month_name: str) -> Optional[str]:
        """Create or get month-specific folder inside email folder"""
        try:
            # First ensure email folder exists
            email_folder_id = self.create_email_folder(inviter_user_id, email_address)
            if not email_folder_id:
                return None
            
            # Check if month folder already exists
            query = f"name='{month_name}' and '{email_folder_id}' in parents and mimeType='application/vnd.google-apps.folder' and trashed=false"
            results = self.service.files().list(q=query).execute()
            
            if results['files']:
                logger.info(f"✅ Found existing month folder {month_name}: {results['files'][0]['id']}")
                return results['files'][0]['id']
            
            # Create new month folder
            folder_metadata = {
                'name': month_name,
                'mimeType': 'application/vnd.google-apps.folder',
                'parents': [email_folder_id]
            }
            
            folder = self.service.files().create(
                body=folder_metadata,
                fields='id'
            ).execute()
            
            logger.info(f"✅ Created new month folder {month_name}: {folder['id']}")
            return folder['id']
            
        except Exception as e:
            logger.error(f"Error creating month folder {month_name}: {str(e)}")
            return None

    def create_vendor_folder_in_month(self, inviter_user_id: str, email_address: str, month_name: str, vendor_name: str) -> Optional[str]:
        """Create or get vendor-specific folder inside month folder"""
        try:
            # First ensure month folder exists
            month_folder_id = self.create_month_folder(inviter_user_id, email_address, month_name)
            if not month_folder_id:
                return None
            
            # Sanitize vendor name for folder name
            safe_vendor_name = "".join(c for c in vendor_name if c.isalnum() or c in (' ', '-', '_')).rstrip()
            
            # Check if vendor folder already exists
            query = f"name='{safe_vendor_name}' and '{month_folder_id}' in parents and mimeType='application/vnd.google-apps.folder' and trashed=false"
            results = self.service.files().list(q=query).execute()
            
            if results['files']:
                logger.info(f"✅ Found existing vendor folder {safe_vendor_name}: {results['files'][0]['id']}")
                return results['files'][0]['id']
            
            # Create new vendor folder
            folder_metadata = {
                'name': safe_vendor_name,
                'mimeType': 'application/vnd.google-apps.folder',
                'parents': [month_folder_id]
            }
            
            folder = self.service.files().create(
                body=folder_metadata,
                fields='id'
            ).execute()
            
            logger.info(f"✅ Created new vendor folder {safe_vendor_name}: {folder['id']}")
            return folder['id']
            
        except Exception as e:
            logger.error(f"Error creating vendor folder {vendor_name}: {str(e)}")
            return None

    def create_invoice_folder(self, user_id: str) -> Optional[str]:
        """Create or get invoice folder for user (legacy method - kept for compatibility)"""
        try:
            folder_name = f"Invoice Manager - {user_id}"
            
            # Check if folder already exists
            query = f"name='{folder_name}' and mimeType='application/vnd.google-apps.folder' and trashed=false"
            results = self.service.files().list(q=query).execute()
            
            if results['files']:
                return results['files'][0]['id']
            
            # Create new folder
            folder_metadata = {
                'name': folder_name,
                'mimeType': 'application/vnd.google-apps.folder'
            }
            
            folder = self.service.files().create(
                body=folder_metadata,
                fields='id'
            ).execute()
            
            return folder['id']
            
        except Exception as e:
            logger.error(f"Error creating invoice folder: {str(e)}")
            return None

    def create_uploads_invoices_folder(self, user_id: str, scanned_email: str = None) -> Optional[str]:
        """Create or get uploads/invoices folder structure for user (matching local structure)"""
        try:
            # Use scanned email for folder naming if available, otherwise fallback to user_id
            folder_name = scanned_email if scanned_email else user_id
            
            # Create main uploads folder
            uploads_folder_name = "uploads"
            uploads_query = f"name='{uploads_folder_name}' and mimeType='application/vnd.google-apps.folder' and trashed=false"
            uploads_results = self.service.files().list(q=uploads_query).execute()
            
            if uploads_results['files']:
                uploads_folder_id = uploads_results['files'][0]['id']
            else:
                # Create uploads folder
                uploads_metadata = {
                    'name': uploads_folder_name,
                    'mimeType': 'application/vnd.google-apps.folder'
                }
                uploads_folder = self.service.files().create(
                    body=uploads_metadata,
                    fields='id'
                ).execute()
                uploads_folder_id = uploads_folder['id']
            
            # Create invoices subfolder
            invoices_folder_name = "invoices"
            invoices_query = f"name='{invoices_folder_name}' and '{uploads_folder_id}' in parents and mimeType='application/vnd.google-apps.folder' and trashed=false"
            invoices_results = self.service.files().list(q=invoices_query).execute()
            
            if invoices_results['files']:
                invoices_folder_id = invoices_results['files'][0]['id']
            else:
                # Create invoices folder
                invoices_metadata = {
                    'name': invoices_folder_name,
                    'mimeType': 'application/vnd.google-apps.folder',
                    'parents': [uploads_folder_id]
                }
                invoices_folder = self.service.files().create(
                    body=invoices_metadata,
                    fields='id'
                ).execute()
                invoices_folder_id = invoices_folder['id']
            
            # Create user-specific folder (using scanned email if available)
            user_folder_name = folder_name
            user_query = f"name='{user_folder_name}' and '{invoices_folder_id}' in parents and mimeType='application/vnd.google-apps.folder' and trashed=false"
            user_results = self.service.files().list(q=user_query).execute()
            
            if user_results['files']:
                user_folder_id = user_results['files'][0]['id']
            else:
                # Create user folder
                user_metadata = {
                    'name': user_folder_name,
                    'mimeType': 'application/vnd.google-apps.folder',
                    'parents': [invoices_folder_id]
                }
                user_folder = self.service.files().create(
                    body=user_metadata,
                    fields='id'
                ).execute()
                user_folder_id = user_folder['id']
            
            return user_folder_id
            
        except Exception as e:
            logger.error(f"Error creating uploads/invoices folder structure: {str(e)}")
            return None
    
    def create_vendor_folder(self, vendor_name: str, parent_folder_id: str) -> Optional[str]:
        """Create vendor-specific folder"""
        try:
            # Sanitize vendor name for folder name
            safe_vendor_name = "".join(c for c in vendor_name if c.isalnum() or c in (' ', '-', '_')).rstrip()
            
            # Check if vendor folder exists
            query = f"name='{safe_vendor_name}' and '{parent_folder_id}' in parents and mimeType='application/vnd.google-apps.folder' and trashed=false"
            results = self.service.files().list(q=query).execute()
            
            if results['files']:
                return results['files'][0]['id']
            
            # Create new vendor folder
            folder_metadata = {
                'name': safe_vendor_name,
                'mimeType': 'application/vnd.google-apps.folder',
                'parents': [parent_folder_id]
            }
            
            folder = self.service.files().create(
                body=folder_metadata,
                fields='id'
            ).execute()
            
            return folder['id']
            
        except Exception as e:
            logger.error(f"Error creating vendor folder: {str(e)}")
            return None

    async def save_scanned_email_invoice_new_structure(self, email_account_id: str, vendor_name: str, email_data: Dict, invoice_info: Dict, local_file_info: Optional[Dict] = None, scanned_email: str = None) -> Optional[Dict]:
        """Save scanned email invoice to inviter's Google Drive with new folder structure"""
        try:
            logger.info(f"📁 Saving scanned email invoice to inviter's Google Drive (new structure)...")
            logger.info(f"   Email Account ID: {email_account_id}")
            logger.info(f"   Vendor: {vendor_name}")
            logger.info(f"   Scanned Email: {scanned_email or 'Not provided'}")
            logger.info(f"   Email Subject: {email_data.get('subject', 'No Subject')[:50]}...")
            logger.info(f"   Has Local File: {'Yes' if local_file_info else 'No'}")
            
            # Check if service is available
            if not self.service:
                logger.error("❌ Google Drive service not initialized")
                return None
            
            # If no local file exists, don't save to Drive (text-based invoices)
            if not local_file_info:
                logger.info(f"📝 No local file found - skipping Drive storage for text-based invoice")
                logger.info(f"   This is a text-based invoice with no PDF attachment")
                return None
            
            # Check if the file is actually a PDF (additional safety check)
            local_filename = local_file_info.get('filename', '')
            if not local_filename.lower().endswith('.pdf'):
                logger.info(f"📝 File is not a PDF ({local_filename}) - skipping Drive storage")
                logger.info(f"   Only PDF files are uploaded to Drive")
                return None
            
            # Check if local file exists and is accessible
            local_file_path = local_file_info.get('file_path')
            if not local_file_path or not os.path.exists(local_file_path):
                logger.warning(f"⚠️ Local file not found at path: {local_file_path}")
                logger.info(f"   Skipping Drive storage for this invoice")
                return None
            
            logger.info(f"📄 Local file found: {local_file_path}")
            
            # Find the inviter user for this email account
            inviter_info = await inviter_service.get_inviter_user_for_email_account(email_account_id)
            if not inviter_info:
                logger.error(f"❌ Could not find inviter for email account: {email_account_id}")
                return None
            
            inviter_user_id = inviter_info["user_id"]
            logger.info(f"✅ Found inviter: {inviter_info.get('email', 'Unknown')} (ID: {inviter_user_id})")
            
            # Get the scanned email address
            if not scanned_email:
                # Try to get it from email_data
                scanned_email = email_data.get('sender', '').split('<')[-1].split('>')[0].strip()
                if not scanned_email:
                    scanned_email = "unknown@email.com"
            
            logger.info(f"📧 Using scanned email: {scanned_email}")
            
            # Get month name from invoice date
            invoice_date = invoice_info.get('invoice_date', '')
            month_name = get_month_name_from_date(invoice_date)
            logger.info(f"📅 Invoice date: {invoice_date} -> Month folder: {month_name}")
            
            # Create the new folder structure: Invoice Manager/Invoices/{email}/{month}/{vendor}/
            logger.info(f"📂 Creating new folder structure...")
            
            # Create vendor folder in the correct month
            vendor_folder_id = self.create_vendor_folder_in_month(
                inviter_user_id, 
                scanned_email, 
                month_name, 
                vendor_name
            )
            
            if not vendor_folder_id:
                logger.error(f"❌ Failed to create vendor folder for {vendor_name} in {month_name}")
                return None
            
            logger.info(f"✅ Vendor folder created/retrieved: {vendor_folder_id}")
            logger.info(f"   Structure: Invoice Manager/Invoices/{scanned_email}/{month_name}/{vendor_name}/")
            
            # Upload the actual PDF file
            logger.info(f"📄 Uploading PDF file: {local_filename}")
            
            try:
                # Read the PDF file
                with open(local_file_path, 'rb') as file:
                    file_content = file.read()
                
                logger.info(f"   File size: {len(file_content)} bytes")
                
                # Upload PDF to Google Drive
                logger.info(f"🚀 Uploading PDF to Google Drive...")
                file_info = self.upload_invoice_file(
                    file_content,
                    local_filename,
                    vendor_folder_id,
                    'application/pdf'
                )
                
                if file_info:
                    logger.info(f"✅ Successfully uploaded PDF to Drive!")
                    logger.info(f"   📄 File Name: {local_filename}")
                    logger.info(f"   🔗 File ID: {file_info['id']}")
                    logger.info(f"   📁 Folder: Invoice Manager/Invoices/{scanned_email}/{month_name}/{vendor_name}/")
                    
                    return {
                        'drive_file_id': file_info['id'],
                        'drive_file_name': file_info['name'],
                        'drive_folder_id': vendor_folder_id,
                        'web_view_link': file_info['web_view_link'],
                        'web_content_link': file_info['web_content_link'],
                        'folder_structure': f"Invoice Manager/Invoices/{scanned_email}/{month_name}/{vendor_name}/",
                        'inviter_user_id': inviter_user_id,
                        'month_folder': month_name
                    }
                else:
                    logger.error(f"❌ Failed to upload PDF to Drive")
                    return None
                    
            except Exception as file_error:
                logger.error(f"❌ Error reading/uploading local file: {str(file_error)}")
                return None
                
        except Exception as e:
            logger.error(f"❌ Error saving scanned email invoice to Drive (new structure): {str(e)}")
            logger.error(f"   Exception type: {type(e).__name__}")
            import traceback
            logger.error(f"   Traceback: {traceback.format_exc()}")
            return None

    def save_scanned_email_invoice(self, user_id: str, vendor_name: str, email_data: Dict, invoice_info: Dict, local_file_info: Optional[Dict] = None, scanned_email: str = None) -> Optional[Dict]:
        """Save scanned email invoice to Google Drive with same structure as uploads folder"""
        try:
            logger.info(f"📁 Saving scanned email invoice to Google Drive...")
            logger.info(f"   User ID: {user_id}")
            logger.info(f"   Vendor: {vendor_name}")
            logger.info(f"   Scanned Email: {scanned_email or 'Not provided'}")
            logger.info(f"   Email Subject: {email_data.get('subject', 'No Subject')[:50]}...")
            logger.info(f"   Has Local File: {'Yes' if local_file_info else 'No'}")
            
            # Check if service is available
            if not self.service:
                logger.error("❌ Google Drive service not initialized")
                return None
            
            # If no local file exists, don't save to Drive (text-based invoices)
            if not local_file_info:
                logger.info(f"📝 No local file found - skipping Drive storage for text-based invoice")
                logger.info(f"   This is a text-based invoice with no PDF attachment")
                return None
            
            # Check if the file is actually a PDF (additional safety check)
            local_filename = local_file_info.get('filename', '')
            if not local_filename.lower().endswith('.pdf'):
                logger.info(f"📝 File is not a PDF ({local_filename}) - skipping Drive storage")
                logger.info(f"   Only PDF files are uploaded to Drive")
                return None
            
            # Check if local file exists and is accessible
            local_file_path = local_file_info.get('file_path')
            if not local_file_path or not os.path.exists(local_file_path):
                logger.warning(f"⚠️ Local file not found at path: {local_file_path}")
                logger.info(f"   Skipping Drive storage for this invoice")
                return None
            
            logger.info(f"📄 Local file found: {local_file_path}")
            
            # Create the folder structure: uploads/invoices/{scanned_email}/{vendor_name}/
            logger.info(f"📂 Creating folder structure...")
            user_folder_id = self.create_uploads_invoices_folder(user_id, scanned_email)
            if not user_folder_id:
                logger.error(f"❌ Failed to create user folder structure for {scanned_email or user_id}")
                return None
            
            logger.info(f"✅ User folder created/retrieved: {user_folder_id}")
            logger.info(f"   Using folder name: {scanned_email or user_id}")
            
            vendor_folder_id = self.create_vendor_folder(vendor_name, user_folder_id)
            if not vendor_folder_id:
                logger.error(f"❌ Failed to create vendor folder for {vendor_name}")
                return None
            
            logger.info(f"✅ Vendor folder created/retrieved: {vendor_folder_id}")
            
            # Upload the actual PDF file (not text)
            local_filename = local_file_info.get('filename', 'invoice.pdf')
            logger.info(f"📄 Uploading PDF file: {local_filename}")
            
            try:
                # Read the PDF file
                with open(local_file_path, 'rb') as file:
                    file_content = file.read()
                
                logger.info(f"   File size: {len(file_content)} bytes")
                
                # Upload PDF to Google Drive
                logger.info(f"🚀 Uploading PDF to Google Drive...")
                file_info = self.upload_invoice_file(
                    file_content,
                    local_filename,
                    vendor_folder_id,
                    'application/pdf'
                )
                
                if file_info:
                    logger.info(f"✅ Successfully uploaded PDF to Drive!")
                    logger.info(f"   📄 File Name: {local_filename}")
                    logger.info(f"   🔗 File ID: {file_info['id']}")
                    logger.info(f"   📁 Folder: uploads/invoices/{scanned_email or user_id}/{vendor_name}/")
                    
                    return {
                        'drive_file_id': file_info['id'],
                        'drive_file_name': file_info['name'],
                        'drive_folder_id': vendor_folder_id,
                        'web_view_link': file_info['web_view_link'],
                        'web_content_link': file_info['web_content_link'],
                        'folder_structure': f"uploads/invoices/{scanned_email or user_id}/{vendor_name}/"
                    }
                else:
                    logger.error(f"❌ Failed to upload PDF to Drive")
                    return None
                    
            except Exception as file_error:
                logger.error(f"❌ Error reading/uploading local file: {str(file_error)}")
                return None
                
        except Exception as e:
            logger.error(f"❌ Error saving scanned email invoice to Drive: {str(e)}")
            logger.error(f"   Exception type: {type(e).__name__}")
            import traceback
            logger.error(f"   Traceback: {traceback.format_exc()}")
            return None

    def _format_email_for_storage(self, email_data: Dict, invoice_info: Dict) -> str:
        """Format email data and invoice info for storage as text file"""
        try:
            content = []
            content.append("=" * 80)
            content.append("SCANNED EMAIL INVOICE")
            content.append("=" * 80)
            content.append("")
            
            # Email metadata
            content.append("EMAIL METADATA:")
            content.append(f"Subject: {email_data.get('subject', 'No Subject')}")
            content.append(f"Sender: {email_data.get('sender', 'Unknown')}")
            content.append(f"Date: {email_data.get('date', 'Unknown')}")
            content.append(f"Message ID: {email_data.get('message_id', 'Unknown')}")
            content.append("")
            
            # Invoice information
            content.append("EXTRACTED INVOICE DATA:")
            content.append(f"Vendor: {invoice_info.get('vendor_name', 'Unknown')}")
            content.append(f"Invoice Number: {invoice_info.get('invoice_number', 'N/A')}")
            content.append(f"Invoice Date: {invoice_info.get('invoice_date', 'N/A')}")
            content.append(f"Due Date: {invoice_info.get('due_date', 'N/A')}")
            content.append(f"Amount: {invoice_info.get('amount', 0)}")
            content.append(f"Tax Amount: {invoice_info.get('tax_amount', 0)}")
            content.append(f"Total Amount: {invoice_info.get('total_amount', 0)}")
            content.append(f"Currency: {invoice_info.get('currency', 'USD')}")
            content.append(f"Category: {invoice_info.get('category', 'N/A')}")
            content.append(f"Confidence Score: {invoice_info.get('confidence_score', 'N/A')}")
            content.append("")
            
            # Email body
            content.append("EMAIL CONTENT:")
            content.append("-" * 40)
            content.append(email_data.get('body', 'No content'))
            content.append("")
            
            # Processing metadata
            content.append("PROCESSING METADATA:")
            content.append(f"Processed At: {datetime.utcnow().isoformat()}")
            content.append(f"Source: Email Scanner")
            content.append(f"Processing Method: {'AI (Gemini)' if invoice_info.get('confidence_score') else 'Regex Fallback'}")
            content.append("")
            content.append("=" * 80)
            
            return "\n".join(content)
            
        except Exception as e:
            logger.error(f"Error formatting email for storage: {str(e)}")
            return f"Error formatting email: {str(e)}"
    
    def upload_text_file(self, file_content: bytes, filename: str, folder_id: str, mime_type: str = 'text/plain') -> Optional[Dict]:
        """Upload text file to Google Drive"""
        try:
            # Create file metadata
            file_metadata = {
                'name': filename,
                'parents': [folder_id]
            }
            
            # Create media upload
            media = MediaIoBaseUpload(
                io.BytesIO(file_content),
                mimetype=mime_type,
                resumable=True
            )
            
            # Upload file
            file = self.service.files().create(
                body=file_metadata,
                media_body=media,
                fields='id,name,webViewLink,webContentLink'
            ).execute()
            
            return {
                'id': file['id'],
                'name': file['name'],
                'web_view_link': file.get('webViewLink'),
                'web_content_link': file.get('webContentLink')
            }
            
        except Exception as e:
            logger.error(f"Error uploading text file to Drive: {str(e)}")
            return None
    
    def upload_invoice_file(self, file_content: bytes, filename: str, folder_id: str, mime_type: str = 'application/pdf') -> Optional[Dict]:
        """Upload invoice file to Google Drive"""
        try:
            # Create file metadata
            file_metadata = {
                'name': filename,
                'parents': [folder_id]
            }
            
            # Create media upload
            media = MediaIoBaseUpload(
                io.BytesIO(file_content),
                mimetype=mime_type,
                resumable=True
            )
            
            # Upload file
            file = self.service.files().create(
                body=file_metadata,
                media_body=media,
                fields='id,name,webViewLink,webContentLink'
            ).execute()
            
            return {
                'id': file['id'],
                'name': file['name'],
                'web_view_link': file.get('webViewLink'),
                'web_content_link': file.get('webContentLink')
            }
            
        except Exception as e:
            logger.error(f"Error uploading file to Drive: {str(e)}")
            return None
    
    def organize_invoice_files(self, user_id: str, vendor_name: str, invoice_data: Dict) -> Optional[Dict]:
        """Organize invoice files in Drive structure"""
        try:
            # Get or create main invoice folder
            main_folder_id = self.create_invoice_folder(user_id)
            if not main_folder_id:
                return None
            
            # Get or create vendor folder
            vendor_folder_id = self.create_vendor_folder(vendor_name, main_folder_id)
            if not vendor_folder_id:
                return None
            
            # Upload invoice file
            if 'file_content' in invoice_data and 'filename' in invoice_data:
                file_info = self.upload_invoice_file(
                    invoice_data['file_content'],
                    invoice_data['filename'],
                    vendor_folder_id,
                    invoice_data.get('mime_type', 'application/pdf')
                )
                
                if file_info:
                    return {
                        'folder_id': main_folder_id,
                        'vendor_folder_id': vendor_folder_id,
                        'file_id': file_info['id'],
                        'file_name': file_info['name'],
                        'web_view_link': file_info['web_view_link'],
                        'web_content_link': file_info['web_content_link']
                    }
            
            return None
            
        except Exception as e:
            logger.error(f"Error organizing invoice files: {str(e)}")
            return None

    def get_folder_structure(self, user_id: str) -> Optional[Dict]:
        """Get the complete folder structure for a user"""
        try:
            structure = {
                'uploads_folder': None,
                'invoices_folder': None,
                'user_folder': None,
                'vendor_folders': []
            }
            
            # Get uploads folder
            uploads_query = "name='uploads' and mimeType='application/vnd.google-apps.folder' and trashed=false"
            uploads_results = self.service.files().list(q=uploads_query).execute()
            if uploads_results['files']:
                structure['uploads_folder'] = uploads_results['files'][0]['id']
                
                # Get invoices folder
                invoices_query = f"name='invoices' and '{structure['uploads_folder']}' in parents and mimeType='application/vnd.google-apps.folder' and trashed=false"
                invoices_results = self.service.files().list(q=invoices_query).execute()
                if invoices_results['files']:
                    structure['invoices_folder'] = invoices_results['files'][0]['id']
                    
                    # Get user folder
                    user_query = f"name='{user_id}' and '{structure['invoices_folder']}' in parents and mimeType='application/vnd.google-apps.folder' and trashed=false"
                    user_results = self.service.files().list(q=user_query).execute()
                    if user_results['files']:
                        structure['user_folder'] = user_results['files'][0]['id']
                        
                        # Get vendor folders
                        vendor_query = f"'{structure['user_folder']}' in parents and mimeType='application/vnd.google-apps.folder' and trashed=false"
                        vendor_results = self.service.files().list(q=vendor_query).execute()
                        structure['vendor_folders'] = vendor_results.get('files', [])
            
            return structure
            
        except Exception as e:
            logger.error(f"Error getting folder structure: {str(e)}")
            return None
    
    def get_file_metadata(self, file_id: str) -> Optional[Dict]:
        """Get file metadata from Drive"""
        try:
            file = self.service.files().get(
                fileId=file_id,
                fields='id,name,size,createdTime,modifiedTime,webViewLink,webContentLink'
            ).execute()
            
            return {
                'id': file['id'],
                'name': file['name'],
                'size': file.get('size'),
                'created_time': file.get('createdTime'),
                'modified_time': file.get('modifiedTime'),
                'web_view_link': file.get('webViewLink'),
                'web_content_link': file.get('webContentLink')
            }
            
        except Exception as e:
            logger.error(f"Error getting file metadata: {str(e)}")
            return None
    
    def delete_file(self, file_id: str) -> bool:
        """Delete file from Drive"""
        try:
            self.service.files().delete(fileId=file_id).execute()
            return True
            
        except Exception as e:
            logger.error(f"Error deleting file: {str(e)}")
            return False
    
    def download_file(self, file_id: str) -> Optional[bytes]:
        """Download file content from Drive"""
        try:
            # Get file content
            request = self.service.files().get_media(fileId=file_id)
            file_content = request.execute()
            
            return file_content
            
        except Exception as e:
            logger.error(f"Error downloading file: {str(e)}")
            return None
    
    def list_user_files(self, folder_id: str = None) -> List[Dict]:
        """List files in user's Drive"""
        try:
            query = "trashed=false"
            if folder_id:
                query += f" and '{folder_id}' in parents"
            
            results = self.service.files().list(
                q=query,
                fields="files(id,name,mimeType,size,createdTime,webViewLink)"
            ).execute()
            
            return results.get('files', [])
            
        except Exception as e:
            logger.error(f"Error listing files: {str(e)}")
            return [] 