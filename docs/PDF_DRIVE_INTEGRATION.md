# PDF Drive Integration

## Overview

This document describes the updated Google Drive integration that now properly handles PDF files instead of creating text files.

## Changes Made

### 1. **PDF Files Only to Drive**
- **Before**: All invoices were saved as text files in Google Drive
- **After**: Only invoices with PDF attachments are saved to Drive
- **Text invoices**: No files are saved to Drive (only stored locally)

### 2. **Enhanced File Handling**
- PDF files are read from local storage and uploaded to Drive
- File type validation ensures only PDFs are processed
- Proper MIME type handling (`application/pdf`)

### 3. **Improved Logic Flow**
- Drive storage is skipped for text-based invoices
- PDF invoices get both local and Drive storage
- Better error handling and logging

## How It Works Now

### **Invoices WITH PDF Attachments**
1. PDF is saved locally in `uploads/invoices/{user_id}/{vendor_name}/`
2. PDF is uploaded to Google Drive in same folder structure
3. Drive file ID is stored in invoice record

### **Invoices WITHOUT PDF Attachments (Text-based)**
1. Invoice data is processed and stored in database
2. **No files are saved to Google Drive**
3. Only local database storage

## Code Changes

### **DriveService.save_scanned_email_invoice()**
- Added `local_file_info` parameter
- Checks for local file existence before Drive upload
- Validates file type (PDF only)
- Uploads actual PDF content instead of text

### **InvoiceProcessor Integration**
- Passes `local_file_info` to Drive service
- Enhanced logging for Drive operations
- Clear indication of what's being saved where

## File Structure

### **Local Storage (Unchanged)**
```
uploads/invoices/{user_id}/{vendor_name}/
├── invoice1.pdf
├── invoice2.pdf
└── invoice3.pdf
```

### **Google Drive Storage (Updated)**
```
uploads/invoices/{user_id}/{vendor_name}/
├── invoice1.pdf  ← Actual PDF file
├── invoice2.pdf  ← Actual PDF file
└── invoice3.pdf  ← Actual PDF file
```

**Note**: No more `.txt` files in Drive

## Benefits

1. **Storage Efficiency**: No unnecessary text files in Drive
2. **File Consistency**: Drive contains actual invoice PDFs
3. **Better Organization**: Clear separation between PDF and text invoices
4. **Preserved Functionality**: All existing features continue to work

## Testing

### **Run the Test Script**
```bash
cd backend
python test_pdf_drive_integration.py
```

This will verify:
- Text invoices are NOT saved to Drive
- PDF invoices ARE saved to Drive
- All methods are available
- Environment is properly configured

## Configuration

### **Required Environment Variables**
```bash
GOOGLE_CLIENT_ID=your_client_id
GOOGLE_CLIENT_SECRET=your_client_secret
DEEPSEEK_API_KEY=your_deepseek_api_key
```

### **OAuth Scopes Required**
```
https://www.googleapis.com/auth/drive.file
https://www.googleapis.com/auth/gmail.readonly
https://www.googleapis.com/auth/userinfo.email
https://www.googleapis.com/auth/userinfo.profile
```

## Error Handling

### **Common Scenarios**
1. **No PDF File**: Drive storage is skipped (expected behavior)
2. **File Not Found**: Drive storage is skipped with warning
3. **Authentication Failed**: Drive storage fails, local storage continues
4. **Upload Failed**: Drive storage fails, local storage continues

### **Log Messages**
- `📝 No local file found - skipping Drive storage for text-based invoice`
- `📄 File is not a PDF - skipping Drive storage`
- `✅ Successfully uploaded PDF to Drive!`
- `📝 Text-based invoice - no PDF to save to Drive`

## Migration Notes

### **Existing Invoices**
- Text-based invoices: No changes needed
- PDF invoices: Will be re-uploaded to Drive on next scan
- Database records: No changes required

### **Drive Cleanup**
- Old text files can be manually removed from Drive
- New PDF files will be uploaded to correct locations
- Folder structure remains the same

## Troubleshooting

### **Drive Storage Not Working**
1. Check OAuth tokens are valid
2. Verify Drive API is enabled in Google Cloud Console
3. Check file permissions and accessibility
4. Review application logs for specific errors

### **PDF Files Not Uploading**
1. Verify local file exists and is accessible
2. Check file is actually a PDF
3. Ensure Drive authentication is successful
4. Review folder creation permissions

## Future Enhancements

1. **File Type Support**: Extend to other file types (images, documents)
2. **Batch Uploads**: Process multiple files simultaneously
3. **File Compression**: Optimize storage usage
4. **Version Control**: Track file changes and updates

## Support

For issues or questions:
1. Check application logs for detailed error messages
2. Run the test script to verify configuration
3. Review this documentation for common solutions
4. Check Google Cloud Console for API quotas and permissions 