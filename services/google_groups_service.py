import logging
import os
from typing import List, Dict, Optional
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from datetime import datetime
from models.google_group import GoogleGroupModel
from models.email_account import EmailAccountModel
from core.database import mongodb
from core.config import settings

logger = logging.getLogger(__name__)

class GoogleGroupsService:
    """Service to interact with Google Groups API"""
    
    def __init__(self):
        self.service = None
        self.credentials = None
    
    def authenticate(self, access_token: str, refresh_token: str = None) -> bool:
        """Authenticate with Google Admin SDK"""
        try:
            self.credentials = Credentials(
                token=access_token,
                refresh_token=refresh_token,
                token_uri="https://oauth2.googleapis.com/token",
                client_id=settings.GOOGLE_CLIENT_ID,
                client_secret=settings.GOOGLE_CLIENT_SECRET
            )
            
            # Refresh token if needed
            if self.credentials.expired and refresh_token:
                self.credentials.refresh(Request())
            
            # Build the Admin SDK service
            self.service = build('admin', 'directory_v1', credentials=self.credentials)
            return True
            
        except Exception as e:
            logger.error(f"Failed to authenticate with Google Admin SDK: {str(e)}")
            return False
    
    def get_groups(self) -> List[Dict[str, any]]:
        """Get all Google Groups for the authenticated user"""
        try:
            if not self.service:
                raise Exception("Service not initialized")
            
            # Get groups
            groups = []
            page_token = None
            
            while True:
                request = self.service.groups().list(
                    customer='my_customer',
                    maxResults=100,
                    pageToken=page_token
                )
                response = request.execute()
                
                groups.extend(response.get('groups', []))
                
                page_token = response.get('nextPageToken')
                if not page_token:
                    break
            
            return groups
            
        except Exception as e:
            logger.error(f"Error fetching Google Groups: {str(e)}")
            return []
    
    async def sync_groups_to_database(self, user_id: str, email_account_id: str, access_token: str, refresh_token: str = None) -> Dict[str, any]:
        """Sync Google Groups to database"""
        try:
            # Authenticate
            if not self.authenticate(access_token, refresh_token):
                return {
                    'success': False,
                    'message': 'Failed to authenticate with Google',
                    'groups_count': 0,
                    'synced_count': 0,
                    'groups': []
                }
            
            # Get groups from Google
            google_groups = self.get_groups()
            
            if not google_groups:
                return {
                    'success': True,
                    'message': 'No groups found',
                    'groups_count': 0,
                    'synced_count': 0,
                    'groups': []
                }
            
            # Get database
            groups_collection = mongodb.db["google_groups"]
            
            # Sync groups to database
            synced_count = 0
            for group_data in google_groups:
                try:
                    # Check if group already exists
                    existing_group = await groups_collection.find_one({
                        'user_id': user_id,
                        'email_account_id': email_account_id,
                        'group_id': group_data['id']
                    })
                    
                    group_model = GoogleGroupModel(
                        user_id=user_id,
                        email_account_id=email_account_id,
                        group_id=group_data['id'],
                        name=group_data.get('name', ''),
                        email=group_data.get('email', ''),
                        description=group_data.get('description', ''),
                        member_count=group_data.get('directMembersCount', 0),
                        is_active=True,
                        connected=existing_group.get('connected', False) if existing_group else False,
                        last_sync=datetime.utcnow()
                    )
                    
                    if existing_group:
                        # Update existing group
                        await groups_collection.update_one(
                            {'_id': existing_group['_id']},
                            {'$set': group_model.model_dump(exclude={'id'})}
                        )
                    else:
                        # Insert new group (exclude id field for new records)
                        group_dict = group_model.model_dump(exclude={'id'})
                        await groups_collection.insert_one(group_dict)
                    
                    synced_count += 1
                    
                except Exception as e:
                    logger.error(f"Error syncing group {group_data.get('id')}: {str(e)}")
                    continue
            
            return {
                'success': True,
                'message': f'Successfully synced {synced_count} groups',
                'groups_count': len(google_groups),
                'synced_count': synced_count,
                'groups': google_groups
            }
            
        except Exception as e:
            logger.error(f"Error syncing groups to database: {str(e)}")
            return {
                'success': False,
                'message': f'Error syncing groups: {str(e)}',
                'groups_count': 0,
                'synced_count': 0,
                'groups': []
            }
    
    async def get_groups_from_database(self, user_id: str, email_account_id: str = None) -> List[GoogleGroupModel]:
        """Get groups from database"""
        try:
            groups_collection = mongodb.db["google_groups"]
            
            query = {'user_id': user_id}
            if email_account_id:
                query['email_account_id'] = email_account_id
            
            groups_data = await groups_collection.find(query).to_list(length=None)
            
            # Convert ObjectId to string for each group
            groups = []
            for group in groups_data:
                group['id'] = str(group['_id'])
                del group['_id']  # Remove ObjectId field to avoid validation error
                groups.append(GoogleGroupModel(**group))
            
            return groups
            
        except Exception as e:
            logger.error(f"Error getting groups from database: {str(e)}")
            return []
    
    async def update_group_connection_status(self, user_id: str, email_account_id: str, selected_group_ids: List[str]) -> bool:
        """Update which groups are connected for scanning"""
        try:
            groups_collection = mongodb.db["google_groups"]
            
            # Get all groups for this email account
            all_groups = await groups_collection.find({
                'user_id': user_id,
                'email_account_id': email_account_id
            }).to_list(length=None)
            
            # Update connection status for all groups
            for group in all_groups:
                is_connected = str(group['_id']) in selected_group_ids
                await groups_collection.update_one(
                    {'_id': group['_id']},
                    {'$set': {'connected': is_connected, 'updated_at': datetime.utcnow()}}
                )
            
            return True
            
        except Exception as e:
            logger.error(f"Error updating group connection status: {str(e)}")
            return False 