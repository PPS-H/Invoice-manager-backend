# Vendor Preference Email Scanning System

## 🎯 System Overview

This system allows users to select their preferred vendors for email scanning, ensuring only relevant emails are processed by Gemini AI.

## 📊 System Flow Diagram

```mermaid
graph TD
    A[User Login] --> B{Has User Preferences?}
    B -->|No| C[Show Vendor Selection Page]
    B -->|Yes| D[Load User Preferences]
    
    C --> E[Display Available Vendors]
    E --> F[User Selects Vendors]
    F --> G[User Adds Custom Vendors]
    G --> H[Save User Preferences]
    H --> I[Redirect to Dashboard]
    
    D --> J[Show Dashboard with Selected Vendors]
    J --> K[User Clicks "Scan Emails"]
    
    K --> L[Get User's Selected Vendors]
    L --> M[For Each Selected Vendor]
    
    M --> N[Build Email Search Query]
    N --> O[Search Gmail API]
    O --> P[Get Email Data]
    
    P --> Q[Send to Gemini AI]
    Q --> R{Gemini Analysis}
    
    R -->|is_invoice: true| S[Extract Invoice Data]
    R -->|is_invoice: false| T[Skip Email]
    
    S --> U[Save to Database]
    T --> V[Log: Not an Invoice]
    
    U --> W[Process Next Email]
    V --> W
    
    W --> X{More Emails?}
    X -->|Yes| Q
    X -->|No| Y{More Vendors?}
    
    Y -->|Yes| M
    Y -->|No| Z[Scan Complete]
    
    Z --> AA[Show Results Dashboard]
    
    style A fill:#e1f5fe
    style C fill:#fff3e0
    style Q fill:#f3e5f5
    style S fill:#e8f5e8
    style Z fill:#e3f2fd
```

## 🗄️ Database Schema

### User Vendor Preferences Collection
```javascript
// Collection: user_vendor_preferences
{
  "_id": "ObjectId",
  "user_id": "string",
  "selected_vendors": [
    {
      "vendor_id": "ObjectId",
      "vendor_name": "string",
      "email_domains": ["domain1.com", "domain2.com"],
      "is_custom": false
    }
  ],
  "custom_vendors": [
    {
      "vendor_id": "ObjectId", 
      "vendor_name": "string",
      "email_domains": ["custom@domain.com"],
      "category": "software",
      "is_custom": true,
      "created_at": "datetime"
    }
  ],
  "scan_settings": {
    "days_back": 30,
    "include_attachments": true,
    "auto_scan_enabled": false
  },
  "created_at": "datetime",
  "updated_at": "datetime"
}
```

### Enhanced Vendor Collection
```javascript
// Collection: vendors (existing + new fields)
{
  "_id": "ObjectId",
  "name": "string",
  "display_name": "string", 
  "category": "string",
  "typical_email_domains": ["array"],
  "typical_email_addresses": ["array"],
  "is_global": true,  // NEW: true for system vendors
  "created_by": "string",  // NEW: user_id who created
  "is_active": true,
  "created_at": "datetime",
  "updated_at": "datetime"
}
```

## 🚀 Implementation Plan

### Phase 1: Database & Backend Structure

#### 1.1 Create User Preferences Collection
```python
# New model: models/user_vendor_preferences.py
class UserVendorPreferences(BaseModel):
    user_id: str
    selected_vendors: List[Dict] = []
    custom_vendors: List[Dict] = []
    scan_settings: Dict = {
        "days_back": 30,
        "include_attachments": True,
        "auto_scan_enabled": False
    }
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
```

#### 1.2 Enhanced Vendor Model
```python
# Update models/vendor.py
class VendorModel(BaseModel):
    # ... existing fields ...
    is_global: bool = True  # NEW: system vs user-created
    created_by: Optional[str] = None  # NEW: user_id
    usage_count: int = 0  # NEW: track popularity
```

### Phase 2: Backend API Endpoints

#### 2.1 Vendor Management Routes
```python
# routes/vendors.py (NEW FILE)
@router.get("/vendors/available")
async def get_available_vendors(current_user: UserModel = Depends(get_current_user))

@router.get("/vendors/user-preferences") 
async def get_user_vendor_preferences(current_user: UserModel = Depends(get_current_user))

@router.post("/vendors/preferences")
async def save_user_vendor_preferences(
    preferences: UserVendorPreferencesRequest,
    current_user: UserModel = Depends(get_current_user)
)

@router.post("/vendors/custom")
async def add_custom_vendor(
    vendor_data: CustomVendorRequest,
    current_user: UserModel = Depends(get_current_user)
)

@router.post("/vendors/scan-selected")
async def scan_selected_vendor_emails(
    current_user: UserModel = Depends(get_current_user)
)
```

#### 2.2 Simplified Email Processing
```python
# services/invoice_processor.py - NEW METHOD
async def process_user_preferred_vendors(self, user_id: str, email_account_id: str) -> Dict:
    """
    FAST TARGETED SCANNING:
    1. Get user's selected vendors from preferences
    2. For each vendor, build targeted email search
    3. Send emails directly to Gemini
    4. Save only invoices (is_invoice: true)
    5. Move to next vendor
    """
```

### Phase 3: Frontend Implementation

#### 3.1 Vendor Selection Page
```typescript
// components/VendorSelection.tsx (NEW)
interface Vendor {
  id: string;
  name: string;
  display_name: string;
  category: string;
  email_domains: string[];
  is_global: boolean;
  is_selected: boolean;
}

const VendorSelection: React.FC = () => {
  const [availableVendors, setAvailableVendors] = useState<Vendor[]>([]);
  const [selectedVendors, setSelectedVendors] = useState<string[]>([]);
  const [customVendor, setCustomVendor] = useState({
    name: '',
    email_domains: '',
    category: 'software'
  });
  
  // Component logic for vendor selection and custom vendor addition
}
```

#### 3.2 Enhanced Navigation
```typescript
// Update App.tsx to include Vendor Preferences in sidebar
const sidebarItems = [
  { path: '/dashboard', icon: HomeIcon, label: 'Dashboard' },
  { path: '/vendor-preferences', icon: SettingsIcon, label: 'Vendor Preferences' }, // NEW
  { path: '/email-accounts', icon: Mail, label: 'Email Accounts' },
  { path: '/invoices', icon: FileText, label: 'Invoices' },
  { path: '/invoices/review', icon: CheckCircle, label: 'Review Invoices' }
];
```

### Phase 4: Fast Email Processing

#### 4.1 Optimized Email Search
```python
# Enhanced email search for specific vendors
async def search_vendor_emails(self, vendor: Dict, days_back: int = 30) -> List[Dict]:
    """
    FAST VENDOR-SPECIFIC SEARCH:
    - Build targeted query using vendor email domains
    - Use Gmail API with specific date range
    - Return only relevant emails
    """
    email_domains = vendor.get('typical_email_domains', [])
    email_addresses = vendor.get('typical_email_addresses', [])
    
    # Build targeted query
    query_parts = []
    for domain in email_domains:
        query_parts.append(f"from:{domain}")
    for email in email_addresses:
        query_parts.append(f"from:{email}")
    
    if not query_parts:
        return []
    
    vendor_query = f"({' OR '.join(query_parts)})"
    since_date = (datetime.utcnow() - timedelta(days=days_back)).strftime('%Y/%m/%d')
    final_query = f"{vendor_query} after:{since_date}"
    
    # Execute search
    messages = self.email_scanner.service.users().messages().list(
        userId='me',
        q=final_query,
        maxResults=50  # Limit for speed
    ).execute()
    
    return messages.get('messages', [])
```

#### 4.2 Streamlined Gemini Processing
```python
# Simplified Gemini prompt for fast processing
GEMINI_FAST_PROMPT = """
Analyze this email quickly and determine if it's an invoice.

EMAIL: {email_content}

Return JSON only:
{
    "is_invoice": true/false,
    "subject": "email subject",
    "vendor_name": "company name or null",
    "amount": 100.50 or null,
    "currency": "USD" or null,
    "invoice_date": "YYYY-MM-DD" or null,
    "confidence_score": 0.8
}

Rules: true only for actual invoices/payments, false for requests/marketing.
"""
```

### Phase 5: Code Cleanup

#### 5.1 Remove Old Code
```python
# REMOVE these methods from invoice_processor.py:
# - _is_non_invoice_email() - COMPLETELY REMOVE
# - process_user_emails() - REPLACE with new method
# - process_filtered_emails() - REMOVE
# - _scan_vendor_specific_emails() - REMOVE
# - process_all_invoice_emails() - REMOVE

# KEEP only:
# - process_user_preferred_vendors() - NEW MAIN METHOD
# - _save_gemini_invoice() - ENHANCED
# - _process_single_invoice() - SIMPLIFIED
```

#### 5.2 Simplified Processing Flow
```python
# NEW MAIN PROCESSING FLOW
async def process_user_preferred_vendors(self, user_id: str, email_account_id: str) -> Dict:
    """
    FAST TARGETED PROCESSING:
    1. Get user preferences
    2. For each selected vendor:
       - Search vendor emails (fast, targeted)
       - Send to Gemini (direct analysis)
       - Save if invoice (is_invoice: true)
       - Log progress clearly
    3. Return results
    """
```

## 🎯 Key Benefits

1. **Speed**: Only scan user-selected vendors
2. **Accuracy**: Gemini makes all decisions, no pre-filtering
3. **User Control**: Users choose exactly which vendors to scan
4. **Flexibility**: Custom vendor addition
5. **Clean Code**: Remove all complex pre-filtering logic
6. **Clear Logging**: See exactly what's happening

## 📋 Implementation Checklist

- [ ] Create user_vendor_preferences collection
- [ ] Update vendor model with new fields
- [ ] Create vendor management API endpoints
- [ ] Build VendorSelection frontend component
- [ ] Add vendor preferences to sidebar navigation
- [ ] Implement fast vendor-specific email search
- [ ] Simplify Gemini processing
- [ ] Remove old pre-filtering code
- [ ] Test complete user flow
- [ ] Verify performance improvements

## 🚀 Next Steps

1. Start with database schema updates
2. Create backend API endpoints
3. Build frontend vendor selection
4. Implement fast email processing
5. Remove old code
6. Test and optimize 