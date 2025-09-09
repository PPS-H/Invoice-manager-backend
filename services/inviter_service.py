"""
Service to determine the inviter user for email accounts
"""
import logging
from typing import Optional, Dict, Any
from bson import ObjectId
from core.database import mongodb

logger = logging.getLogger(__name__)

class InviterService:
    """Service to find the inviter user for email accounts"""
    
    @staticmethod
    async def get_inviter_user_for_email_account(email_account_id: str) -> Optional[Dict[str, Any]]:
        """
        Find the inviter user for a given email account.
        
        Args:
            email_account_id: The email account ID to find the inviter for
            
        Returns:
            Dict with inviter user info, or None if not found
        """
        try:
            # First, get the email account
            email_account = await mongodb.db["email_accounts"].find_one({
                "_id": ObjectId(email_account_id)
            })
            
            if not email_account:
                logger.warning(f"Email account not found: {email_account_id}")
                return None
            
            email_address = email_account.get("email", "").lower()
            account_user_id = email_account.get("user_id")
            
            logger.info(f"🔍 Finding inviter for email account: {email_address}")
            logger.info(f"   Account User ID: {account_user_id}")
            
            # Check if this email account was created through an invitation
            # Look for used invitations where this email was invited
            # First try with added_email_account_id (more specific)
            invitation = await mongodb.db["invites"].find_one({
                "invite_type": "add_email_account",
                "invited_email": email_address,
                "status": "used",
                "added_email_account_id": str(email_account_id)
            })
            
            # If not found with added_email_account_id, try without it (fallback)
            if not invitation:
                invitation = await mongodb.db["invites"].find_one({
                    "invite_type": "add_email_account",
                    "invited_email": email_address,
                    "status": "used"
                })
            
            if invitation:
                inviter_user_id = invitation.get("inviter_user_id")
                logger.info(f"✅ Found invitation - Inviter User ID: {inviter_user_id}")
                logger.info(f"   Invitation ID: {invitation.get('_id')}")
                logger.info(f"   Invited Email: {invitation.get('invited_email')}")
                logger.info(f"   Added Email Account ID: {invitation.get('added_email_account_id')}")
                
                # Get the inviter user details
                inviter_user = await mongodb.db["users"].find_one({
                    "_id": ObjectId(inviter_user_id)
                })
                
                if inviter_user:
                    logger.info(f"✅ Found inviter user: {inviter_user.get('email', 'Unknown')}")
                    return {
                        "user_id": str(inviter_user["_id"]),
                        "email": inviter_user.get("email"),
                        "name": inviter_user.get("name"),
                        "is_inviter": True,
                        "invitation_id": str(invitation["_id"])
                    }
                else:
                    logger.warning(f"Inviter user not found: {inviter_user_id}")
                    return None
            else:
                # No invitation found - this is likely the user's own account
                # The account owner is the inviter (themselves)
                logger.info(f"📧 No invitation found - this is likely the user's own account")
                logger.info(f"   Searching for invitations with email: {email_address}")
                
                # Let's also check what invitations exist for this email
                all_invitations = await mongodb.db["invites"].find({
                    "invite_type": "add_email_account",
                    "invited_email": email_address
                }).to_list(length=None)
                
                logger.info(f"   Found {len(all_invitations)} total invitations for this email")
                for inv in all_invitations:
                    logger.info(f"     - Status: {inv.get('status')}, Inviter: {inv.get('inviter_user_id')}")
                
                # Get the account owner details
                account_owner = await mongodb.db["users"].find_one({
                    "_id": ObjectId(account_user_id)
                })
                
                if account_owner:
                    logger.info(f"✅ Account owner is the inviter: {account_owner.get('email', 'Unknown')}")
                    return {
                        "user_id": str(account_owner["_id"]),
                        "email": account_owner.get("email"),
                        "name": account_owner.get("name"),
                        "is_inviter": True,
                        "is_own_account": True
                    }
                else:
                    logger.warning(f"Account owner not found: {account_user_id}")
                    return None
                    
        except Exception as e:
            logger.error(f"Error finding inviter for email account {email_account_id}: {str(e)}")
            return None
    
    @staticmethod
    async def get_inviter_user_for_email_address(email_address: str) -> Optional[Dict[str, Any]]:
        """
        Find the inviter user for a given email address.
        
        Args:
            email_address: The email address to find the inviter for
            
        Returns:
            Dict with inviter user info, or None if not found
        """
        try:
            email_address = email_address.lower()
            logger.info(f"🔍 Finding inviter for email address: {email_address}")
            
            # First, find the email account
            email_account = await mongodb.db["email_accounts"].find_one({
                "email": email_address
            })
            
            if not email_account:
                logger.warning(f"Email account not found for: {email_address}")
                return None
            
            # Use the existing method
            return await InviterService.get_inviter_user_for_email_account(str(email_account["_id"]))
                    
        except Exception as e:
            logger.error(f"Error finding inviter for email address {email_address}: {str(e)}")
            return None
    
    @staticmethod
    async def get_all_invited_email_accounts_for_user(user_id: str) -> list:
        """
        Get all email accounts that were invited by a specific user.
        
        Args:
            user_id: The user ID to find invited accounts for
            
        Returns:
            List of email account info
        """
        try:
            logger.info(f"🔍 Finding all invited email accounts for user: {user_id}")
            
            # Find all invitations created by this user
            invitations = await mongodb.db["invites"].find({
                "inviter_user_id": user_id,
                "invite_type": "add_email_account",
                "status": "used"
            }).to_list(length=None)
            
            invited_accounts = []
            for invitation in invitations:
                email_account_id = invitation.get("added_email_account_id")
                if email_account_id:
                    email_account = await mongodb.db["email_accounts"].find_one({
                        "_id": ObjectId(email_account_id)
                    })
                    
                    if email_account:
                        invited_accounts.append({
                            "account_id": str(email_account["_id"]),
                            "email": email_account.get("email"),
                            "provider": email_account.get("provider"),
                            "status": email_account.get("status"),
                            "invitation_id": str(invitation["_id"])
                        })
            
            logger.info(f"✅ Found {len(invited_accounts)} invited accounts for user {user_id}")
            return invited_accounts
                    
        except Exception as e:
            logger.error(f"Error finding invited accounts for user {user_id}: {str(e)}")
            return []

# Global instance
inviter_service = InviterService()