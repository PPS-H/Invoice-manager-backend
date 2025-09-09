# Text-Based Invoice Processing

## Overview

The invoice management system now supports processing invoices from email content even when there are no PDF attachments. This feature uses AI-powered analysis (Google Gemini) combined with fallback regex patterns to extract invoice information from text-based emails.

## Features

### 1. AI-Powered Extraction
- **Gemini AI Integration**: Uses Google's Gemini 2.5-flash model to intelligently parse email content
- **Smart Recognition**: Identifies vendor names, amounts, dates, invoice numbers, and other key fields
- **Context Understanding**: Analyzes email subject and body together for better accuracy

### 2. Fallback Processing
- **Regex Patterns**: Comprehensive patterns for extracting invoice data when AI fails
- **Vendor Detection**: Recognizes common vendor names and patterns
- **Amount Extraction**: Multiple currency and amount pattern recognition
- **Date Parsing**: Flexible date format handling

### 3. Comprehensive Coverage
- **Payment Confirmations**: "Thank you for your payment" emails
- **Subscription Renewals**: Monthly/annual billing notifications
- **Receipt Emails**: Transaction confirmations and receipts
- **Billing Statements**: Account summaries and billing notifications
- **Seat Upgrades**: Team member additions and upgrades

## How It Works

### 1. Email Classification
The system automatically classifies emails into different types:
- `PDF_ATTACHMENT`: Emails with PDF attachments
- `INVOICE_LINK`: Emails with download links
- `EMAIL_CONTENT`: Text-based invoices (no PDF)
- `UNKNOWN`: Non-invoice emails

### 2. Processing Flow
```
Email Received → Classify Type → AI Processing → Fallback Extraction → Save Invoice
     ↓              ↓              ↓              ↓              ↓
  Parse Email   Determine if    Gemini AI     Regex-based    Store in
  Content       Text-based      Analysis      Extraction     Database
```

### 3. AI Processing
- Sends email content to Gemini AI
- Extracts structured invoice data
- Returns JSON with vendor, amount, dates, etc.
- Handles various email formats and languages

### 4. Fallback Extraction
If AI processing fails, the system uses regex patterns to:
- Extract vendor names from common patterns
- Identify monetary amounts and currency
- Parse invoice numbers and dates
- Determine invoice categories

## API Endpoints

### Process Text-Based Invoice
```http
POST /api/invoices/process-text-invoice
```

**Request Body:**
```json
{
  "subject": "Payment Confirmation - GitHub",
  "body": "Thank you for your payment of $12.00 USD...",
  "sender": "billing@github.com",
  "date": "2025-01-15T10:30:00Z",
  "message_id": "msg-123",
  "email_account_id": "acc-456"
}
```

**Response:**
```json
{
  "success": true,
  "message": "Text-based invoice processed successfully",
  "invoice": {
    "id": "inv-789",
    "vendor_name": "GitHub",
    "invoice_number": "AUTO-2025-01-15-12.00",
    "total_amount": 12.00,
    "currency": "USD",
    "invoice_date": "2025-01-15T00:00:00Z",
    "status": "pending"
  }
}
```

## Frontend Component

### TextInvoiceProcessor
A dedicated React component for manually processing text-based invoices:

- **Form Interface**: Input fields for email content
- **Real-time Processing**: Immediate AI analysis
- **Results Display**: Shows extracted invoice information
- **Error Handling**: Graceful fallback and error messages

**Access**: Navigate to `/text-invoice-processor` in the application

## Configuration

### Environment Variables
```bash
# Required for AI processing
GEMINI_API_KEY=your_gemini_api_key_here

# Optional: Customize processing
GEMINI_MODEL=gemini-2.5-flash
GEMINI_MAX_TOKENS=8192
```

### Gemini AI Setup
1. Get API key from [Google AI Studio](https://aistudio.google.com/app/apikey)
2. Set `GEMINI_API_KEY` environment variable
3. Restart the application

## Usage Examples

### 1. Automatic Email Processing
When scanning emails, the system automatically:
- Detects text-based invoices
- Processes them with AI
- Creates invoice records
- Stores in the database

### 2. Manual Processing
Use the frontend component to:
- Paste email content
- Process specific emails
- Review extracted data
- Manually correct if needed

### 3. API Integration
Integrate with external systems:
- Send email content via API
- Receive structured invoice data
- Handle processing errors gracefully

## Supported Email Types

### Payment Confirmations
- GitHub subscription renewals
- Figma payment confirmations
- Stripe transaction receipts
- PayPal payment notifications

### Billing Notifications
- Datadog monthly invoices
- AWS billing summaries
- Google Cloud charges
- Microsoft 365 subscriptions

### Subscription Updates
- Slack team upgrades
- Notion workspace expansions
- Linear seat additions
- Vercel plan changes

## Error Handling

### AI Processing Failures
- Automatic fallback to regex extraction
- Detailed error logging
- Graceful degradation
- User-friendly error messages

### Data Validation
- Required field checking
- Amount format validation
- Date parsing fallbacks
- Vendor name normalization

## Performance Considerations

### AI API Limits
- Rate limiting (0.5s between calls)
- Token usage optimization
- Response caching
- Batch processing support

### Fallback Efficiency
- Fast regex matching
- Minimal CPU usage
- Efficient pattern matching
- Quick response times

## Testing

### Test Script
Run the test script to verify functionality:
```bash
cd backend
python test_text_invoice_processing.py
```

### Test Cases
- Various email formats
- Different vendor types
- Multiple currency formats
- Edge cases and errors

## Troubleshooting

### Common Issues

1. **AI Processing Fails**
   - Check `GEMINI_API_KEY` is set
   - Verify API key is valid
   - Check network connectivity
   - Review API rate limits

2. **Fallback Extraction Issues**
   - Verify email content format
   - Check regex patterns
   - Review vendor detection
   - Validate amount extraction

3. **Database Errors**
   - Check MongoDB connection
   - Verify user authentication
   - Review data validation
   - Check required fields

### Debug Logging
Enable detailed logging to troubleshoot:
```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

## Future Enhancements

### Planned Features
- **Multi-language Support**: Process invoices in different languages
- **Template Recognition**: Learn from user corrections
- **Batch Processing**: Handle multiple emails simultaneously
- **Advanced Validation**: Machine learning-based data validation

### Integration Opportunities
- **Email Providers**: Direct integration with Gmail, Outlook
- **Accounting Software**: QuickBooks, Xero, FreshBooks
- **Expense Management**: Expensify, Concur, Ramp
- **ERP Systems**: SAP, Oracle, Microsoft Dynamics

## Support

For issues or questions:
1. Check the logs for error details
2. Verify configuration settings
3. Test with the provided test script
4. Review the API documentation
5. Contact the development team

---

**Note**: This feature requires a valid Gemini API key for optimal performance. The system will fall back to regex-based extraction if AI processing is unavailable. 