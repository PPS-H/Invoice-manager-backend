# Drive Link Frontend Integration

## Overview

This document describes the integration of Google Drive links into the frontend, allowing users to view invoices directly from Drive using the eye icon.

## Changes Made

### 1. **Backend Changes**

#### **Invoice Model (`models/invoice.py`)**
- Added `drive_view_link: Optional[str]` field to store the Drive view link

#### **Invoice Schemas (`schemas/invoice.py`)**
- Added `drive_view_link` field to `InvoiceResponse` schema for API responses

#### **Invoice Processor (`services/invoice_processor.py`)**
- Modified invoice creation to store `drive_view_link` from Drive upload result
- Updated both PDF and text invoice processing flows

#### **Drive Service (`services/drive_service.py`)**
- Enhanced `save_scanned_email_invoice` method to return Drive view links
- Added file type validation (PDF only)
- Improved error handling and logging

### 2. **Frontend Changes**

#### **Invoices Component (`frontend/src/components/Invoices.tsx`)**
- Updated `handleViewInvoice` function to use Drive links
- Enhanced eye icon with visual indicators
- Added Drive availability badges
- Improved tooltips and user feedback

## How It Works

### **Backend Flow**
1. **Invoice Processing**: Invoice is processed and PDF uploaded to Drive
2. **Drive Link Storage**: Drive view link is stored in `drive_view_link` field
3. **Database Update**: Invoice record is updated with Drive information
4. **API Response**: Frontend receives invoice data including Drive link

### **Frontend Flow**
1. **Invoice Display**: Invoices are displayed with Drive availability indicators
2. **Eye Icon Click**: User clicks eye icon to view invoice
3. **Drive Link Check**: System checks if Drive link is available
4. **Link Opening**: Drive link opens in new tab if available

## Features

### **Visual Indicators**
- **Blue Eye Icon**: When Drive link is available
- **Gray Eye Icon**: When no Drive link is available
- **Blue Dot**: Small indicator on eye icon when Drive link exists
- **Drive Badge**: Blue "Drive" badge for invoices with Drive links

### **User Experience**
- **Tooltips**: Clear indication of what will happen when clicked
- **Fallback Messages**: Helpful messages when Drive links aren't available
- **New Tab Opening**: Drive links open in new tab for better UX
- **Responsive Design**: Works on all screen sizes

## Code Examples

### **Backend - Storing Drive Link**
```python
# In InvoiceProcessor
invoice_model = InvoiceModel(
    # ... other fields ...
    drive_view_link=drive_file_info.get('web_view_link') if drive_file_info else None,
    # ... other fields ...
)
```

### **Frontend - Using Drive Link**
```typescript
const handleViewInvoice = (invoice: any) => {
  if (invoice.drive_view_link) {
    // Open Drive link in new tab
    window.open(invoice.drive_view_link, '_blank');
  } else if (invoice.local_file_path) {
    // Fallback to local file
    alert('Invoice file is available locally but Drive link is not available.');
  } else {
    // No file available
    alert('No invoice file available for viewing.');
  }
};
```

### **Frontend - Visual Indicators**
```typescript
{/* Drive availability badge */}
{invoice.drive_view_link && (
  <span className="px-2 py-1 bg-blue-100 text-blue-800 border border-blue-200 rounded-md text-xs font-medium flex items-center gap-1">
    <svg className="w-3 h-3" fill="currentColor" viewBox="0 0 20 20">
      <path d="M3 4a1 1 0 011-1h12a1 1 0 011 1v2a1 1 0 01-1 1H4a1 1 0 01-1-1V4zM3 10a1 1 0 011-1h6a1 1 0 011 1v6a1 1 0 01-1 1H4a1 1 0 01-1-1v-6zM14 9a1 1 0 00-1 1v6a1 1 0 001 1h2a1 1 0 001-1v-6a1 1 0 00-1-1h-2z"/>
    </svg>
    Drive
  </span>
)}
```

## Database Schema

### **Invoice Collection Fields**
```json
{
  "_id": "ObjectId",
  "user_id": "string",
  "vendor_name": "string",
  "total_amount": "number",
  "drive_file_id": "string",      // Google Drive file ID
  "drive_file_name": "string",    // Google Drive file name
  "drive_folder_id": "string",    // Google Drive folder ID
  "drive_view_link": "string",    // Google Drive view link
  "local_file_path": "string",    // Local file path (if exists)
  "status": "string",
  "created_at": "datetime",
  "updated_at": "datetime"
}
```

## Testing

### **Run the Test Script**
```bash
cd backend
python test_drive_link_storage.py
```

This will verify:
- Drive links are stored in MongoDB
- Invoice schema includes required fields
- Frontend can access Drive link data
- All functionality works correctly

### **Manual Testing**
1. **Process Invoices**: Scan emails with PDF attachments
2. **Check Database**: Verify Drive links are stored
3. **Frontend Display**: Check eye icons and Drive badges
4. **Link Functionality**: Click eye icons to open Drive links

## Error Handling

### **Common Scenarios**
1. **No Drive Link**: Shows "No invoice file available" message
2. **Local File Only**: Shows "File available locally" message
3. **Drive Link Available**: Opens Drive link in new tab
4. **Invalid Link**: Graceful fallback with user feedback

### **User Messages**
- `"No invoice file available for viewing."`
- `"Invoice file is available locally but Drive link is not available."`
- `"View Invoice in Google Drive"` (tooltip)
- `"No invoice file available"` (tooltip)

## Benefits

1. **Seamless Integration**: Direct access to invoices in Drive
2. **Visual Clarity**: Clear indication of what's available
3. **User Experience**: One-click access to invoice files
4. **Fallback Support**: Graceful handling when Drive links aren't available
5. **Responsive Design**: Works on all devices and screen sizes

## Future Enhancements

1. **File Preview**: Inline preview of invoices
2. **Download Options**: Direct download from Drive
3. **Version Control**: Track file changes and updates
4. **Sharing**: Share invoice links with team members
5. **Offline Access**: Cache frequently accessed invoices

## Troubleshooting

### **Drive Links Not Working**
1. Check OAuth tokens are valid
2. Verify Drive API is enabled
3. Check invoice processing logs
4. Run the test script to identify issues

### **Frontend Issues**
1. Check browser console for errors
2. Verify API responses include Drive links
3. Check network requests to Drive
4. Test with different browsers

## Support

For issues or questions:
1. Check application logs for detailed error messages
2. Run the test script to verify configuration
3. Review this documentation for common solutions
4. Check Google Cloud Console for API quotas and permissions 