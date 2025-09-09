# Google Drive Integration

## Overview

The invoice management system now integrates with Google Drive to automatically save scanned email invoices with the same folder structure as your local uploads folder. This ensures all invoices are backed up to the cloud and accessible from anywhere.

## Features

### 1. **Automatic Drive Storage**
- **Seamless Integration**: Automatically saves invoices to Google Drive during email scanning
- **Same Folder Structure**: Mirrors your local `uploads/invoices/{user_id}/{vendor_name}/` structure
- **Real-time Sync**: Invoices are saved to Drive as soon as they're processed

### 2. **Folder Organization**
```
Google Drive/
├── uploads/
│   └── invoices/
│       └── {user_id}/
│           ├── GitHub_Inc/
│           │   ├── GitHub_Pro_Subscription_20250115_103000.txt
│           │   └── GitHub_Team_Upgrade_20250116_143000.txt
│           ├── Datadog_Inc/
│           │   ├── Datadog_Monthly_Billing_20250115_090000.txt
│           │   └── Datadog_Invoice_DD123456_20250115_090000.txt
│           └── Figma/
│               └── Figma_Payment_Confirmation_20250115_084500.txt
```

### 3. **File Format**
- **Text Files**: Email content formatted with extracted invoice data
- **Rich Metadata**: Includes email details, invoice information, and processing metadata
- **Searchable**: Full-text searchable in Google Drive

## How It Works

### 1. **Email Processing Flow**
```
Email Scanned → Invoice Extracted → Save to Database → Save to Google Drive
      ↓              ↓                ↓                ↓
   Parse Email   AI Analysis    Store Invoice    Create Drive File
   Content      (Gemini)       Record          (uploads/invoices/...)
```

### 2. **Drive Storage Process**
1. **Authentication**: Uses email account's OAuth tokens for Drive access
2. **Folder Creation**: Automatically creates folder structure if it doesn't exist
3. **File Generation**: Creates formatted text file with invoice data
4. **Upload**: Saves file to appropriate vendor folder
5. **Metadata Update**: Updates invoice record with Drive file information

### 3. **File Content Structure**
```
================================================================================
SCANNED EMAIL INVOICE
================================================================================

EMAIL METADATA:
Subject: Payment Confirmation - GitHub Pro Subscription
Sender: billing@github.com
Date: 2025-01-15T10:30:00Z
Message ID: test-email-123

EXTRACTED INVOICE DATA:
Vendor: GitHub_Inc
Invoice Number: GH-12345678
Invoice Date: 2025-01-15
Due Date: N/A
Amount: 12.0
Tax Amount: 0.0
Total Amount: 12.0
Currency: USD
Category: software
Confidence Score: 0.95

EMAIL CONTENT:
----------------------------------------
Hi there,

Thank you for your payment of $12.00 USD for your GitHub Pro subscription.
...

PROCESSING METADATA:
Processed At: 2025-01-15T10:30:00.123456
Source: Email Scanner
Processing Method: AI (Gemini)
================================================================================
```

## Configuration

### 1. **Environment Variables**
```bash
# Required for Google OAuth
GOOGLE_CLIENT_ID=your_google_client_id
GOOGLE_CLIENT_SECRET=your_google_client_secret

# Optional: Customize Drive behavior
GOOGLE_DRIVE_SCOPES=https://www.googleapis.com/auth/drive.file
```

### 2. **Google OAuth Setup**
1. **Create Project**: Go to [Google Cloud Console](https://console.cloud.google.com/)
2. **Enable APIs**: Enable Google Drive API and Gmail API
3. **Create Credentials**: Create OAuth 2.0 client credentials
4. **Set Scopes**: Ensure `https://www.googleapis.com/auth/drive.file` scope is included
5. **Configure Redirects**: Add your application's redirect URIs

### 3. **Required Permissions**
- **Drive Access**: `https://www.googleapis.com/auth/drive.file`
- **File Creation**: Create and organize folders and files
- **User Data**: Access to user's Drive for organization

## API Integration

### 1. **Automatic Storage**
When processing invoices via email scanning, Drive storage happens automatically:
- No additional API calls needed
- Uses existing email account credentials
- Handles errors gracefully with fallback to local storage

### 2. **Manual Storage**
For manual invoice processing, use the text invoice processor:
```http
POST /api/invoices/process-text-invoice
```

The system will automatically save to both database and Google Drive.

### 3. **Drive Information in Invoice Records**
Invoice records now include Drive metadata:
```json
{
  "id": "inv_123",
  "vendor_name": "GitHub_Inc",
  "total_amount": 12.00,
  "drive_file_id": "1ABC123DEF456",
  "drive_file_name": "GitHub_Pro_Subscription_20250115_103000.txt",
  "drive_folder_id": "1XYZ789GHI012",
  "local_file_path": "/uploads/invoices/user123/GitHub_Inc/file.pdf"
}
```

## Folder Structure Management

### 1. **Automatic Creation**
- **uploads/**: Main uploads folder
- **invoices/**: Invoice-specific subfolder
- **{user_id}/**: User-specific folder
- **{vendor_name}/**: Vendor-specific subfolder

### 2. **Vendor Naming**
- **Sanitized Names**: Special characters removed for Drive compatibility
- **Consistent Format**: Matches local folder naming conventions
- **Hierarchical Organization**: Easy to navigate and search

### 3. **File Naming Convention**
```
{vendor_name}_{email_subject}_{timestamp}.txt
```
Example: `GitHub_Inc_Payment_Confirmation_20250115_103000.txt`

## Error Handling

### 1. **Authentication Failures**
- **Token Expiry**: Automatic refresh using refresh tokens
- **Invalid Credentials**: Graceful fallback to local storage
- **Scope Issues**: Clear error logging for permission problems

### 2. **Drive API Errors**
- **Rate Limiting**: Built-in delays between API calls
- **Network Issues**: Retry logic with exponential backoff
- **Quota Exceeded**: User notification and fallback storage

### 3. **Fallback Strategy**
- **Primary**: Google Drive storage
- **Secondary**: Local file system storage
- **Tertiary**: Database-only storage with metadata

## Performance Considerations

### 1. **API Optimization**
- **Batch Operations**: Group folder creation operations
- **Caching**: Cache folder IDs to reduce API calls
- **Rate Limiting**: Respect Google's API quotas

### 2. **Storage Efficiency**
- **Text Compression**: Efficient text file storage
- **Metadata Optimization**: Minimal file overhead
- **Cleanup**: Optional cleanup of old test files

### 3. **User Experience**
- **Async Processing**: Non-blocking Drive operations
- **Progress Indicators**: Real-time upload status
- **Error Recovery**: Automatic retry on failures

## Testing

### 1. **Test Script**
Run the comprehensive test script:
```bash
cd backend
python test_drive_integration.py
```

### 2. **Test Coverage**
- **Folder Structure**: Creation and organization
- **File Upload**: Text file storage and metadata
- **Error Handling**: Authentication and API failures
- **Integration**: End-to-end invoice processing

### 3. **Manual Testing**
- **Email Scanning**: Process real emails with Drive storage
- **Folder Verification**: Check Drive folder structure
- **File Access**: Verify file content and metadata

## Monitoring and Logging

### 1. **Success Metrics**
- **Upload Success Rate**: Percentage of successful Drive saves
- **Folder Creation**: New folder structure creation
- **File Storage**: Total files stored in Drive

### 2. **Error Tracking**
- **Authentication Failures**: OAuth token issues
- **API Errors**: Drive API response errors
- **Storage Failures**: File upload problems

### 3. **Performance Metrics**
- **Upload Time**: Time to save files to Drive
- **API Response Time**: Drive API call performance
- **Storage Usage**: Drive space utilization

## Troubleshooting

### 1. **Common Issues**

#### **Authentication Problems**
```bash
# Check environment variables
echo $GOOGLE_CLIENT_ID
echo $GOOGLE_CLIENT_SECRET

# Verify OAuth scopes
# Ensure https://www.googleapis.com/auth/drive.file is included
```

#### **Folder Creation Failures**
```bash
# Check Drive API quotas
# Verify user has sufficient Drive space
# Check folder naming conflicts
```

#### **File Upload Issues**
```bash
# Verify file size limits
# Check Drive storage quota
# Review API rate limits
```

### 2. **Debug Logging**
Enable detailed logging:
```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

### 3. **Drive API Console**
- **Google Cloud Console**: Monitor API usage and quotas
- **Drive Web Interface**: Verify folder structure and files
- **OAuth Consent**: Check application permissions

## Security Considerations

### 1. **OAuth Security**
- **Limited Scope**: Only `drive.file` access (user's files only)
- **Token Management**: Secure storage and refresh of tokens
- **User Consent**: Clear permission requests

### 2. **Data Privacy**
- **User Isolation**: Each user's files are separate
- **No Cross-Access**: Users cannot access other users' files
- **Audit Trail**: Full logging of all Drive operations

### 3. **Compliance**
- **GDPR**: User data control and deletion
- **SOC 2**: Security and privacy controls
- **Industry Standards**: Best practices for cloud storage

## Future Enhancements

### 1. **Planned Features**
- **Multi-Cloud Support**: AWS S3, Azure Blob Storage
- **Advanced Search**: Full-text search across Drive files
- **Version Control**: File versioning and history
- **Collaboration**: Shared folder access for teams

### 2. **Integration Opportunities**
- **Google Workspace**: Integration with Docs, Sheets
- **Third-Party Apps**: Zapier, IFTTT automation
- **Accounting Software**: QuickBooks, Xero integration
- **Expense Management**: Expensify, Concur sync

### 3. **Advanced Analytics**
- **Storage Insights**: Drive usage analytics
- **Cost Optimization**: Storage cost analysis
- **Performance Metrics**: Upload/download performance
- **User Behavior**: Storage pattern analysis

## Support and Maintenance

### 1. **Regular Maintenance**
- **Token Refresh**: Monitor OAuth token expiration
- **Quota Monitoring**: Track API usage and limits
- **Storage Cleanup**: Remove old test files
- **Performance Review**: Monitor upload/download times

### 2. **User Support**
- **Setup Assistance**: Help with OAuth configuration
- **Troubleshooting**: Guide users through common issues
- **Training**: Educate users on Drive organization
- **Best Practices**: Share optimization tips

### 3. **System Health**
- **Health Checks**: Monitor Drive service availability
- **Error Alerts**: Notify administrators of failures
- **Performance Metrics**: Track system performance
- **Capacity Planning**: Plan for storage growth

---

**Note**: This integration requires valid Google OAuth credentials and proper API setup. The system gracefully falls back to local storage if Drive operations fail, ensuring invoice processing continues uninterrupted. 