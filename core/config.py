import os
from dotenv import load_dotenv

load_dotenv()

class Settings:
    MONGODB_URI: str = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
    MONGODB_DB: str = os.getenv("MONGODB_DB", "invoice")
    
    # Google OAuth Configuration
    # To get these values:
    # 1. Go to https://console.cloud.google.com/
    # 2. Create a new project or select existing
    # 3. Enable Google+ API
    # 4. Create OAuth 2.0 credentials
    # 5. Add http://localhost:5173/auth/callback to authorized redirect URIs
    GOOGLE_CLIENT_ID: str = os.getenv("GOOGLE_CLIENT_ID", "335844982428-81d0ifptntss8716c3pfgk1h8i2vb2lo.apps.googleusercontent.com")
    GOOGLE_CLIENT_SECRET: str = os.getenv("GOOGLE_CLIENT_SECRET", "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")
    GOOGLE_REDIRECT_URI: str = os.getenv("GOOGLE_REDIRECT_URI", "http://localhost:5173/auth/callback")
    
    # Security
    SESSION_SECRET: str = os.getenv("SESSION_SECRET", "your-session-secret-key")
    JWT_SECRET_KEY: str = os.getenv("JWT_SECRET_KEY", "changeme_super_secret_key")
    JWT_ALGORITHM: str = os.getenv("JWT_ALGORITHM", "HS256")
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("JWT_ACCESS_TOKEN_EXPIRE_MINUTES", "30"))
    
    # Gemini AI Configuration
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")

    def __post_init__(self):
        if not self.GOOGLE_CLIENT_SECRET:
            print("WARNING: GOOGLE_CLIENT_SECRET is not set. Google OAuth will not work.")
            print("Please set GOOGLE_CLIENT_SECRET environment variable or update config.py")

settings = Settings() 

# Check for missing Google OAuth configuration
if not settings.GOOGLE_CLIENT_SECRET:
    print("⚠️  Google OAuth is not properly configured!")
    print("   Please set GOOGLE_CLIENT_SECRET environment variable")
    print("   Or update the GOOGLE_CLIENT_SECRET in core/config.py")
    print("   Get your credentials from: https://console.cloud.google.com/")

# Check for missing Gemini API key
if not settings.GEMINI_API_KEY:
    print("⚠️  WARNING: Gemini API key is not configured!")
    print("   Invoice extraction will not work without GEMINI_API_KEY")
    print("   Please set GEMINI_API_KEY environment variable in .env file")
    print("   Get your API key from: https://aistudio.google.com/app/apikey")
else:
    print(f"✅ Gemini API key configured (ends with: ...{settings.GEMINI_API_KEY[-10:]})") 