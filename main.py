from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from core import config  # Load environment variables
from core.database import connect_to_mongo, close_mongo_connection
from routes import auth, invoices, email_accounts, dashboard, groups, invites, email_filters, vendors, admin

app = FastAPI(title="Invoice SaaS Backend", version="1.0.0")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173", "http://localhost:5174", "http://127.0.0.1:3000", "http://127.0.0.1:5173", "http://127.0.0.1:5174", "https://invoice.saasdor.com"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
async def startup_event():
    await connect_to_mongo()

@app.on_event("shutdown")
async def shutdown_event():
    await close_mongo_connection()

# Include routers
app.include_router(auth.router, prefix="/auth")
app.include_router(email_accounts.router, prefix="/api")
app.include_router(invoices.router, prefix="/api")
app.include_router(dashboard.router, prefix="/api")
app.include_router(groups.router, prefix="/api")
app.include_router(invites.router, prefix="/api")
app.include_router(email_filters.router, prefix="/api")
app.include_router(vendors.router, prefix="/api")
app.include_router(admin.router, prefix="/api")

@app.get("/")
async def root():
    return {"message": "Invoice SaaS Backend API", "version": "1.0.0"}

@app.get("/health")
async def health_check():
    return {"status": "healthy"}



if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=False) 
