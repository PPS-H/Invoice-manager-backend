# Invitation OAuth Fix

## Problem Description

After accepting an invitation and completing OAuth, users were getting a popup with the text "User not authenticated. Please log in first." This prevented the email account from being properly linked to the inviter's system.

## Root Cause Analysis

### **Issue 1: OAuth Callback Authentication Check**
- The OAuth callback endpoint required full user authentication
- Invited users completing OAuth might not have valid sessions
- This caused the "User not authenticated" error

### **Issue 2: Email Account Linking Logic**
- The system wasn't properly finding and processing public invitations
- Email accounts weren't being linked to the correct inviter
- Ownership relationships weren't being established correctly

### **Issue 3: Email Accounts Listing**
- The Email Accounts tab only showed accounts owned by the current user
- Invited accounts weren't visible to the inviter
- No distinction between owned and invited accounts

## Solutions Implemented

### **Fix 1: Enhanced OAuth Callback Processing**

#### **Improved Invitation Detection**
```python
# Check for public invites that are ready for OAuth
if not pending_invite:
    pending_invite = await mongodb.db["invites"].find_one({
        "invite_type": "add_email_account",
        "status": "ready_for_oauth",
        "invited_email": user_info["email"].lower()
    })
    
    # If we found a public invite, mark it as used by this user
    if pending_invite:
        await mongodb.db["invites"].update_one(
            {"_id": pending_invite["_id"]},
            {
                "$set": {
                    "status": "used",
                    "used_at": datetime.utcnow(),
                    "used_by_user_id": current_user.id
                }
            }
        )
```

#### **Enhanced Logging**
- Added detailed logging for invitation processing
- Track invitation status changes
- Monitor email account creation and linking

### **Fix 2: Proper Email Account Ownership**

#### **Correct User ID Assignment**
```python
# Determine the user_id for the email account
# If there's a pending invite, use the inviter's user_id
# Otherwise, use the current user's user_id
owner_user_id = current_user.id
if pending_invite:
    owner_user_id = pending_invite["inviter_user_id"]
    print(f"🔗 Linking email account to inviter: {owner_user_id}")
```

#### **Invitation Status Tracking**
- Track invitation progression: `active` → `ready_for_oauth` → `used`
- Link email accounts to inviter's user ID
- Maintain proper audit trail

### **Fix 3: Enhanced Email Accounts Listing**

#### **Show Both Owned and Invited Accounts**
```python
# Get email accounts owned by the current user
owned_accounts = await mongodb.db["email_accounts"].find({"user_id": current_user.id}).to_list(length=None)

# Get email accounts that were invited by the current user (for other users)
invited_accounts = await mongodb.db["email_accounts"].find({
    "user_id": {"$ne": current_user.id}  # Not owned by current user
}).to_list(length=None)

# Check which of these invited accounts were actually invited by the current user
invited_by_current_user = []
for account in invited_accounts:
    invitation = await mongodb.db["invites"].find_one({
        "inviter_user_id": current_user.id,
        "invite_type": "add_email_account",
        "invited_email": account.get("email", "").lower(),
        "status": "used",
        "added_email_account_id": str(account["_id"])
    })
    
    if invitation:
        invited_by_current_user.append(account)
```

#### **Account Type Identification**
```python
# Determine if this is an owned or invited account
is_owned = account.get("user_id") == current_user.id
account_type = "owned" if is_owned else "invited"

account_data = {
    # ... other fields ...
    "account_type": account_type,  # "owned" or "invited"
    "owner_user_id": account.get("user_id")  # Add owner info
}
```

## Updated Database Schema

### **Email Account Response Schema**
```python
class EmailAccountResponse(BaseModel):
    id: str
    user_id: str
    email: EmailStr
    provider: EmailProvider
    # ... other fields ...
    account_type: Optional[str] = None  # "owned" or "invited"
    owner_user_id: Optional[str] = None  # ID of the user who owns this account
```

### **Invitation Status Flow**
```
active → ready_for_oauth → used
  ↓           ↓          ↓
Created   Accepted    Connected
```

## Complete Workflow

### **1. Invitation Creation**
```
User A (logged in) → Creates invitation for user@example.com
↓
System generates token and sends email
↓
Invitation stored with status: "active"
```

### **2. Public Invitation Acceptance**
```
User B → Receives email → Clicks invitation link
↓
Opens invitation page (any browser)
↓
Accepts invitation without login
↓
System updates status to "ready_for_oauth"
```

### **3. OAuth Flow and Account Linking**
```
User B → Clicks "Log In with Google"
↓
Completes OAuth authentication
↓
OAuth callback processes invitation
↓
Email account created with owner_user_id = User A's ID
↓
Account linked to User A's system
```

### **4. Email Accounts Visibility**
```
User A → Goes to Email Accounts tab
↓
Sees both owned and invited accounts
↓
Invited accounts show as "invited" type
↓
Can scan invoices from invited accounts
```

## Testing

### **Run Test Script**
```bash
cd backend
python test_complete_invitation_flow.py
```

### **Manual Testing Steps**
1. **Create Invitation**
   - Log in as User A
   - Create invitation for user@example.com

2. **Accept Invitation**
   - Open invitation link in different browser
   - Accept invitation without login
   - Verify status updates to "ready_for_oauth"

3. **Complete OAuth**
   - Click "Log In with Google"
   - Complete OAuth flow
   - Verify no "User not authenticated" error

4. **Check Email Accounts**
   - Log in as User A
   - Go to Email Accounts tab
   - Verify invited account appears
   - Check account type shows as "invited"

5. **Test Functionality**
   - Verify invoice scanning works
   - Check Google Drive integration
   - Ensure proper account ownership

## Expected Results

### **For Inviters (User A)**
- ✅ Can see invited email accounts in Email Accounts tab
- ✅ Accounts show as "invited" type
- ✅ Can scan invoices from invited accounts
- ✅ Google Drive integration works
- ✅ Proper account management

### **For Invited Users (User B)**
- ✅ Can accept invitations without login
- ✅ OAuth flow completes successfully
- ✅ Email account gets connected
- ✅ Can access system functionality
- ✅ Account properly linked to inviter

### **System Behavior**
- ✅ No "User not authenticated" errors
- ✅ Proper invitation status progression
- ✅ Correct email account ownership
- ✅ Enhanced logging and debugging
- ✅ Account type identification

## Troubleshooting

### **Common Issues**

#### **Still Getting Authentication Error**
1. Check backend logs for detailed information
2. Verify invitation status progression
3. Check OAuth callback processing
4. Verify email account creation

#### **Invited Account Not Visible**
1. Check invitation status is "used"
2. Verify email account ownership
3. Check email accounts listing logic
4. Run test script to verify

#### **OAuth Flow Fails**
1. Check Google Cloud Console configuration
2. Verify OAuth redirect URIs
3. Check invitation status
4. Review backend logs

### **Debug Steps**
1. **Check Invitation Status**
   ```bash
   # In MongoDB
   db.invites.find({"invite_type": "add_email_account"})
   ```

2. **Check Email Accounts**
   ```bash
   # In MongoDB
   db.email_accounts.find({})
   ```

3. **Run Test Script**
   ```bash
   python test_complete_invitation_flow.py
   ```

4. **Check Backend Logs**
   - Look for invitation processing logs
   - Check OAuth callback logs
   - Verify account creation logs

## Benefits

### **For Users**
- **Seamless Experience**: No authentication barriers
- **Cross-Browser Compatibility**: Works in any browser
- **Clear Process**: Step-by-step guidance
- **Proper Integration**: Full functionality access

### **For System**
- **Better Tracking**: Enhanced invitation monitoring
- **Proper Ownership**: Clear account relationships
- **Enhanced Visibility**: Both owned and invited accounts
- **Improved Debugging**: Detailed logging and error handling

## Conclusion

The implemented fixes resolve the OAuth authentication issue and ensure that:

1. **Public invitations work correctly** without authentication barriers
2. **OAuth flow completes successfully** for invited users
3. **Email accounts are properly linked** to inviter's system
4. **Invited accounts are visible** in Email Accounts tab
5. **All functionality works** including invoice scanning and Drive integration

The system now provides a robust, user-friendly invitation flow that works seamlessly across different browsers and user scenarios while maintaining proper security and account management. 