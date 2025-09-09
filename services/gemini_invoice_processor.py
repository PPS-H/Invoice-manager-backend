import base64
import json
import logging
import re
from typing import Dict, List, Optional, Any
from datetime import datetime
import requests
import PyPDF2
import io
from PIL import Image
import os
import time
import asyncio

logger = logging.getLogger(__name__)

class GeminiInvoiceProcessor:
    """Gemini AI service for processing invoices from various sources"""
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://generativelanguage.googleapis.com/v1"  # Use the stable v1 API
        self.model = "gemini-2.5-flash"  # Back to 2.5-flash as requested
        self.last_api_call = 0
        self.min_call_interval = 0.5  # Minimum 0.5 seconds between API calls
        
        # Invoice extraction prompt templates
        self.pdf_prompt = """
        Analyze this PDF document and extract invoice information. Return a JSON object with the following structure:
        {
            "vendor_name": "string",
            "invoice_number": "string",
            "invoice_date": "YYYY-MM-DD",
            "due_date": "YYYY-MM-DD",
            "amount": "float",
            "currency": "string",
            "tax_amount": "float",
            "total_amount": "float",
            "category": "string",
            "line_items": [
                {
                    "description": "string",
                    "quantity": "float",
                    "unit_price": "float",
                    "total": "float"
                }
            ],
            "billing_address": "string",
            "payment_terms": "string",
            "confidence_score": "float (0-1)"
        }
        
        Only extract information that is clearly visible in the document. Use null for missing fields.
        Set confidence_score based on how clear and complete the invoice data is.
        """
        
        self.email_content_prompt = """
        Analyze this email content and extract invoice/payment information. This could be:
        - A formal invoice
        - A payment confirmation/receipt
        - A billing notification
        - A subscription charge confirmation
        - A payment statement
        - A billing summary
        - A charge notification
        - A receipt email
        - Seat upgrade confirmations (YES, these are invoices - extract the charge amount)

        Return a JSON object with this structure:
        {{
            "vendor_name": "Company Name",
            "invoice_number": "invoice/transaction ID or null",
            "invoice_date": "YYYY-MM-DD or null",
            "due_date": "YYYY-MM-DD or null", 
            "amount": 100.50,
            "currency": "USD",
            "tax_amount": 5.25 or null,
            "total_amount": 105.75,
            "category": "software",
            "confidence_score": 0.9
        }}

        EXTRACTION RULES:
        - vendor_name: Extract the ACTUAL company name (e.g., "Figma", "Microsoft", "Stripe", "Google", "GitHub")
        - invoice_number: Look for ANY reference number. Common patterns:
          * GitHub: Look for numbers like "12345678", "GH-123456", or transaction IDs
          * Datadog: "DD-123456", "INV-123456" 
          * If NO clear invoice number found, generate: "AUTO-{date}-{amount}"
        - amounts: Extract numeric values as floats. If only one amount is found, use it for both amount and total_amount.
        - dates: Use YYYY-MM-DD format. If no invoice date, use email date. Use null for missing dates.
        - currency: Extract currency code (USD, EUR, etc.) or use "USD" as default
        - confidence_score: Rate 0.3-1.0 based on data quality
          * 0.3-0.4: Payment confirmation with vendor and amount only
          * 0.5-0.7: Good invoice data with most fields
          * 0.8-1.0: Complete formal invoice with all fields

        CRITICAL - BE EXTREMELY INCLUSIVE:
        - ANY email mentioning money/payments from legitimate vendors = PROCESS IT
        - Payment confirmations, receipts, bills, statements = ALL valid invoices
        - Don't reject emails just because they lack formal invoice structure
        - If vendor name + amount exists, it's worth saving
        - Even simple "Thank you for your payment" emails = VALID invoices
        - Subscription renewals = VALID invoices
        - Seat upgrades = VALID invoices
        - Monthly charges = VALID invoices

        SPECIAL CASES:
        - Figma "Thank you for your payment": Extract vendor="Figma", look for amounts in email body
        - Subscription charges, payment confirmations, billing notifications: ALL valid invoices
        - GitHub payment receipts: VALID - extract vendor="GitHub", amount, use AUTO-GH-date-amount for invoice_number
        - Datadog billing: VALID - extract all available data
        - Only reject if NO vendor name and NO amount can be found

        Email Content:
        {content}

        JSON Response:"""
        
        self.link_content_prompt = """
        Analyze this downloaded content from an invoice link and extract invoice information.
        The content might be HTML, PDF, or other formats containing invoice data.
        
        Return the same JSON structure as specified above.
        
        Content:
        {content}
        """
    
    def process_pdf_attachment(self, pdf_data: bytes, filename: str) -> Dict[str, Any]:
        """Process PDF attachment using Gemini AI"""
        try:
            # Convert PDF to images for Gemini processing
            images = self._pdf_to_images(pdf_data)
            
            if not images:
                # Fallback: extract text from PDF
                text_content = self._extract_pdf_text(pdf_data)
                if text_content:
                    return self._process_text_content(text_content, "pdf_text")
                else:
                    return {"error": "Unable to extract content from PDF"}
            
            # Process images with Gemini Vision
            return self._process_images_with_gemini(images, self.pdf_prompt)
            
        except Exception as e:
            logger.error(f"Error processing PDF attachment {filename}: {str(e)}")
            return {"error": f"PDF processing failed: {str(e)}"}
    
    def process_email_content(self, email_body: str, subject: str = "") -> Dict[str, Any]:

        print('=======================144',email_body)
        """Process email content using Gemini AI"""
        try:
            # Combine subject and body for better context
            full_content = f"Subject: {subject}\n\nContent:\n{email_body}"
            
            # Log email details for debugging
            logger.info(f"📧 GEMINI PROCESSING EMAIL:")
            logger.info(f"   📨 Subject: {subject[:80]}{'...' if len(subject) > 80 else ''}")
            logger.info(f"   📏 Content Length: {len(email_body)} chars")
            logger.info(f"   📝 Body Preview: {email_body[:150]}{'...' if len(email_body) > 150 else ''}")
            
            # Use safer string replacement to avoid KeyError from curly braces in email content
            prompt = self.email_content_prompt.replace("{content}", full_content)
            result = self._process_text_content(full_content, "email", prompt)
            
            if result.get('error'):
                logger.error(f"❌ GEMINI PROCESSING FAILED: {result['error']}")
            else:
                logger.info(f"✅ GEMINI PROCESSING COMPLETED")
                
            return result
            
        except Exception as e:
            logger.error(f"Error processing email content: {str(e)}")
            return {"error": f"Email content processing failed: {str(e)}"}
    
    def process_link_content(self, content: bytes, url: str, content_type: str = "") -> Dict[str, Any]:
        """Process downloaded link content using Gemini AI"""
        try:
            # Determine content type and process accordingly
            if content_type.lower() == 'application/pdf' or url.lower().endswith('.pdf'):
                return self.process_pdf_attachment(content, url)
            
            # Try to decode as text content
            try:
                text_content = content.decode('utf-8', errors='ignore')
            except:
                text_content = str(content)
            
            # Use safer string replacement to avoid KeyError from curly braces in content
            prompt = self.link_content_prompt.replace("{content}", text_content[:5000])
            return self._process_text_content(text_content, "link", prompt)
            
        except Exception as e:
            logger.error(f"Error processing link content from {url}: {str(e)}")
            return {"error": f"Link content processing failed: {str(e)}"}
    
    def _pdf_to_images(self, pdf_data: bytes) -> List[str]:
        """Convert PDF pages to base64 images"""
        try:
            # This is a simplified version - you might need pdf2image library
            # For now, we'll try to extract text instead
            return []
        except Exception as e:
            logger.error(f"Error converting PDF to images: {str(e)}")
            return []
    
    def _extract_pdf_text(self, pdf_data: bytes) -> str:
        """Extract text content from PDF"""
        try:
            pdf_reader = PyPDF2.PdfReader(io.BytesIO(pdf_data))
            text_content = ""
            
            for page in pdf_reader.pages:
                text_content += page.extract_text() + "\n"
            
            return text_content.strip()
            
        except Exception as e:
            logger.error(f"Error extracting PDF text: {str(e)}")
            return ""
    
    def _process_text_content(self, content: str, source_type: str, custom_prompt: str = None) -> Dict[str, Any]:
        """Process text content using Gemini AI with strict validation"""
        try:
            if not self.api_key:
                return {"error": "Gemini API key not configured"}
                
            prompt = custom_prompt or self.pdf_prompt
            
            # Clean and optimize content for Gemini processing
            clean_content = self._optimize_content_for_gemini(content)
            
            # Prepare the request with explicit JSON requirement
            full_prompt = f"""{prompt}

CRITICAL INSTRUCTIONS:
- Return ONLY a raw JSON object (no markdown, no code blocks, no explanations)
- Do not wrap in ```json``` or any other formatting
- Start directly with {{ and end with }}
- For missing optional fields, use null (not "Unknown" or empty strings)
- Minimum required fields: vendor_name and total_amount (others can be null)

Content to analyze:
{clean_content}"""
            
            # Try multiple times with Gemini to ensure we get valid JSON
            max_retries = 2
            for attempt in range(max_retries):
                logger.info(f"🤖 Gemini processing attempt {attempt + 1}/{max_retries}")

                # print('--=====================244')
                
                response = self._call_gemini_api(full_prompt)
                
                if response:
                    # Try to parse JSON response
                    invoice_data = self._parse_gemini_response(response)
                    
                    # Make sure invoice_data is not None before calling .get()
                    if invoice_data is None:
                        logger.warning(f"⚠️ Gemini returned None on attempt {attempt + 1}")
                        continue
                    
                    # Validate the response has required fields
                    if not invoice_data.get('error') and self._validate_gemini_response(invoice_data):
                        invoice_data['source_type'] = source_type
                        invoice_data['processing_timestamp'] = datetime.utcnow().isoformat()
                        logger.info(f"✅ Gemini successfully processed content: vendor={invoice_data.get('vendor_name')}, amount={invoice_data.get('total_amount')}")
                        return invoice_data
                    elif invoice_data.get('vendor_name') is None and invoice_data.get('total_amount') is None:
                        # This is correctly identified as non-invoice
                        logger.info("✅ Email correctly identified as NON-INVOICE by Gemini")
                        logger.info(f"   Gemini response: {invoice_data}")
                        return {"error": "Not an invoice - correctly identified by Gemini", "is_non_invoice": True}
                    elif attempt < max_retries - 1:
                        logger.warning(f"⚠️ Gemini response needs retry on attempt {attempt + 1}")
                        continue
                else:
                    logger.warning(f"⚠️ No Gemini response on attempt {attempt + 1}")
                    
            # If all attempts failed, return error instead of None to prevent NoneType errors
            logger.error("⚠️ GEMINI EMAIL PROCESSING FAILED: Gemini failed to provide valid response after multiple attempts")
            return {"error": "Gemini failed to provide valid response after multiple attempts"}
                
        except Exception as e:
            logger.error(f"Error processing text content: {str(e)}")
            return {"error": f"Text processing failed: {str(e)}"}
    
    def _process_images_with_gemini(self, images: List[str], prompt: str) -> Dict[str, Any]:
        """Process images using Gemini Vision API"""
        try:
            # This would use Gemini's vision capabilities
            # For now, fallback to text processing
            return {"error": "Image processing not implemented yet"}
            
        except Exception as e:
            logger.error(f"Error processing images with Gemini: {str(e)}")
            return {"error": f"Image processing failed: {str(e)}"}
    
    def _call_gemini_api(self, prompt: str) -> Optional[str]:
        """Call DeepSeek API with the given prompt"""

        # print('================298',prompt)
        try:
            # Rate limiting
            current_time = time.time()
            time_since_last_call = current_time - self.last_api_call
            if time_since_last_call < self.min_call_interval:
                sleep_time = self.min_call_interval - time_since_last_call
                logger.info(f"⏳ Rate limiting: sleeping for {sleep_time:.2f}s")
                time.sleep(sleep_time)
            self.last_api_call = time.time()
            
            if not self.api_key:
                logger.error("❌ CRITICAL: DeepSeek API key not provided")
                return None
                
            # DeepSeek API endpoint
            url = "https://api.deepseek.com/v1/chat/completions"
            
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}"
            }
            
            payload = {
                "model": "deepseek-chat",
                "messages": [
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                "temperature": 0.1,
                "top_p": 0.95,
                "max_tokens": 4000,
                "stream": False
            }
            
            logger.info(f"🌐 Calling DeepSeek API: {url}")
            logger.info(f"📊 Prompt length: {len(prompt)} chars")
            logger.info(f"🔑 API key present: {bool(self.api_key and len(self.api_key) > 10)}")
            
            response = requests.post(url, headers=headers, json=payload, timeout=30)
            
            logger.info(f"📈 DeepSeek API response status: {response.status_code}")
            
            if response.status_code == 200:
                result = response.json()
                logger.info(f"📊 DeepSeek response keys: {list(result.keys())}")
                
                if 'choices' in result and len(result['choices']) > 0:
                    choice = result['choices'][0]
                    logger.info(f"🎯 Choice keys: {list(choice.keys())}")
                    
                    # Check for finish reason
                    finish_reason = choice.get('finish_reason', '')
                    if finish_reason:
                        logger.info(f"🏁 Finish reason: {finish_reason}")
                        
                    if finish_reason == 'length':  # DeepSeek equivalent of MAX_TOKENS
                        logger.warning("❌ DeepSeek hit max tokens limit - response truncated")
                        # Try to extract partial content if available
                        if 'message' in choice and 'content' in choice['message']:
                            partial_text = choice['message']['content']
                            if partial_text:
                                logger.warning(f"⚠️ Attempting to parse truncated response: {partial_text[:200]}...")
                                # Don't return None here - let the parsing continue below
                            else:
                                return None
                        else:
                            return None
                    elif finish_reason == 'content_filter':  # DeepSeek equivalent of SAFETY
                        logger.error("❌ DeepSeek blocked for content filter reasons")
                        return None
                    elif finish_reason not in ['stop', '']:
                        logger.warning(f"⚠️ DeepSeek finished with reason: {finish_reason}")
                    
                    # Handle DeepSeek response structure
                    content_text = None
                    
                    try:
                        # DeepSeek uses OpenAI-compatible structure
                        if 'message' in choice and 'content' in choice['message']:
                            content_text = choice['message']['content']
                            logger.info(f"✅ Extracted text from message.content, length: {len(content_text)}")
                        
                        # Fallback: try direct content access
                        elif 'content' in choice:
                            content_text = choice['content']
                            logger.info(f"✅ Extracted text from direct choice.content, length: {len(content_text)}")
                        
                        # Another fallback: try text field
                        elif 'text' in choice:
                            content_text = choice['text']
                            logger.info(f"✅ Extracted text from choice.text, length: {len(content_text)}")
                        
                        if content_text:
                            logger.info(f"✅ DeepSeek response length: {len(content_text)}, first 200 chars: {content_text[:200]}")
                            return content_text.strip()
                        else:
                            logger.error(f"❌ Could not extract text from choice structure: {list(choice.keys())}")
                            logger.error(f"❌ Full choice structure: {json.dumps(choice, indent=2, default=str)}")
                            return None
                            
                    except KeyError as e:
                        logger.error(f"❌ KeyError accessing DeepSeek response: {str(e)}")
                        logger.error(f"❌ Choice structure: {json.dumps(choice, indent=2, default=str)}")
                        return None
                    except Exception as e:
                        logger.error(f"❌ Error parsing DeepSeek response: {str(e)}")
                        return None
                else:
                    logger.error(f"❌ No choices in DeepSeek response: {result}")
                    return None
            else:
                logger.error(f"❌ DeepSeek API error {response.status_code}: {response.text}")
                # Try to parse error message for better debugging
                try:
                    error_data = response.json()
                    if 'error' in error_data:
                        error_msg = error_data['error'].get('message', 'Unknown error')
                        logger.error(f"❌ DeepSeek error details: {error_msg}")
                except:
                    pass
                return None
                
        except requests.RequestException as e:
            logger.error(f"❌ Network error calling DeepSeek API: {str(e)}")
            return None
        except Exception as e:
            logger.error(f"❌ Unexpected error calling DeepSeek API: {str(e)}")
            return None
    
    def _parse_gemini_response(self, response: str) -> Dict[str, Any]:
        """Parse Gemini response and extract JSON"""
        try:
            logger.info(f"Parsing Gemini response: {response[:500]}...")
            
            # Clean the response - remove control characters and fix encoding
            cleaned_response = response.strip()
            
            # Remove control characters that break JSON parsing
            import re
            cleaned_response = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', cleaned_response)
            
            # Fix common JSON formatting issues
            cleaned_response = cleaned_response.replace('\n', ' ').replace('\r', ' ')
            cleaned_response = re.sub(r'\s+', ' ', cleaned_response)  # Multiple spaces to single
            
            # Try to parse as direct JSON first
            try:
                result = json.loads(cleaned_response)
                logger.info("Successfully parsed response as direct JSON")
                return result
            except json.JSONDecodeError:
                pass
            
            # Try to find JSON block in the response with improved patterns
            json_patterns = [
                r'```json\s*(\{.*?\})\s*```',        # JSON in code blocks
                r'```\s*(\{.*?\})\s*```',            # Any code block with JSON
                r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}',  # Match balanced braces
                r'\{(?:[^{}]|{[^{}]*})*\}',          # Better balanced matching
                r'\{.*?\}',                          # Greedy match within braces
            ]
            
            for i, pattern in enumerate(json_patterns):
                matches = re.findall(pattern, cleaned_response, re.DOTALL | re.IGNORECASE)
                logger.info(f"🔍 Pattern {i+1} found {len(matches)} potential JSON matches")
                
                for j, match in enumerate(matches):
                    try:
                        if isinstance(match, tuple):
                            match = match[0] if match else match
                        
                        # Clean the match
                        json_str = match.strip()
                        logger.info(f"📝 Attempting to parse match {j+1}: {json_str[:150]}...")
                        result = json.loads(json_str)
                        logger.info(f"✅ Successfully parsed JSON using pattern {i+1}")
                        return result
                    except json.JSONDecodeError as e:
                        logger.warning(f"❌ JSON parse failed for match {j+1}: {str(e)}")
                        continue
            
            logger.error("❌ No valid JSON found in Gemini response")
            logger.error(f"📄 Full Gemini response: {response}")
            return {"error": "Failed to parse valid JSON from Gemini response", "raw_response": response[:500]}
                
        except Exception as e:
            logger.error(f"Error parsing Gemini response: {str(e)}")
            return {"error": f"JSON parsing failed: {str(e)}", "raw_response": response[:500]}
    
    def _optimize_content_for_gemini(self, content: str) -> str:
        """Optimize email content for Gemini processing by removing unnecessary parts"""
        try:
            # Remove common email signatures and footers
            signature_patterns = [
                r'--\s*\n.*$',  # Email signatures starting with --
                r'Sent from my .*$',  # Mobile signatures
                r'Get Outlook for .*$',  # Outlook signatures
                r'Confidentiality Notice.*$',  # Legal disclaimers
                r'This email and any attachments.*$',  # Disclaimers
                r'The information in this email.*$',  # Legal text
            ]
            
            optimized = content
            for pattern in signature_patterns:
                optimized = re.sub(pattern, '', optimized, flags=re.MULTILINE | re.DOTALL)
            
            # Remove excessive whitespace and newlines
            optimized = re.sub(r'\n\s*\n\s*\n+', '\n\n', optimized)  # Multiple newlines to double
            optimized = re.sub(r'[ \t]+', ' ', optimized)  # Multiple spaces to single
            
            # Remove HTML-like content if present
            optimized = re.sub(r'<[^>]+>', ' ', optimized)
            
            # Keep only most relevant parts - prioritize content with numbers and currency
            lines = optimized.split('\n')
            relevant_lines = []
            
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                    
                # Keep lines with currency symbols, numbers, or key invoice words
                if any(char in line for char in ['$', '€', '£', '¥']) or \
                   any(word in line.lower() for word in ['invoice', 'bill', 'amount', 'total', 'paid', 'due', 'charge']) or \
                   re.search(r'\d+[.,]\d+', line):  # Contains price-like numbers
                    relevant_lines.append(line)
                elif len(relevant_lines) < 10:  # Keep first 10 lines for context
                    relevant_lines.append(line)
            
            # Join and limit final size
            result = '\n'.join(relevant_lines)
            
            # Final size limit (reduced to avoid MAX_TOKENS)
            if len(result) > 1500:
                result = result[:1500] + "... [content truncated]"
                
            logger.info(f"📝 Content optimized: {len(content)} → {len(result)} chars")
            return result
            
        except Exception as e:
            logger.error(f"Error optimizing content: {str(e)}")
            # Fallback to simple truncation
            return content.replace('\n', ' ').replace('\r', ' ')[:1500]
    
    def _validate_gemini_response(self, response_data: Dict[str, Any]) -> bool:
        """Validate Gemini response has required fields"""
        try:
            # Log the full response for debugging
            logger.info(f"🔍 VALIDATING GEMINI RESPONSE:")
            logger.info(f"   Raw data: {json.dumps(response_data, indent=2)}")
            
            # Check if response indicates this is NOT an invoice (e.g., seat request)
            vendor_name = response_data.get('vendor_name')
            total_amount = response_data.get('total_amount')
            
            # If both vendor and amount are null, this is correctly identified as non-invoice
            if vendor_name is None and total_amount is None:
                logger.info("✅ CORRECT: Gemini identified this as NOT an invoice (vendor and amount are null)")
                logger.info("   This email will be skipped - working as intended!")
                return False
            
            # If we have vendor but no amount, it might be incomplete
            if vendor_name and not total_amount:
                logger.warning(f"⚠️ Incomplete invoice data: Has vendor '{vendor_name}' but no amount")
                return False
            
            # Must have vendor_name (but be more flexible)
            if not vendor_name or vendor_name.lower() in ['string', 'unknown', ''] or len(str(vendor_name).strip()) < 2:
                logger.warning(f"❌ Invalid vendor_name: {vendor_name}")
                return False
            
            # Must have a valid amount (allow 0 for refunds, free services, and various formats)
            if total_amount is None or total_amount == "" or total_amount == "null":
                logger.warning(f"❌ Missing total_amount: {total_amount}")
                return False
            
            # Handle various amount formats
            try:
                # Convert string amounts like "$100.00", "100", "0.00" to float
                if isinstance(total_amount, str):
                    # Remove currency symbols and spaces
                    clean_amount = total_amount.replace('$', '').replace('€', '').replace('£', '').replace(',', '').strip()
                    if clean_amount.lower() in ['free', 'no charge', 'complimentary', '', 'null']:
                        amount_float = 0.0
                    else:
                        amount_float = float(clean_amount)
                else:
                    amount_float = float(total_amount)
                
                # Allow negative amounts for refunds
                if amount_float < -10000:  # Reasonable limit for refunds
                    logger.warning(f"Amount too negative: {amount_float}")
                    return False
                    
            except (ValueError, TypeError):
                logger.warning(f"❌ Amount not convertible to number: {total_amount}")
                return False
            
            # Check confidence score if present (more lenient)
            confidence = response_data.get('confidence_score', 1.0)
            if confidence < 0.2:  # Further lowered to 0.2 to accept more invoices
                logger.warning(f"❌ Low confidence score: {confidence}")
                return False
            
            logger.info(f"✅ VALID INVOICE: vendor={vendor_name}, amount={total_amount}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error validating Gemini response: {str(e)}")
            return False
    
    def validate_invoice_data(self, invoice_data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate and clean extracted invoice data"""
        try:
            validated_data = invoice_data.copy()
            
            # Validate required fields
            required_fields = ['vendor_name', 'total_amount']
            for field in required_fields:
                if not validated_data.get(field):
                    validated_data['validation_errors'] = validated_data.get('validation_errors', [])
                    validated_data['validation_errors'].append(f"Missing required field: {field}")
            
            # Validate amount fields
            amount_fields = ['amount', 'total_amount', 'tax_amount']
            for field in amount_fields:
                if validated_data.get(field) is not None:
                    try:
                        validated_data[field] = float(validated_data[field])
                        if validated_data[field] < 0:
                            validated_data['validation_errors'] = validated_data.get('validation_errors', [])
                            validated_data['validation_errors'].append(f"Invalid {field}: cannot be negative")
                    except (ValueError, TypeError):
                        validated_data['validation_errors'] = validated_data.get('validation_errors', [])
                        validated_data['validation_errors'].append(f"Invalid {field}: not a valid number")
            
            # Validate date fields
            date_fields = ['invoice_date', 'due_date']
            for field in date_fields:
                if validated_data.get(field):
                    try:
                        # Try to parse and standardize date format
                        parsed_date = self._parse_date(validated_data[field])
                        if parsed_date:
                            validated_data[field] = parsed_date.strftime('%Y-%m-%d')
                        else:
                            validated_data['validation_errors'] = validated_data.get('validation_errors', [])
                            validated_data['validation_errors'].append(f"Invalid {field}: cannot parse date")
                    except Exception:
                        validated_data['validation_errors'] = validated_data.get('validation_errors', [])
                        validated_data['validation_errors'].append(f"Invalid {field}: date parsing error")
            
            # Set default currency
            if not validated_data.get('currency'):
                validated_data['currency'] = 'USD'
            
            # Calculate confidence score based on completeness
            total_fields = 8  # Number of important fields
            completed_fields = sum(1 for field in ['vendor_name', 'invoice_number', 'invoice_date', 'amount', 'total_amount', 'currency'] if validated_data.get(field))
            calculated_confidence = completed_fields / total_fields
            
            if 'confidence_score' not in validated_data:
                validated_data['confidence_score'] = calculated_confidence
            
            return validated_data
            
        except Exception as e:
            logger.error(f"Error validating invoice data: {str(e)}")
            invoice_data['validation_error'] = str(e)
            return invoice_data
    
    def _parse_date(self, date_str: str) -> Optional[datetime]:
        """Parse various date formats"""
        date_formats = [
            '%Y-%m-%d',
            '%m/%d/%Y',
            '%d/%m/%Y',
            '%m-%d-%Y',
            '%d-%m-%Y',
            '%B %d, %Y',
            '%b %d, %Y',
            '%Y/%m/%d'
        ]
        
        for fmt in date_formats:
            try:
                return datetime.strptime(date_str.strip(), fmt)
            except ValueError:
                continue
        
        return None 