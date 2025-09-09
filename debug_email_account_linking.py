#!/usr/bin/env python3
"""
Debug script for Email Account Linking
This helps understand what's happening when invited users complete OAuth
"""

import os
import sys
import asyncio
from datetime import datetime

# Add the backend directory to the path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

async def debug_email_account_linking():
    """Debug email account linking issues"""
    
    print("🔍 Debugging Email Account Linking")
    print("=" * 80)
    
    try:
        from core.database import connect_to_mongo, mongodb
        await connect_to_mongo()
        print("✅ MongoDB connected successfully")
        
        # Check all invitations
        print("\n📧 Step 1: Checking all invitations")
        all_invites = await mongodb.db["invites"].find({
            "invite_type": "add_email_account"
        }).to_list(length=None)
        
        print(f"   📊 Found {len(all_invites)} total invitations")
        
        for invite in all_invites:
            print(f"\n   📧 Invitation: {invite.get('invited_email')}")
            print(f"      ID: {invite['_id']}")
            print(f"      Status: {invite.get('status')}")
            print(f"      Inviter: {invite.get('inviter_user_id')}")
            print(f"      Created: {invite.get('created_at')}")
            print(f"      Updated: {invite.get('updated_at')}")
            print(f"      Used by: {invite.get('used_by_user_id')}")
            print(f"      Added account: {invite.get('added_email_account_id')}")
            
            # Check if there's a corresponding email account
            if invite.get('added_email_account_id'):
                email_account = await mongodb.db["email_accounts"].find_one({
                    "_id": invite['added_email_account_id']
                })
                if email_account:
                    print(f"      📧 Email account found:")
                    print(f"         ID: {email_account['_id']}")
                    print(f"         Email: {email_account.get('email')}")
                    print(f"         User ID: {email_account.get('user_id')}")
                    print(f"         Status: {email_account.get('status')}")
                    print(f"         Created: {email_account.get('created_at')}")
                else:
                    print(f"      ❌ Email account not found!")
            else:
                print(f"      ⚠️ No email account ID linked yet")
        
        # Check all email accounts
        print("\n📧 Step 2: Checking all email accounts")
        all_email_accounts = await mongodb.db["email_accounts"].find({}).to_list(length=None)
        
        print(f"   📊 Found {len(all_email_accounts)} total email accounts")
        
        # Group by user_id
        user_accounts = {}
        for account in all_email_accounts:
            user_id = account.get('user_id')
            if user_id not in user_accounts:
                user_accounts[user_id] = []
            user_accounts[user_id].append(account)
        
        print("\n   👥 Email accounts by user:")
        for user_id, accounts in user_accounts.items():
            print(f"      User {user_id}: {len(accounts)} accounts")
            for account in accounts:
                print(f"        - {account.get('email')} (Status: {account.get('status')})")
                print(f"          Created: {account.get('created_at')}")
                print(f"          Updated: {account.get('updated_at')}")
        
        # Check for orphaned accounts (accounts without valid invitations)
        print("\n🔍 Step 3: Checking for orphaned accounts")
        orphaned_accounts = []
        
        for account in all_email_accounts:
            # Check if this account was created through an invitation
            invitation = await mongodb.db["invites"].find_one({
                "invite_type": "add_email_account",
                "invited_email": account.get("email", "").lower(),
                "status": "used",
                "added_email_account_id": str(account["_id"])
            })
            
            if not invitation:
                # This account might be orphaned
                orphaned_accounts.append(account)
        
        if orphaned_accounts:
            print(f"   ⚠️ Found {len(orphaned_accounts)} potentially orphaned accounts:")
            for account in orphaned_accounts:
                print(f"      - {account.get('email')} (User ID: {account.get('user_id')})")
                print(f"        Status: {account.get('status')}")
                print(f"        Created: {account.get('created_at')}")
        else:
            print("   ✅ No orphaned accounts found")
        
        # Check invitation status progression
        print("\n📊 Step 4: Checking invitation status progression")
        
        status_counts = {}
        for invite in all_invites:
            status = invite.get('status', 'unknown')
            status_counts[status] = status_counts.get(status, 0) + 1
        
        print("   📋 Invitation status breakdown:")
        for status, count in status_counts.items():
            print(f"      {status}: {count}")
        
        # Check for stuck invitations
        print("\n⚠️ Step 5: Checking for stuck invitations")
        
        # Check invitations that are ready_for_oauth but haven't been processed
        stuck_invites = await mongodb.db["invites"].find({
            "invite_type": "add_email_account",
            "status": "ready_for_oauth"
        }).to_list(length=None)
        
        if stuck_invites:
            print(f"   ⚠️ Found {len(stuck_invites)} stuck invitations (ready_for_oauth):")
            for invite in stuck_invites:
                print(f"      - {invite.get('invited_email')}")
                print(f"        ID: {invite['_id']}")
                print(f"        Updated: {invite.get('updated_at')}")
                
                # Check if there's already an email account for this email
                existing_account = await mongodb.db["email_accounts"].find_one({
                    "email": invite.get('invited_email')
                })
                
                if existing_account:
                    print(f"        ⚠️ Email account already exists: {existing_account['_id']}")
                    print(f"           User ID: {existing_account.get('user_id')}")
                else:
                    print(f"        ✅ No email account exists yet")
        else:
            print("   ✅ No stuck invitations found")
        
        # Check for duplicate email accounts
        print("\n🔍 Step 6: Checking for duplicate email accounts")
        
        email_counts = {}
        for account in all_email_accounts:
            email = account.get('email', '').lower()
            email_counts[email] = email_counts.get(email, 0) + 1
        
        duplicates = {email: count for email, count in email_counts.items() if count > 1}
        
        if duplicates:
            print(f"   ⚠️ Found {len(duplicates)} duplicate email addresses:")
            for email, count in duplicates.items():
                print(f"      - {email}: {count} accounts")
                
                # Show details of duplicate accounts
                duplicate_accounts = await mongodb.db["email_accounts"].find({
                    "email": email
                }).to_list(length=None)
                
                for i, account in enumerate(duplicate_accounts):
                    print(f"        Account {i+1}:")
                    print(f"          ID: {account['_id']}")
                    print(f"          User ID: {account.get('user_id')}")
                    print(f"          Status: {account.get('status')}")
                    print(f"          Created: {account.get('created_at')}")
        else:
            print("   ✅ No duplicate email accounts found")
        
        print("\n🎉 Debug analysis completed!")
        return True
        
    except Exception as e:
        print(f"❌ Error during debug analysis: {e}")
        import traceback
        print(f"   Traceback: {traceback.format_exc()}")
        return False

async def main():
    """Main debug function"""
    
    print("🚀 Starting Email Account Linking Debug")
    print("=" * 80)
    
    success = await debug_email_account_linking()
    
    print("\n" + "=" * 80)
    print("🏁 Debug analysis completed!")
    
    if success:
        print("\n📋 Analysis Summary:")
        print("1. ✅ Invitation status checked")
        print("2. ✅ Email accounts examined")
        print("3. ✅ Account ownership verified")
        print("4. ✅ Orphaned accounts identified")
        print("5. ✅ Stuck invitations found")
        print("6. ✅ Duplicate accounts checked")
        
        print("\n🔧 Next Steps:")
        print("1. Review the debug output above")
        print("2. Identify any issues with account linking")
        print("3. Check invitation status progression")
        print("4. Verify email account ownership")
        print("5. Fix any identified issues")
        
    else:
        print("\n❌ Debug analysis failed. Please check the errors above.")
    
    print("\n💡 Tips:")
    print("1. Look for invitations stuck in 'ready_for_oauth' status")
    print("2. Check if email accounts have correct user_id")
    print("3. Verify invitation status progression")
    print("4. Look for duplicate or orphaned accounts")

if __name__ == "__main__":
    asyncio.run(main()) 