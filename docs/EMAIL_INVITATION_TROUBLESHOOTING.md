# Email Invitation Troubleshooting Guide

## Common Issues and Solutions

### **1. Import Error: "No module named 'email.mime.html'"**

**Problem**: This error occurs when there's an incorrect import statement.

**Solution**: ✅ **FIXED** - The import has been corrected to use the proper Python email modules.

**Root Cause**: The `email.mime.html` module doesn't exist. HTML content should use `email.mime.text.MIMEText` with 'html' subtype.

---

### **2. SMTP Connection Failed**

**Problem**: Cannot connect to SMTP server or authentication fails.

**Solutions**:

#### **Check Environment Variables**
```bash
# Ensure these are set in your .env file
SMTP_USERNAME=your-email@gmail.com
SMTP_PASSWORD=your-app-password
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
FRONTEND_URL=http://localhost:5173
```

#### **Gmail Setup**
1. **Enable 2-Factor Authentication**
   - Go to Google Account settings
   - Security → 2-Step Verification → Turn on

2. **Generate App Password**
   - Security → App passwords
   - Select "Mail" and your device
   - Use the generated 16-character password

3. **Use App Password**
   ```bash
   SMTP_PASSWORD=abcd efgh ijkl mnop  # Remove spaces
   ```

#### **Test SMTP Connection**
```bash
cd backend
python test_email_service.py
```

---

### **3. 403 Forbidden Error on Invite Acceptance**

**Problem**: Users get "403 Forbidden" when trying to accept email account invitations.

**Solution**: ✅ **FIXED** - The email validation logic has been updated to allow any logged-in user to accept invites.

**Root Cause**: The system was checking if the logged-in user's email matched the invited email, but this created a chicken-and-egg problem.

**New Logic**: 
- Users can accept invites for any email address
- Email validation happens during OAuth when the actual account is connected
- This allows the invitation flow to work properly

---

### **4. Invitation Email Not Received**

**Problem**: Invitation emails are not being delivered.

**Solutions**:

#### **Check Spam/Junk Folders**
- Gmail: Check Spam folder
- Outlook: Check Junk folder
- Other providers: Check spam/junk folders

#### **Verify Email Address**
- Ensure the email address is correct
- Check for typos or extra spaces
- Verify the domain is valid

#### **Check SMTP Configuration**
```bash
# Test SMTP connection
cd backend
python test_email_service.py
```

#### **Review Server Logs**
- Check backend logs for email sending errors
- Look for SMTP authentication failures
- Verify email service is being called

---

### **5. OAuth Flow Not Working for Invited Users**

**Problem**: Invited users cannot complete the OAuth flow.

**Solutions**:

#### **Check OAuth Configuration**
- Verify Google Cloud Console settings
- Check OAuth redirect URIs
- Ensure OAuth credentials are correct

#### **Verify Invitation Status**
- Check if invitation was accepted
- Verify invitation is not expired
- Check database for proper invite status

#### **Check User Authentication**
- Ensure invited user is logged in
- Verify JWT token is valid
- Check user permissions

---

## **Testing Steps**

### **1. Test Email Service**
```bash
cd backend
python test_email_service.py
```

This will test:
- Email service imports
- Content generation
- SMTP connection (if configured)

### **2. Test Full Invitation Flow**
1. **Create Invitation**
   - Go to Email Accounts
   - Click "Invite User to Add Email"
   - Enter test email address
   - Send invitation

2. **Check Backend Logs**
   - Look for email sending logs
   - Verify invitation creation
   - Check for any errors

3. **Accept Invitation**
   - Check email for invitation
   - Click invitation link
   - Complete OAuth flow

4. **Verify Integration**
   - Check email account connection
   - Test invoice scanning
   - Verify Drive integration

---

## **Debug Commands**

### **Check Environment Variables**
```bash
# In your backend directory
grep -E "SMTP_|FRONTEND_" .env
```

### **Test SMTP Manually**
```bash
# Test SMTP connection
python -c "
import smtplib
server = smtplib.SMTP('smtp.gmail.com', 587)
server.starttls()
server.login('your-email@gmail.com', 'your-app-password')
print('SMTP connection successful')
server.quit()
"
```

### **Check Database**
```bash
# Check invitations collection
python -c "
from core.database import connect_to_mongo, mongodb
import asyncio

async def check_invites():
    await connect_to_mongo()
    invites = await mongodb.db['invites'].find({}).to_list(length=10)
    print(f'Found {len(invites)} invitations')
    for invite in invites:
        print(f'- {invite.get(\"invited_email\")} ({invite.get(\"status\")})')

asyncio.run(check_invites())
"
```

---

## **Common Error Messages**

### **"SMTP not configured"**
- Set SMTP_USERNAME and SMTP_PASSWORD environment variables
- Check .env file configuration

### **"SMTP Authentication failed"**
- Verify 2FA is enabled
- Use App Password, not regular password
- Check username format (email address)

### **"Connection refused"**
- Check firewall settings
- Verify SMTP server and port
- Test network connectivity

### **"Invalid invite link"**
- Check invitation token validity
- Verify invitation hasn't expired
- Check database for invite status

---

## **Environment Variable Reference**

### **Required Variables**
```bash
# SMTP Configuration
SMTP_USERNAME=your-email@gmail.com
SMTP_PASSWORD=your-app-password
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587

# Application Configuration
FRONTEND_URL=http://localhost:5173
```

### **Optional Variables**
```bash
# Email Configuration
FROM_EMAIL=noreply@yourdomain.com
APP_NAME=Invoice Manager
```

---

## **Getting Help**

### **1. Check Logs**
- Backend application logs
- SMTP connection logs
- Database operation logs

### **2. Run Tests**
- Email service tests
- Invitation system tests
- OAuth integration tests

### **3. Verify Configuration**
- Environment variables
- SMTP settings
- OAuth credentials
- Database connection

### **4. Common Solutions**
- Restart backend service
- Check environment file
- Verify SMTP credentials
- Test OAuth flow manually

---

## **Success Indicators**

When everything is working correctly, you should see:

1. **Invitation Creation**
   ```
   ✅ Invitation email sent successfully to user@example.com
   ```

2. **Email Delivery**
   - Invitation email received in inbox
   - Professional HTML formatting
   - Clear call-to-action button

3. **Invitation Acceptance**
   - User can click invitation link
   - OAuth flow completes successfully
   - Email account gets connected

4. **System Integration**
   - Connected account appears in Email Accounts
   - Invoice scanning works
   - Google Drive integration functions

---

## **Next Steps After Fixing Issues**

1. **Test Email Service**
   - Run `python test_email_service.py`
   - Verify SMTP connection works

2. **Test Invitation Flow**
   - Create test invitation
   - Check email delivery
   - Test invitation acceptance

3. **Verify Integration**
   - Connect email account
   - Test invoice scanning
   - Check Drive integration

4. **Monitor System**
   - Watch backend logs
   - Check for errors
   - Verify user experience 