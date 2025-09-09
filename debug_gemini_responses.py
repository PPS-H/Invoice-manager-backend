#!/usr/bin/env python3
"""Debug Gemini responses to understand the format"""

import os
from services.gemini_invoice_processor import GeminiInvoiceProcessor

# Test different types of emails
test_emails = [
    {
        "name": "Newsletter (NOT an invoice)",
        "subject": "How to Build a Custom AI Copilot",
        "body": """
        Hey there!
        
        Check out our latest blog post about building AI copilots.
        Learn how to integrate AI into your workflow.
        
        Best,
        The Team
        """
    },
    {
        "name": "Valid Invoice",
        "subject": "Your Google Cloud invoice is available",
        "body": """
        Invoice Number: CLOUD-12345
        Amount Due: $1,234.56
        Due Date: January 15, 2025
        
        Thank you for using Google Cloud Platform.
        """
    },
    {
        "name": "Payment Confirmation",
        "subject": "Thank you for your payment!",
        "body": """
        Hi there,
        
        We've received your payment to Figma.
        
        Amount paid: $390.00
        Date: December 15, 2024
        
        Thanks,
        Figma Team
        """
    }
]

def main():
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("❌ GEMINI_API_KEY not found")
        return
    
    processor = GeminiInvoiceProcessor(api_key)
    
    print("🔍 UNDERSTANDING GEMINI RESPONSES")
    print("=" * 60)
    
    for test in test_emails:
        print(f"\n📧 Testing: {test['name']}")
        print(f"Subject: {test['subject']}")
        print("-" * 40)
        
        # Show the exact prompt being sent
        prompt = processor.email_content_prompt.format(
            content=f"Subject: {test['subject']}\n\n{test['body']}"
        )
        
        print("\n📤 PROMPT SENT TO GEMINI:")
        print("```")
        print(prompt[:500] + "..." if len(prompt) > 500 else prompt)
        print("```")
        
        # Get response
        result = processor.process_email_content(test['body'], test['subject'])
        
        print("\n📥 GEMINI RESPONSE:")
        print("```json")
        if result.get('error'):
            print(f"ERROR: {result['error']}")
        else:
            import json
            print(json.dumps(result, indent=2))
        print("```")
        
        print("\n✅ INTERPRETATION:")
        if result.get('error'):
            if "non-invoice" in result.get('error', ''):
                print("→ This is NOT an invoice (Gemini correctly identified it)")
            else:
                print("→ Gemini had an error processing this")
        else:
            print(f"→ This IS an invoice from {result.get('vendor_name')}")
            print(f"→ Amount: ${result.get('total_amount')}")
            print(f"→ Confidence: {result.get('confidence_score')}")

if __name__ == "__main__":
    main() 