#!/usr/bin/env python3
import asyncio
from core.database import mongodb, connect_to_mongo
from bson import ObjectId

async def check_email_accounts():
    await connect_to_mongo()
    db = mongodb.db
    
    accounts = await db['email_accounts'].find().to_list(length=None)
    print(f'Found {len(accounts)} email accounts:')
    
    for i, acc in enumerate(accounts):
        print(f'Account {i+1}:')
        print(f'  _id: {acc.get("_id")}')
        print(f'  id field: {acc.get("id")}')
        print(f'  email: {acc.get("email")}')
        print(f'  user_id: {acc.get("user_id")}')
        print(f'  status: {acc.get("status")}')
        print(f'  provider: {acc.get("provider")}')
        print('  ---')

if __name__ == "__main__":
    asyncio.run(check_email_accounts()) 