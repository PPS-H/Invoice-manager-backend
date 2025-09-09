from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.responses import RedirectResponse
import requests
import os
from datetime import datetime, timedelta
from bson import ObjectId
from core.database import mongodb
from core.jwt import create_access_token, verify_token, get_current_user
from models.user import UserModel
from core.config import settings
from schemas.auth import (
    GoogleAuthRequest,
    GoogleCallbackRequest, 
    GoogleExchangeRequest,
    AuthResponse,
    UserResponse,
    GoogleAuthUrlResponse
)

router = APIRouter()

# OAuth Configuration
GOOGLE_CLIENT_ID = settings.GOOGLE_CLIENT_ID
GOOGLE_CLIENT_SECRET = settings.GOOGLE_CLIENT_SECRET
GOOGLE_REDIRECT_URI = settings.GOOGLE_REDIRECT_URI

@router.get("/google/login", response_model=GoogleAuthUrlResponse)
async def google_login():
    """Initiate Google OAuth login"""
    auth_url = "https://accounts.google.com/o/oauth2/v2/auth"
    params = {
        "client_id": GOOGLE_CLIENT_ID,
        "redirect_uri": GOOGLE_REDIRECT_URI,
        "response_type": "code",
        "scope": "openid email profile",
        "access_type": "offline",
        "prompt": "consent"
    }
    query_string = "&".join([f"{k}={v}" for k, v in params.items()])
    full_auth_url = f"{auth_url}?{query_string}"
    
    return GoogleAuthUrlResponse(auth_url=full_auth_url)

@router.get("/google/callback")
async def google_callback(code: str, state: str = None):
    """Handle Google OAuth callback"""
    try:
        print(f"Google callback received - Code: {code[:10]}...")
        print(f"Using redirect URI: {GOOGLE_REDIRECT_URI}")
        print(f"Client ID: {GOOGLE_CLIENT_ID[:20]}...")
        
        # Exchange code for tokens
        token_url = "https://oauth2.googleapis.com/token"
        token_data = {
            "client_id": GOOGLE_CLIENT_ID,
            "client_secret": GOOGLE_CLIENT_SECRET,
            "code": code,
            "grant_type": "authorization_code",
            "redirect_uri": GOOGLE_REDIRECT_URI
        }
        
        response = requests.post(token_url, data=token_data)
        
        if response.status_code != 200:
            error_data = response.json() if response.headers.get('content-type', '').startswith('application/json') else {"error": "unknown"}
            print(f"Google token exchange failed: {error_data}")
            
            # Provide more specific error messages
            if error_data.get("error") == "invalid_grant":
                if "authorization code" in error_data.get("error_description", "").lower():
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Authorization code has expired or already been used. Please try logging in again."
                    )
                elif "redirect_uri" in error_data.get("error_description", "").lower():
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Redirect URI mismatch. Expected: {GOOGLE_REDIRECT_URI}"
                    )
            
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Google OAuth error: {error_data.get('error_description', 'Token exchange failed')}"
            )
        
        tokens = response.json()
        
        # Get user info from Google
        user_info_url = "https://www.googleapis.com/oauth2/v1/userinfo"
        headers = {"Authorization": f"Bearer {tokens['access_token']}"}
        user_response = requests.get(user_info_url, headers=headers)
        
        if user_response.status_code != 200:
            print(f"Failed to get user info: Status {user_response.status_code}")
            print(f"Response: {user_response.text}")
            print(f"Access token: {tokens['access_token'][:20]}...")
            
            # Try alternative endpoint
            user_info_url_alt = "https://www.googleapis.com/oauth2/v2/userinfo"
            user_response_alt = requests.get(user_info_url_alt, headers=headers)
            
            if user_response_alt.status_code != 200:
                print(f"Alternative endpoint also failed: Status {user_response_alt.status_code}")
                print(f"Alternative response: {user_response_alt.text}")
                
                # TEMPORARY: Create a mock user for testing
                print("Creating mock user for testing purposes...")
                user_info = {
                    "id": "mock_google_id_" + str(hash(code))[:10],
                    "email": "test@example.com",
                    "name": "Test User",
                    "picture": "https://ui-avatars.com/api/?name=Test+User&background=2563eb&color=fff&size=150"
                }
                print(f"Using mock user: {user_info}")
            else:
                user_response = user_response_alt
                print(f"Alternative endpoint worked!")
                user_info = user_response.json()
        else:
            user_info = user_response.json()
        
        # Check if user exists
        existing_user = await mongodb.db["users"].find_one({"google_id": user_info["id"]})
        
        if existing_user:
            # Update existing user
            await mongodb.db["users"].update_one(
                {"_id": existing_user["_id"]},
                {"$set": {
                    "email": user_info["email"],
                    "name": user_info.get("name", ""),
                    "picture": user_info.get("picture", ""),
                    "updated_at": datetime.utcnow()
                }}
            )
            user_id = str(existing_user["_id"])
        else:
            # Create new user
            user = UserModel(
                google_id=user_info["id"],
                email=user_info["email"],
                name=user_info.get("name", ""),
                picture=user_info.get("picture", "")
            )
            
            print(f"About to save user: {user.dict()}")
            
            try:
                result = await mongodb.db["users"].insert_one(user.dict(by_alias=True))
                user_id = str(result.inserted_id)
                print(f"Created new user: {user_id}")
                
                # Verify user was saved
                saved_user = await mongodb.db["users"].find_one({"_id": result.inserted_id})
                if saved_user:
                    print(f"User verified in database: {saved_user}")
                else:
                    print("ERROR: User not found in database after save!")
                    
            except Exception as e:
                print(f"ERROR saving user: {e}")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Failed to save user: {str(e)}"
                )
        
        # Create JWT token
        access_token = create_access_token(
            data={"sub": user_id, "email": user_info["email"]}
        )
        
        # Redirect to frontend with success
        frontend_redirect = f"http://localhost:5173/auth/callback?code={code}"
        return RedirectResponse(url=frontend_redirect)
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Callback error: {str(e)}")
        # Redirect to frontend with error
        frontend_redirect = f"http://localhost:5173/auth/callback?error=authentication_failed"
        return RedirectResponse(url=frontend_redirect)

@router.post("/google/exchange", response_model=AuthResponse)
async def google_exchange_code(request: GoogleExchangeRequest):
    """Exchange Google OAuth code for JWT token (called by frontend)"""
    try:
        print(f"Google exchange attempt with code: {request.code[:10]}...")
        print(f"Using redirect URI: {GOOGLE_REDIRECT_URI}")
        print(f"Client ID: {GOOGLE_CLIENT_ID[:20]}...")
        
        # Exchange code for tokens
        token_url = "https://oauth2.googleapis.com/token"
        token_data = {
            "client_id": GOOGLE_CLIENT_ID,
            "client_secret": GOOGLE_CLIENT_SECRET,
            "code": request.code,
            "grant_type": "authorization_code",
            "redirect_uri": GOOGLE_REDIRECT_URI
        }
        
        response = requests.post(token_url, data=token_data)
        
        if response.status_code != 200:
            error_data = response.json() if response.headers.get('content-type', '').startswith('application/json') else {"error": "unknown"}
            print(f"Google token exchange failed: Status {response.status_code}")
            print(f"Error data: {error_data}")
            
            # Provide more specific error messages
            if error_data.get("error") == "invalid_grant":
                if "authorization code" in error_data.get("error_description", "").lower():
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Authorization code has expired or already been used. Please try logging in again."
                    )
                elif "redirect_uri" in error_data.get("error_description", "").lower():
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Redirect URI mismatch. Expected: {GOOGLE_REDIRECT_URI}"
                    )
            
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Google OAuth error: {error_data.get('error_description', 'Token exchange failed')}"
            )
        
        tokens = response.json()
        print(f"Successfully got tokens from Google")
        print(f"Access token: {tokens.get('access_token', 'missing')[:20]}...")
        print(f"Token type: {tokens.get('token_type', 'missing')}")
        print(f"Expires in: {tokens.get('expires_in', 'missing')}")
        print(f"Scope: {tokens.get('scope', 'missing')}")
        
        # Verify the access token by calling tokeninfo endpoint
        tokeninfo_url = "https://www.googleapis.com/oauth2/v1/tokeninfo"
        tokeninfo_response = requests.get(f"{tokeninfo_url}?access_token={tokens['access_token']}")
        
        if tokeninfo_response.status_code == 200:
            tokeninfo = tokeninfo_response.json()
            print(f"Token info: {tokeninfo}")
        else:
            print(f"Token info failed: Status {tokeninfo_response.status_code}")
            print(f"Token info response: {tokeninfo_response.text}")
        
        # Get user info from Google
        user_info_url = "https://www.googleapis.com/oauth2/v1/userinfo"
        headers = {"Authorization": f"Bearer {tokens['access_token']}"}
        user_response = requests.get(user_info_url, headers=headers)
        
        if user_response.status_code != 200:
            print(f"Failed to get user info: Status {user_response.status_code}")
            print(f"Response: {user_response.text}")
            print(f"Access token: {tokens['access_token'][:20]}...")
            
            # Try alternative endpoint
            user_info_url_alt = "https://www.googleapis.com/oauth2/v2/userinfo"
            user_response_alt = requests.get(user_info_url_alt, headers=headers)
            
            if user_response_alt.status_code != 200:
                print(f"Alternative endpoint also failed: Status {user_response_alt.status_code}")
                print(f"Alternative response: {user_response_alt.text}")
                
                # TEMPORARY: Create a mock user for testing
                print("Creating mock user for testing purposes...")
                user_info = {
                    "id": "mock_google_id_" + str(hash(request.code))[:10],
                    "email": "test@example.com",
                    "name": "Test User",
                    "picture": "https://ui-avatars.com/api/?name=Test+User&background=2563eb&color=fff&size=150"
                }
                print(f"Using mock user: {user_info}")
            else:
                user_response = user_response_alt
                print(f"Alternative endpoint worked!")
                user_info = user_response.json()
        else:
            user_info = user_response.json()
            
        print(f"Got user info for: {user_info.get('email')}")
        
        # Check if user exists
        existing_user = await mongodb.db["users"].find_one({"google_id": user_info["id"]})
        
        if existing_user:
            # Update existing user
            await mongodb.db["users"].update_one(
                {"_id": existing_user["_id"]},
                {"$set": {
                    "email": user_info["email"],
                    "name": user_info.get("name", ""),
                    "picture": user_info.get("picture", ""),
                    "updated_at": datetime.utcnow()
                }}
            )
            user_id = str(existing_user["_id"])
            print(f"Updated existing user: {user_id}")
        else:
            # Create new user
            user = UserModel(
                google_id=user_info["id"],
                email=user_info["email"],
                name=user_info.get("name", ""),
                picture=user_info.get("picture", "")
            )
            
            result = await mongodb.db["users"].insert_one(user.dict(by_alias=True))
            user_id = str(result.inserted_id)
            print(f"Created new user: {user_id}")
        
        # Create JWT token
        access_token = create_access_token(
            data={"sub": user_id, "email": user_info["email"]}
        )
        
        return AuthResponse(
            access_token=access_token,
            token_type="bearer",
            user=UserResponse(
                id=user_id,
                email=user_info["email"],
                name=user_info.get("name", ""),
                picture=user_info.get("picture", ""),
                google_id=user_info["id"]
            )
        )
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Exchange error: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Authentication failed: {str(e)}"
        )

@router.post("/mock-login", response_model=AuthResponse)
async def mock_login():
    """Mock login for testing purposes when Google OAuth is not configured"""
    try:
        # Create a mock user
        mock_user_info = {
            "id": "mock_user_123",
            "email": "test@example.com",
            "name": "Test User",
            "picture": "https://via.placeholder.com/150"
        }
        
        # Check if user exists
        existing_user = await mongodb.db["users"].find_one({"google_id": mock_user_info["id"]})
        
        if existing_user:
            # Update existing user
            await mongodb.db["users"].update_one(
                {"_id": existing_user["_id"]},
                {"$set": {
                    "email": mock_user_info["email"],
                    "name": mock_user_info.get("name", ""),
                    "picture": mock_user_info.get("picture", ""),
                    "updated_at": datetime.utcnow()
                }}
            )
            user_id = str(existing_user["_id"])
        else:
            # Create new user
            user_doc = {
                "google_id": mock_user_info["id"],
                "email": mock_user_info["email"],
                "name": mock_user_info.get("name", ""),
                "picture": mock_user_info.get("picture", ""),
                "linked_accounts": [],
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow()
            }
            
            result = await mongodb.db["users"].insert_one(user_doc)
            user_id = str(result.inserted_id)
        
        # Create JWT token
        access_token = create_access_token(data={"sub": user_id})
        
        # Get user data for response
        user_data = await mongodb.db["users"].find_one({"_id": ObjectId(user_id)})
        user_data['id'] = str(user_data['_id'])
        del user_data['_id']  # Remove ObjectId field to avoid validation error
        user_response = UserModel(**user_data)
        
        return AuthResponse(
            access_token=access_token,
            token_type="bearer",
            user=user_response
        )
        
    except Exception as e:
        print(f"Mock login error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Mock login failed: {str(e)}"
        )

@router.post("/dev-login", response_model=AuthResponse)
async def dev_login():
    """Development login that bypasses database for quick testing"""
    # Create a simple JWT token for testing
    from core.jwt import create_access_token
    
    # Create a test token without database interaction
    access_token = create_access_token(
        data={"sub": "test_user_123", "email": "test@example.com"}
    )
    
    # Return mock user data
    mock_user = {
        "id": "test_user_123",
        "email": "test@example.com", 
        "name": "Test User",
        "picture": "https://via.placeholder.com/150",
        "google_id": "mock_google_123"
    }
    
    return AuthResponse(
        access_token=access_token,
        token_type="bearer",
        user=UserResponse(**mock_user)
    )

@router.post("/test-google-exchange")
async def test_google_exchange(request: dict):
    """Test Google OAuth token exchange with provided code"""
    code = request.get("code")
    if not code:
        raise HTTPException(status_code=400, detail="Code is required")
    
    # Exchange code for tokens
    token_url = "https://oauth2.googleapis.com/token"
    token_data = {
        "client_id": GOOGLE_CLIENT_ID,
        "client_secret": GOOGLE_CLIENT_SECRET,
        "code": code,
        "grant_type": "authorization_code",
        "redirect_uri": GOOGLE_REDIRECT_URI
    }
    
    response = requests.post(token_url, data=token_data)
    
    return {
        "status_code": response.status_code,
        "response": response.json() if response.headers.get('content-type', '').startswith('application/json') else response.text,
        "success": response.status_code == 200
    }

@router.get("/test-google-config")
async def test_google_config():
    """Test Google OAuth configuration"""
    return {
        "client_id": GOOGLE_CLIENT_ID[:20] + "..." if GOOGLE_CLIENT_ID else "MISSING",
        "client_secret": "SET" if GOOGLE_CLIENT_SECRET else "MISSING",
        "redirect_uri": GOOGLE_REDIRECT_URI,
        "config_status": "OK" if GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET else "INCOMPLETE"
    }

@router.get("/test-auth")
async def test_auth(current_user: UserModel = Depends(get_current_user)):
    """Test endpoint to verify authentication is working"""
    return {
        "message": "Authentication working",
        "user": {
            "id": current_user.id,
            "email": current_user.email,
            "name": current_user.name
        }
    }

@router.get("/me", response_model=UserResponse)
async def get_current_user(request: Request):
    """Get current authenticated user"""
    # Get authorization header
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid authorization header"
        )
    
    # Extract token
    token = auth_header.split(" ")[1]
    
    try:
        # Verify token
        payload = verify_token(token)
        user_id = payload.get("sub")
        
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token payload"
            )
        
        # Get user from database
        user = await mongodb.db["users"].find_one({"_id": ObjectId(user_id)})
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        return UserResponse(
            id=str(user["_id"]),
            email=user["email"],
            name=user.get("name", ""),
            picture=user.get("picture", ""),
            google_id=user.get("google_id"),
            created_at=user.get("created_at"),
            updated_at=user.get("updated_at")
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token"
        ) 