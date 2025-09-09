# Public Invitation Flow

## Overview

The Public Invitation Flow solves the problem of inviting users to different email addresses and opening invitation links in different browsers. This new system allows anyone to accept invitations without requiring authentication first, then guides them through the OAuth process to connect their email account.

## Problem Solved

### **Previous Issue:**
- Users had to be logged in to accept invitations
- Invitation links only worked in the same browser where the user was authenticated
- OAuth flow couldn't complete for invited users in different browsers

### **New Solution:**
- **Public invitation acceptance**: Anyone can accept invitations without login
- **OAuth-first approach**: Users log in after accepting the invitation
- **Cross-browser compatibility**: Works in any browser or device
- **Seamless integration**: Proper account linking after OAuth completion

## How It Works

### **1. Invitation Creation (Requires Authentication)**
```
User (logged in) → Email Accounts → "Invite User to Add Email"
↓
System generates secure token and sends invitation email
↓
Invitation stored in database with status: "active"
```

### **2. Public Invitation Acceptance (No Authentication Required)**
```
Invited user receives email → Clicks invitation link
↓
Opens invitation page in any browser
↓
Clicks "Accept Invitation" button
↓
System marks invitation as "ready_for_oauth"
↓
User sees login prompt
```

### **3. OAuth Flow and Account Linking**
```
User clicks "Log In with Google" → Google OAuth flow
↓
User authenticates with Google
↓
OAuth callback processes the invitation
↓
Email account linked to inviter's system
↓
User can now scan invoices from their connected account
```

## Technical Implementation

### **Backend Changes**

#### **New Public Endpoint**
```python
@router.post("/accept-public", response_model=AcceptInviteResponse)
async def accept_invite_public(accept_data: AcceptInviteRequest):
    """Accept an invite link publicly (no authentication required)"""
    # Allows anyone to accept invitations
    # Updates status to "ready_for_oauth"
```

#### **Enhanced OAuth Callback**
```python
# Check for public invites that are ready for OAuth
if not pending_invite:
    pending_invite = await mongodb.db["invites"].find_one({
        "invite_type": "add_email_account",
        "status": "ready_for_oauth",
        "invited_email": user_info["email"].lower()
    })
    
    # Mark as used by this user
    if pending_invite:
        await mongodb.db["invites"].update_one(
            {"_id": pending_invite["_id"]},
            {"$set": {"status": "used", "used_by_user_id": current_user.id}}
        )
```

#### **New Invitation Status**
```python
status: str = "active"  # active, used, expired, ready_for_oauth
```

### **Frontend Changes**

#### **Public Invitation Page**
- No authentication required to view invitation
- Accept button works without login
- Shows login prompt after acceptance
- Provides clear next steps

#### **Enhanced User Experience**
- Professional invitation interface
- Clear call-to-action buttons
- Login options (same tab or new tab)
- Progress indicators and success messages

## User Flow Examples

### **Scenario 1: Different Browser**
```
1. User A creates invitation for user@example.com
2. User B receives email on their phone
3. User B clicks link (opens in mobile browser)
4. User B accepts invitation (no login required)
5. User B sees "Log In with Google" button
6. User B completes OAuth flow
7. Email account linked to User A's system
```

### **Scenario 2: Different Device**
```
1. User A creates invitation for user@example.com
2. User B receives email on their laptop
3. User B clicks link (opens in laptop browser)
4. User B accepts invitation (no login required)
5. User B sees "Log In with Google" button
6. User B completes OAuth flow
7. Email account linked to User A's system
```

### **Scenario 3: Incognito/Private Browser**
```
1. User A creates invitation for user@example.com
2. User B receives email
3. User B clicks link in incognito mode
4. User B accepts invitation (no login required)
5. User B sees "Log In with Google" button
6. User B completes OAuth flow
7. Email account linked to User A's system
```

## Security Features

### **Token Security**
- Secure 32-character random tokens
- Expiration timestamps
- Single-use validation
- Status tracking

### **Access Control**
- Public invitation acceptance (limited scope)
- OAuth authentication required for account connection
- Proper user relationship management
- Audit trail for all actions

### **Data Protection**
- No sensitive data exposed in public endpoints
- Email validation during OAuth flow
- Secure account linking process
- Proper permission management

## API Endpoints

### **Public Endpoints (No Authentication Required)**
```
GET /api/invites/validate/{token}     # Validate invitation token
POST /api/invites/accept-public        # Accept invitation publicly
```

### **Protected Endpoints (Authentication Required)**
```
POST /api/invites/accept              # Accept invitation (authenticated)
POST /api/email-accounts/oauth/gmail/callback  # OAuth callback
```

## Database Schema Updates

### **Invitation Status Flow**
```
active → ready_for_oauth → used
  ↓           ↓          ↓
Created   Accepted    Connected
```

### **New Fields**
```python
# Additional fields returned by validation
"inviter_user_id": str,    # ID of user who sent invitation
"invite_id": str,          # Invitation ID for tracking
```

## Testing

### **Run Test Script**
```bash
cd backend
python test_public_invitation_flow.py
```

### **Manual Testing Steps**
1. **Create Invitation**
   - Log in to system
   - Go to Email Accounts
   - Create invitation for test email

2. **Test Public Acceptance**
   - Open invitation link in different browser
   - Accept invitation without login
   - Verify status updates to "ready_for_oauth"

3. **Test OAuth Flow**
   - Click "Log In with Google"
   - Complete OAuth authentication
   - Verify email account connection

4. **Verify Integration**
   - Check email account appears in system
   - Test invoice scanning functionality
   - Verify Google Drive integration

## Benefits

### **For Inviters**
- **Broader reach**: Can invite users regardless of their current authentication status
- **Better user experience**: Invited users can accept immediately
- **Higher acceptance rates**: No barriers to invitation acceptance

### **For Invited Users**
- **Immediate access**: Can accept invitations without creating accounts first
- **Flexible access**: Works on any device or browser
- **Clear process**: Step-by-step guidance through the setup

### **For System Administrators**
- **Simplified workflow**: Clear separation of concerns
- **Better tracking**: Enhanced invitation status monitoring
- **Improved security**: Proper authentication flow

## Troubleshooting

### **Common Issues**

#### **Invitation Not Found**
- Check invitation token validity
- Verify invitation hasn't expired
- Check database for invitation status

#### **OAuth Flow Fails**
- Verify Google Cloud Console configuration
- Check OAuth redirect URIs
- Ensure proper scopes are configured

#### **Account Not Linked**
- Check invitation status progression
- Verify email address matches
- Review OAuth callback logs

### **Debug Steps**
1. Check invitation validation endpoint
2. Verify public acceptance works
3. Monitor OAuth callback process
4. Check database status updates
5. Review user account linking

## Future Enhancements

### **Planned Features**
- **Bulk invitations**: Send multiple invitations at once
- **Invitation templates**: Customizable email content
- **Advanced expiration**: Configurable expiration options
- **Invitation analytics**: Track acceptance rates and usage

### **Potential Improvements**
- **Multi-language support**: International invitation support
- **Custom branding**: Company-specific invitation styling
- **Advanced security**: Additional verification methods
- **Integration options**: Connect with external user management systems

## Conclusion

The Public Invitation Flow provides a robust, user-friendly solution for inviting users to connect their email accounts. By separating invitation acceptance from authentication, the system now works seamlessly across different browsers, devices, and user scenarios while maintaining security and proper account management.

This enhancement ensures that the invitation system is accessible to all users while maintaining the integrity of the OAuth flow and account linking process. 