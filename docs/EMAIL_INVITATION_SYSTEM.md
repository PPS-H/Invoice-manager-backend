# Email Invitation System

## Overview

The Email Invitation System allows users to invite others to connect their email accounts to the invoice management system. This enables collaborative invoice processing where invited users can scan their emails for invoices, and the results are available to the inviting user.

## How It Works

### **1. Invitation Creation**
- User clicks "Invite User to Add Email" button in Email Accounts
- System generates secure invitation token
- Invitation email is sent to specified address
- Invitation stored in database with expiration

### **2. Invitation Acceptance**
- Invited user receives email with invitation link
- Clicks link to access invitation page
- Accepts invitation and proceeds to OAuth
- Connects their Gmail account via Google OAuth

### **3. Email Account Integration**
- Connected email account is linked to inviter's user ID
- Invited user can scan their emails for invoices
- All invoices are processed and stored in the system
- Google Drive integration works for invited accounts

### **4. Invoice Processing**
- Invited email accounts scan for invoices automatically
- PDFs are uploaded to the connected account's Google Drive
- Invoice data is extracted and stored in database
- All functionality remains consistent with regular accounts

## System Architecture

### **Backend Components**

#### **Email Service (`services/email_service.py`)**
- Handles SMTP email sending
- Generates HTML and text invitation emails
- Configurable SMTP settings
- Professional email templates

#### **Invites Route (`routes/invites.py`)**
- Creates invitation tokens
- Sends invitation emails
- Validates invitation tokens
- Handles invitation acceptance

#### **Email Accounts Route (`routes/email_accounts.py`)**
- OAuth callback for invited users
- Links email accounts to inviters
- Maintains proper user relationships
- Handles token refresh and management

### **Frontend Components**

#### **EmailAccountInviteButton (`components/EmailAccountInviteButton.tsx`)**
- Modal for creating invitations
- Email address input
- Expiration time selection
- Invitation URL generation

#### **EmailAccountInvite Page (`pages/EmailAccountInvite.tsx`)**
- Invitation acceptance interface
- OAuth flow initiation
- Security and privacy information
- Professional user experience

#### **EmailAccountCallback (`components/EmailAccountCallback.tsx`)**
- Handles OAuth callback
- Differentiates invited vs. regular users
- Appropriate redirects and messages
- Session management

## Configuration

### **Environment Variables**

#### **Required Variables**
```bash
# SMTP Configuration
SMTP_USERNAME=your-email@gmail.com
SMTP_PASSWORD=your-app-password
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587

# Application Configuration
FRONTEND_URL=http://localhost:5173
```

#### **Optional Variables**
```bash
# Email Configuration
FROM_EMAIL=noreply@yourdomain.com
APP_NAME=Invoice Manager
```

### **SMTP Setup**

#### **Gmail Setup**
1. Enable 2-factor authentication
2. Generate App Password
3. Use App Password as SMTP_PASSWORD
4. Ensure "Less secure app access" is disabled

#### **Other SMTP Providers**
- Update SMTP_SERVER and SMTP_PORT
- Use appropriate authentication method
- Test connection with email service

## Database Schema

### **Invites Collection**
```json
{
  "_id": "ObjectId",
  "inviter_user_id": "string",           // User who sent invitation
  "invite_type": "add_email_account",    // Type of invitation
  "invited_email": "string",             // Email address invited
  "invite_token": "string",              // Secure invitation token
  "status": "active|used|expired",       // Invitation status
  "expires_at": "datetime",              // Expiration timestamp
  "used_at": "datetime",                 // When accepted
  "used_by_user_id": "string",          // User who accepted
  "added_email_account_id": "string",    // Connected email account ID
  "created_at": "datetime",
  "updated_at": "datetime"
}
```

### **Email Accounts Collection**
```json
{
  "_id": "ObjectId",
  "user_id": "string",                   // Owner (inviter) user ID
  "email": "string",                     // Connected email address
  "provider": "gmail",                   // Email provider
  "display_name": "string",              // Display name
  "access_token": "string",              // OAuth access token
  "refresh_token": "string",             // OAuth refresh token
  "token_expires_at": "datetime",        // Token expiration
  "status": "connected",                 // Account status
  "created_at": "datetime",
  "updated_at": "datetime"
}
```

## User Flow

### **For Inviters**

1. **Navigate to Email Accounts**
   - Go to Email Accounts sidebar tab
   - Click "Invite User to Add Email" button

2. **Create Invitation**
   - Enter invited user's email address
   - Set expiration time (default: 24 hours)
   - Click "Send Invitation"

3. **Invitation Sent**
   - System generates secure token
   - Email sent to invited address
   - Invitation stored in database

4. **Monitor Invitations**
   - View invitation status
   - Track accepted invitations
   - Manage active invitations

### **For Invited Users**

1. **Receive Invitation Email**
   - Professional HTML email
   - Clear call-to-action button
   - Security and privacy information

2. **Accept Invitation**
   - Click invitation link
   - Review invitation details
   - Accept invitation terms

3. **Connect Email Account**
   - Initiate Google OAuth flow
   - Grant necessary permissions
   - Complete account connection

4. **Start Using System**
   - Email account now connected
   - Automatic invoice scanning
   - Google Drive integration

## Security Features

### **Token Security**
- 32-character secure random tokens
- URL-safe encoding
- Expiration timestamps
- Single-use validation

### **OAuth Security**
- Google OAuth 2.0 flow
- No credential storage
- Secure token management
- Proper scope limitations

### **Access Control**
- Invited users can only access their own emails
- Inviters maintain control over connected accounts
- Proper user ID relationships
- Audit trail for all actions

## Email Templates

### **HTML Template Features**
- Professional design
- Responsive layout
- Clear call-to-action
- Security information
- Branding customization

### **Text Template Features**
- Plain text fallback
- Clear instructions
- Important information
- Professional formatting

## Testing

### **Run Test Script**
```bash
cd backend
python test_email_invitation_system.py
```

### **Manual Testing Steps**
1. **Create Invitation**
   - Use Email Accounts interface
   - Send invitation to test email

2. **Accept Invitation**
   - Check email for invitation
   - Click invitation link
   - Complete OAuth flow

3. **Verify Integration**
   - Check email account connection
   - Test invoice scanning
   - Verify Drive integration

### **Test Scenarios**
- Valid invitation acceptance
- Expired invitation handling
- Invalid token handling
- OAuth flow completion
- Email account linking
- Invoice processing

## Troubleshooting

### **Common Issues**

#### **SMTP Connection Failed**
- Check SMTP credentials
- Verify 2FA and App Passwords
- Check firewall settings
- Test SMTP connection

#### **Invitation Not Received**
- Check spam/junk folders
- Verify email address
- Check SMTP configuration
- Review server logs

#### **OAuth Flow Issues**
- Check Google Cloud Console
- Verify OAuth credentials
- Check redirect URIs
- Review OAuth scopes

#### **Email Account Not Linked**
- Check invitation status
- Verify user relationships
- Review database records
- Check OAuth callback

### **Debug Steps**
1. Check application logs
2. Verify environment variables
3. Test SMTP connection
4. Check database records
5. Review OAuth flow
6. Test invitation acceptance

## Monitoring

### **Key Metrics**
- Invitations sent
- Invitations accepted
- Email accounts connected
- OAuth success rate
- Email delivery rate

### **Log Analysis**
- Invitation creation logs
- Email sending logs
- OAuth flow logs
- Account linking logs
- Error tracking

## Future Enhancements

### **Planned Features**
- Bulk invitation sending
- Invitation templates
- Advanced expiration options
- Invitation analytics
- User role management

### **Potential Improvements**
- Multi-language support
- Custom email templates
- Advanced security features
- Integration with user management
- Automated follow-ups

## Support

### **Getting Help**
1. Check this documentation
2. Run test scripts
3. Review application logs
4. Check environment configuration
5. Verify OAuth setup

### **Common Solutions**
- Ensure all environment variables are set
- Verify SMTP credentials are correct
- Check Google Cloud Console configuration
- Review OAuth redirect URIs
- Test with simple email addresses first

## Conclusion

The Email Invitation System provides a secure, professional way to expand invoice processing capabilities by allowing users to invite others to connect their email accounts. The system maintains security while providing a seamless user experience for both inviters and invited users.

All existing functionality remains intact, and the system integrates seamlessly with the existing invoice processing, Google Drive integration, and user management features. 