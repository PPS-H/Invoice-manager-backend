import os
import base64
import email
import re
import json
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
import requests
from bs4 import BeautifulSoup
import logging
from enum import Enum
import asyncio
import aiohttp
from urllib.parse import urljoin, urlparse

logger = logging.getLogger(__name__)

class InvoiceType(str, Enum):
    PDF_ATTACHMENT = "pdf_attachment"
    INVOICE_LINK = "invoice_link"
    EMAIL_CONTENT = "email_content"
    UNKNOWN = "unknown"

class ProcessingStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"

class EnhancedEmailScanner:
    """Enhanced email scanning service for comprehensive invoice detection"""
    
    def __init__(self, gemini_api_key: str = None):
        self.service = None
        self.credentials = None
        self.session = None
        self.gemini_api_key = gemini_api_key
        self.processed_message_ids = set()  # Track processed emails to prevent duplicates
        
    def authenticate(self, access_token: str, refresh_token: str = None) -> bool:
        """Authenticate with Gmail API"""
        try:
            self.credentials = Credentials(
                token=access_token,
                refresh_token=refresh_token,
                token_uri="https://oauth2.googleapis.com/token",
                client_id=os.getenv("GOOGLE_CLIENT_ID"),
                client_secret=os.getenv("GOOGLE_CLIENT_SECRET"),
                scopes=['https://www.googleapis.com/auth/gmail.readonly']
            )
            
            if self.credentials.expired and self.credentials.refresh_token:
                self.credentials.refresh(Request())
            
            self.service = build('gmail', 'v1', credentials=self.credentials)
            return True
            
        except Exception as e:
            logger.error(f"Gmail authentication failed: {str(e)}")
            return False
    
    def scan_emails_by_date_range(
        self, 
        start_date: datetime, 
        end_date: datetime,
        group_emails: Optional[List[str]] = None,
        additional_filters: Optional[Dict] = None
    ) -> List[Dict]:
        """Scan emails within specific date range with comprehensive filtering"""
        try:
            # Build date query
            start_str = start_date.strftime('%Y/%m/%d')
            end_str = end_date.strftime('%Y/%m/%d')
            date_query = f"after:{start_str} before:{end_str}"
            
            # Build comprehensive invoice detection query
            invoice_keywords = [
                "invoice", "receipt", "bill", "statement", "payment",
                "purchase order", "quote", "estimate", "remittance",
                "account summary", "transaction", "charge", "fee"
            ]
            
            # Exclude non-invoice emails
            exclude_keywords = [
                "newsletter", "alert", "notification", "digest", "summary",
                "marketing", "promotion", "unsubscribe", "survey"
            ]
            
            keyword_query = "(" + " OR ".join([f'"{keyword}"' for keyword in invoice_keywords]) + ")"
            exclude_query = " AND ".join([f'-"{keyword}"' for keyword in exclude_keywords])
            
            # Add group filter if specified
            group_query = ""
            if group_emails:
                group_query = " AND (" + " OR ".join([f"from:{email}" for email in group_emails]) + ")"
            
            # Combine all filters
            final_query = f"{date_query} AND {keyword_query} {exclude_query}{group_query}"
            
            # Add custom filters
            if additional_filters:
                if 'sender_domain' in additional_filters:
                    final_query += f" AND from:{additional_filters['sender_domain']}"
                if 'has_attachment' in additional_filters and additional_filters['has_attachment']:
                    final_query += " AND has:attachment"
                if 'subject_contains' in additional_filters:
                    final_query += f" AND subject:{additional_filters['subject_contains']}"
            
            logger.info(f"Email search query: {final_query}")
            
            # Execute search with pagination
            all_emails = []
            page_token = None
            max_results_per_page = 100
            
            while True:
                results = self.service.users().messages().list(
                    userId='me',
                    q=final_query,
                    maxResults=max_results_per_page,
                    pageToken=page_token
                ).execute()
                
                messages = results.get('messages', [])
                if not messages:
                    break
                
                # Process messages in batch
                batch_emails = self._process_email_batch(messages)
                all_emails.extend(batch_emails)
                
                page_token = results.get('nextPageToken')
                if not page_token:
                    break
                
                logger.info(f"Processed {len(all_emails)} emails so far...")
            
            logger.info(f"Total emails found: {len(all_emails)}")
            return all_emails
            
        except Exception as e:
            logger.error(f"Error scanning emails by date range: {str(e)}")
            return []
    
    def _process_email_batch(self, messages: List[Dict]) -> List[Dict]:
        """Process a batch of email messages efficiently with duplicate prevention"""
        processed_emails = []
        
        for message in messages:
            try:
                # Get full message
                msg = self.service.users().messages().get(
                    userId='me',
                    id=message['id'],
                    format='full'
                ).execute()
                
                # Check for duplicates using message_id
                message_id = msg['id']
                if message_id in self.processed_message_ids:
                    logger.info(f"Skipping duplicate email: {message_id}")
                    continue
                
                # Classify and parse email
                email_data = self._classify_and_parse_email(msg)
                if email_data:
                    # Add to processed set to prevent future duplicates
                    self.processed_message_ids.add(message_id)
                    processed_emails.append(email_data)
                    
            except Exception as e:
                logger.error(f"Error processing message {message['id']}: {str(e)}")
                continue
        
        return processed_emails
    
    def _classify_and_parse_email(self, message: Dict) -> Optional[Dict]:
        """Classify email type and extract relevant data with AI-powered validation"""
        try:
            # Basic email parsing
            email_data = self._parse_email_message(message)
            if not email_data:
                return None
            
            # TEMPORARILY DISABLED AI CLASSIFICATION to debug performance
            # if self.gemini_api_key and not self._is_invoice_email_ai(email_data):
            #     logger.info(f"AI determined email {email_data['message_id']} is not an invoice")
            #     return None
            logger.info(f"Skipping AI classification for email {email_data['message_id']} (debugging mode)")
            
            # Classify invoice type
            invoice_type = self._classify_invoice_type(email_data)
            if invoice_type == InvoiceType.UNKNOWN:
                logger.info(f"Could not classify invoice type for email {email_data['message_id']}")
                return None
                
            email_data['invoice_type'] = invoice_type
            email_data['processing_status'] = ProcessingStatus.PENDING
            
            # Extract type-specific data
            if invoice_type == InvoiceType.PDF_ATTACHMENT:
                email_data['pdf_attachments'] = self._extract_pdf_attachments(message)
                
            elif invoice_type == InvoiceType.INVOICE_LINK:
                email_data['invoice_links'] = self._extract_invoice_links(email_data['body'])
                
            elif invoice_type == InvoiceType.EMAIL_CONTENT:
                email_data['invoice_content'] = self._extract_invoice_content(email_data['body'])
            
            return email_data
            
        except Exception as e:
            logger.error(f"Error classifying and parsing email: {str(e)}")
            return None
    
    def _classify_invoice_type(self, email_data: Dict) -> InvoiceType:
        """Classify the type of invoice email"""
        try:
            # Check for PDF attachments
            if email_data.get('attachments'):
                pdf_attachments = [att for att in email_data['attachments'] 
                                 if att.get('mime_type', '').lower() == 'application/pdf']
                if pdf_attachments:
                    return InvoiceType.PDF_ATTACHMENT
            
            # Check for invoice links in email body
            body = email_data.get('body', '').lower()
            link_patterns = [
                r'https?://[^\s]+\.pdf',  # Direct PDF links
                r'download.*invoice',      # Download invoice links
                r'view.*invoice',         # View invoice links
                r'invoice.*link',         # Generic invoice links
                r'statement.*download',   # Statement download links
            ]
            
            for pattern in link_patterns:
                if re.search(pattern, body, re.IGNORECASE):
                    return InvoiceType.INVOICE_LINK
            
            # Enhanced check for inline invoice content
            invoice_indicators = [
                r'invoice\s*#?\s*\d+',    # Invoice number
                r'total.*amount.*\$\d+',  # Total amount
                r'amount.*due.*\$\d+',    # Amount due
                r'invoice.*date',         # Invoice date
                r'billing.*period',       # Billing period
                r'payment.*terms',        # Payment terms
                r'payment.*received',     # Payment confirmations
                r'thank.*payment',        # Thank you for payment
                r'receipt.*\$\d+',       # Receipt with amount
                r'charge.*\$\d+',        # Charge with amount
                r'fee.*\$\d+',           # Fee with amount
                r'subscription.*\$\d+',  # Subscription with amount
                r'billing.*\$\d+',       # Billing with amount
                r'statement.*\$\d+',     # Statement with amount
            ]
            
            # Check for vendor names that commonly send invoices
            common_vendors = [
                'github', 'atlassian', 'datadog', 'figma', 'stripe', 'paypal',
                'aws', 'google', 'microsoft', 'zoom', 'slack', 'notion',
                'linear', 'vercel', 'netlify', 'heroku', 'digitalocean'
            ]
            
            # Check if email contains vendor names and amounts
            has_vendor = any(vendor in body for vendor in common_vendors)
            has_amount = re.search(r'\$\d+(?:\.\d{2})?', body)
            
            if has_vendor and has_amount:
                return InvoiceType.EMAIL_CONTENT
            
            # Check for invoice indicators
            for pattern in invoice_indicators:
                if re.search(pattern, body, re.IGNORECASE):
                    return InvoiceType.EMAIL_CONTENT
            
            return InvoiceType.UNKNOWN
            
        except Exception as e:
            logger.error(f"Error classifying invoice type: {str(e)}")
            return InvoiceType.UNKNOWN
    
    def _extract_pdf_attachments(self, message: Dict) -> List[Dict]:
        """Extract PDF attachment information"""
        pdf_attachments = []
        
        try:
            payload = message.get('payload', {})
            parts = payload.get('parts', [])
            
            def extract_from_parts(parts_list):
                for part in parts_list:
                    if (part.get('filename') and 
                        part.get('mimeType', '').lower() == 'application/pdf'):
                        
                        attachment = {
                            'id': part['body']['attachmentId'],
                            'filename': part['filename'],
                            'mime_type': part['mimeType'],
                            'size': part['body'].get('size', 0),
                            'message_id': message['id']
                        }
                        pdf_attachments.append(attachment)
                    
                    # Check nested parts
                    if 'parts' in part:
                        extract_from_parts(part['parts'])
            
            extract_from_parts(parts)
            return pdf_attachments
            
        except Exception as e:
            logger.error(f"Error extracting PDF attachments: {str(e)}")
            return []
    
    def _extract_invoice_links(self, email_body: str) -> List[Dict]:
        """Extract invoice download links from email body"""
        links = []
        
        try:
            # Parse HTML content
            soup = BeautifulSoup(email_body, 'html.parser')
            
            # Find all links
            for link in soup.find_all('a', href=True):
                href = link['href']
                text = link.get_text().strip().lower()
                
                # Check if link is likely an invoice link
                invoice_link_indicators = [
                    'invoice', 'receipt', 'statement', 'bill',
                    'download', 'view', 'pdf', 'document'
                ]
                
                if any(indicator in text for indicator in invoice_link_indicators):
                    links.append({
                        'url': href,
                        'text': text,
                        'type': 'invoice_link'
                    })
                elif href.lower().endswith('.pdf'):
                    links.append({
                        'url': href,
                        'text': text,
                        'type': 'pdf_link'
                    })
            
            # Also search for direct URLs in text
            url_pattern = r'https?://[^\s<>"{}|\\^`\[\]]+'
            text_urls = re.findall(url_pattern, email_body)
            
            for url in text_urls:
                if (url.lower().endswith('.pdf') or 
                    any(keyword in url.lower() for keyword in ['invoice', 'receipt', 'statement'])):
                    links.append({
                        'url': url,
                        'text': 'Direct URL',
                        'type': 'direct_url'
                    })
            
            return links
            
        except Exception as e:
            logger.error(f"Error extracting invoice links: {str(e)}")
            return []
    
    def _extract_invoice_content(self, email_body: str) -> Dict:
        """Extract invoice content indicators from email body"""
        try:
            content = {
                'has_invoice_number': False,
                'has_amount': False,
                'has_date': False,
                'has_vendor': False,
                'invoice_indicators': []
            }
            
            body_lower = email_body.lower()
            
            # Check for invoice number
            if re.search(r'invoice\s*#?\s*\d+', body_lower):
                content['has_invoice_number'] = True
                content['invoice_indicators'].append('invoice_number')
            
            # Check for amounts
            if re.search(r'\$\d+(?:\.\d{2})?', body_lower):
                content['has_amount'] = True
                content['invoice_indicators'].append('amount')
            
            # Check for dates
            date_patterns = [
                r'\d{1,2}[/-]\d{1,2}[/-]\d{2,4}',
                r'\w+ \d{1,2}, \d{4}',
                r'\d{4}-\d{2}-\d{2}'
            ]
            for pattern in date_patterns:
                if re.search(pattern, body_lower):
                    content['has_date'] = True
                    content['invoice_indicators'].append('date')
                    break
            
            # Check for vendor information
            vendor_indicators = ['from:', 'company:', 'vendor:', 'billed by:']
            for indicator in vendor_indicators:
                if indicator in body_lower:
                    content['has_vendor'] = True
                    content['invoice_indicators'].append('vendor')
                    break
            
            return content
            
        except Exception as e:
            logger.error(f"Error extracting invoice content: {str(e)}")
            return {}
    
    def _parse_email_message(self, message: Dict) -> Dict:
        """Parse email message into structured data"""
        try:
            # Extract headers
            headers = message.get('payload', {}).get('headers', [])
            email_data = {
                'message_id': message['id'],
                'thread_id': message.get('threadId', ''),
                'snippet': message.get('snippet', ''),
                'subject': '',
                'sender': '',
                'date': '',
                'body': '',
                'attachments': []
            }
            
            for header in headers:
                name = header['name'].lower()
                if name == 'subject':
                    email_data['subject'] = header['value']
                elif name == 'from':
                    email_data['sender'] = header['value']
                elif name == 'date':
                    email_data['date'] = header['value']
            
            # Extract body and attachments
            email_data['body'] = self._get_email_body(message)
            email_data['attachments'] = self._extract_all_attachments(message)
            
            return email_data
            
        except Exception as e:
            logger.error(f"Error parsing email message: {str(e)}")
            return {}
    
    def _get_email_body(self, message: Dict) -> str:
        """Extract email body text"""
        try:
            payload = message.get('payload', {})
            
            def extract_body_from_parts(parts):
                for part in parts:
                    mime_type = part.get('mimeType', '')
                    
                    if mime_type == 'text/html' and 'data' in part.get('body', {}):
                        data = part['body']['data']
                        html = base64.urlsafe_b64decode(data).decode('utf-8', errors='ignore')
                        soup = BeautifulSoup(html, 'html.parser')
                        return soup.get_text()
                    
                    elif mime_type == 'text/plain' and 'data' in part.get('body', {}):
                        data = part['body']['data']
                        return base64.urlsafe_b64decode(data).decode('utf-8', errors='ignore')
                    
                    if 'parts' in part:
                        body = extract_body_from_parts(part['parts'])
                        if body:
                            return body
                
                return ''
            
            # Handle multipart messages
            if 'parts' in payload:
                return extract_body_from_parts(payload['parts'])
            
            # Handle simple messages
            elif 'body' in payload and 'data' in payload['body']:
                data = payload['body']['data']
                return base64.urlsafe_b64decode(data).decode('utf-8', errors='ignore')
            
            return ''
            
        except Exception as e:
            logger.error(f"Error getting email body: {str(e)}")
            return ''
    
    def _extract_all_attachments(self, message: Dict) -> List[Dict]:
        """Extract all attachment information"""
        attachments = []
        
        try:
            payload = message.get('payload', {})
            
            def extract_from_parts(parts_list):
                for part in parts_list:
                    if part.get('filename') and part.get('body', {}).get('attachmentId'):
                        attachment = {
                            'id': part['body']['attachmentId'],
                            'filename': part['filename'],
                            'mime_type': part.get('mimeType', ''),
                            'size': part['body'].get('size', 0),
                            'message_id': message['id']
                        }
                        attachments.append(attachment)
                    
                    # Check nested parts
                    if 'parts' in part:
                        extract_from_parts(part['parts'])
            
            if 'parts' in payload:
                extract_from_parts(payload['parts'])
            
            return attachments
            
        except Exception as e:
            logger.error(f"Error extracting attachments: {str(e)}")
            return []
    
    async def download_link_content(self, url: str) -> Optional[bytes]:
        """Download content from invoice link"""
        try:
            if not self.session:
                self.session = aiohttp.ClientSession()
            
            async with self.session.get(url, timeout=30) as response:
                if response.status == 200:
                    return await response.read()
                else:
                    logger.error(f"Failed to download link content: HTTP {response.status}")
                    return None
                    
        except Exception as e:
            logger.error(f"Error downloading link content: {str(e)}")
            return None
    
    def download_attachment(self, message_id: str, attachment_id: str) -> Optional[bytes]:
        """Download attachment content"""
        try:
            attachment = self.service.users().messages().attachments().get(
                userId='me',
                messageId=message_id,
                id=attachment_id
            ).execute()
            
            data = attachment['data']
            return base64.urlsafe_b64decode(data)
            
        except Exception as e:
            logger.error(f"Error downloading attachment: {str(e)}")
            return None
    
    def _is_invoice_email_ai(self, email_data: Dict) -> bool:
        """Use Gemini AI to determine if email contains invoice information"""
        try:
            if not self.gemini_api_key:
                return True  # Fallback to traditional filtering if no API key
            
            # Prepare email content for AI analysis
            subject = email_data.get('subject', '')[:100]
            sender = email_data.get('sender', '')[:100]
            snippet = email_data.get('snippet', '')[:200]
            
            # Simplified prompt - just use subject and sender for classification
            prompt = f"""Is this email an invoice, bill, receipt, or payment?

From: {sender}
Subject: {subject}
Preview: {snippet}

Reply only YES or NO."""
            
            response = self._call_gemini_api_simple(prompt)
            
            if response:
                is_invoice = response.strip().upper() == 'YES'
                logger.info(f"AI classification for {email_data['message_id']}: {'INVOICE' if is_invoice else 'NOT INVOICE'}")
                return is_invoice
            else:
                logger.warning("AI classification failed, falling back to traditional filtering")
                return True  # Fallback to traditional filtering
                
        except Exception as e:
            logger.error(f"Error in AI email classification: {str(e)}")
            return True  # Fallback to traditional filtering on error
    
    def _call_gemini_api_simple(self, prompt: str) -> Optional[str]:
        """Simple Gemini API call for email classification"""
        try:
            import requests
            
            url = f"https://generativelanguage.googleapis.com/v1/models/gemini-2.5-flash:generateContent?key={self.gemini_api_key}"
            
            headers = {
                "Content-Type": "application/json"
            }
            
            payload = {
                "contents": [
                    {
                        "parts": [
                            {
                                "text": prompt
                            }
                        ]
                    }
                ],
                "generationConfig": {
                    "temperature": 0.1,  # Low temperature for consistent classification
                    "maxOutputTokens": 2000,  # Increased significantly to account for thought tokens
                    "topK": 1,
                    "topP": 0.95,
                }
            }
            
            response = requests.post(url, headers=headers, json=payload, timeout=15)
            
            if response.status_code == 200:
                result = response.json()
                if 'candidates' in result and len(result['candidates']) > 0:
                    try:
                        candidate = result['candidates'][0]
                        # Try to extract text from different possible structures
                        if 'content' in candidate:
                            content_obj = candidate['content']
                            # Try parts structure first
                            if isinstance(content_obj, dict) and 'parts' in content_obj:
                                if len(content_obj['parts']) > 0 and 'text' in content_obj['parts'][0]:
                                    content = content_obj['parts'][0]['text']
                                    return content.strip()
                            # Try direct text in content
                            elif isinstance(content_obj, str):
                                return content_obj.strip()
                            # Try text field in content object
                            elif isinstance(content_obj, dict) and 'text' in content_obj:
                                return content_obj['text'].strip()
                        elif 'text' in candidate:
                            # Direct text access
                            return candidate['text'].strip()
                        
                        # If we get here, log the actual structure for debugging
                        logger.error(f"Could not extract text from Gemini response")
                        logger.error(f"Candidate keys: {list(candidate.keys())}")
                        logger.error(f"Finish reason: {candidate.get('finishReason', 'None')}")
                        if 'content' in candidate:
                            content = candidate['content']
                            logger.error(f"Content type: {type(content)}")
                            if isinstance(content, dict):
                                logger.error(f"Content keys: {list(content.keys())}")
                                if 'role' in content:
                                    logger.error(f"Content role: {content['role']}")
                                # Log the full content for debugging
                                logger.error(f"Full content: {json.dumps(content, default=str)}")
                        return None
                    except KeyError as e:
                        logger.error(f"KeyError accessing Gemini response parts: {str(e)}")
                        logger.error(f"Candidate structure: {json.dumps(candidate, default=str)}")
                        return None
                else:
                    logger.error("No candidates in Gemini response")
                    return None
            else:
                logger.error(f"Gemini API error: {response.status_code} - {response.text}")
                return None
                
        except Exception as e:
            logger.error(f"Error calling Gemini API: {str(e)}")
            return None

    def search_invoice_emails(self, days_back: int = 90, custom_query: str = None) -> List[Dict]:
        """
        SIMPLIFIED: Just search emails by date range or custom query
        No complex filtering - let Gemini decide what's an invoice
        """
        try:
            # Use custom query if provided
            if custom_query:
                query = custom_query
            else:
                # Simple date-based query
                since_date = (datetime.utcnow() - timedelta(days=days_back)).strftime('%Y/%m/%d')
                query = f"after:{since_date}"
            
            logger.info(f"📧 Searching emails with query: {query}")
            
            messages = self.service.users().messages().list(
                userId='me',
                q=query,
                maxResults=100  # Reasonable limit
            ).execute()
            
            email_messages = messages.get('messages', [])
            logger.info(f"Found {len(email_messages)} emails")
            
            results = []
            for msg in email_messages:
                try:
                    # Get full message
                    full_message = self.service.users().messages().get(
                        userId='me',
                        id=msg['id']
                    ).execute()
                    
                    # Parse the email
                    email_data = self._parse_email_message(full_message)
                    if email_data:
                        results.append(email_data)
                        
                except Exception as e:
                    logger.error(f"Error processing message {msg['id']}: {str(e)}")
                    continue
            
            return results
            
        except Exception as e:
            logger.error(f"Error searching emails: {str(e)}")
            return []
    
    def _search_with_custom_query(self, query: str) -> List[Dict]:
        """Search emails using a custom Gmail query"""
        try:
            if not self.service:
                logger.error("Gmail service not authenticated")
                return []
            
            logger.info(f"Executing Gmail search: {query}")
            
            # Search messages
            results = self.service.users().messages().list(
                userId='me', 
                q=query,
                maxResults=100  # Limit to prevent too many results
            ).execute()
            
            messages = results.get('messages', [])
            logger.info(f"Found {len(messages)} messages")
            
            # Get full message details
            emails = []
            for message in messages:
                try:
                    msg = self.service.users().messages().get(
                        userId='me', 
                        id=message['id'],
                        format='full'
                    ).execute()
                    
                    email_data = self._parse_email_message(msg)
                    if email_data:
                        emails.append(email_data)
                        
                except Exception as e:
                    logger.error(f"Error getting message {message['id']}: {str(e)}")
                    continue
            
            logger.info(f"Successfully parsed {len(emails)} emails")
            return emails
            
        except Exception as e:
            logger.error(f"Error in custom query search: {str(e)}")
            return []
    
    def search_group_emails(self, group_emails: List[str], days_back: int = 90) -> List[Dict]:
        """Search for emails from specific group email addresses in the last N days"""
        try:
            from datetime import timedelta
            
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days_back)
            
            logger.info(f"Searching for group emails from {len(group_emails)} groups from {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}")
            
            return self.scan_emails_by_date_range(
                start_date=start_date,
                end_date=end_date,
                group_emails=group_emails
            )
            
        except Exception as e:
            logger.error(f"Error searching group emails: {str(e)}")
            return []

    async def close(self):
        """Clean up resources"""
        if self.session:
            await self.session.close() 