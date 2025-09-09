# Invoice Management System - Backend

## Overview

A comprehensive invoice management system with AI-powered invoice extraction, Google Drive integration, and automated email processing. Built with FastAPI, MongoDB, and Google Gemini AI.

## 🚀 Features

### Core Functionality
- **AI-Powered Invoice Processing**: Uses Google Gemini AI for intelligent invoice data extraction
- **Email Integration**: Automatic scanning of Gmail accounts for invoices
- **Text-Based Invoice Processing**: Extract invoices from email content without PDF attachments
- **Google Drive Integration**: Automatic backup to Google Drive with organized folder structure
- **Multi-User Support**: User authentication and data isolation
- **Vendor Management**: Intelligent vendor detection and categorization

### AI Capabilities
- **Gemini 2.5-flash**: Latest AI model for invoice analysis
- **Multi-format Support**: PDF, images, email content, and links
- **Fallback Processing**: Regex-based extraction when AI fails
- **Confidence Scoring**: Quality assessment of extracted data

### Storage Solutions
- **Local Storage**: Traditional file system storage
- **Google Drive**: Cloud backup with organized folder structure
- **MongoDB**: Document database for invoice metadata
- **Hybrid Approach**: Combines local and cloud storage seamlessly

## 🏗️ Architecture

### Technology Stack
- **Framework**: FastAPI (Python 3.8+)
- **Database**: MongoDB with Motor async driver
- **AI Service**: Google Gemini API
- **Authentication**: Google OAuth 2.0
- **File Storage**: Local filesystem + Google Drive API
- **Background Tasks**: Celery + Redis

### Service Architecture
```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Email Scanner │    │ Invoice Processor│    │  Gemini AI     │
│                 │───▶│                 │───▶│  Service       │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         ▼                       ▼                       ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│  Google Drive   │    │   MongoDB       │    │  Local Storage  │
│   Service       │    │   Database      │    │   Service       │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

## 📁 Project Structure

```
backend/
├── core/                    # Core configuration and database
├── models/                  # Data models and schemas
├── routes/                  # API endpoints
├── services/                # Business logic services
├── uploads/                 # Local file storage
├── docs/                    # Documentation
├── scripts/                 # Utility scripts
└── tests/                   # Test files
```

## 🛠️ Installation

### Prerequisites
- Python 3.8+
- MongoDB
- Redis (for background tasks)
- Google Cloud Project with OAuth credentials

### Environment Setup
```bash
# Clone the repository
git clone <repository-url>
cd backend

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Set environment variables
cp .env.example .env
# Edit .env with your configuration
```

### Environment Variables
```bash
# Database
MONGODB_URI=mongodb://localhost:27017
MONGODB_DB=invoice

# Google OAuth
GOOGLE_CLIENT_ID=your_client_id
GOOGLE_CLIENT_SECRET=your_client_secret
GOOGLE_REDIRECT_URI=http://localhost:5173/auth/callback

# AI Services
GEMINI_API_KEY=your_gemini_api_key

# Security
JWT_SECRET_KEY=your_jwt_secret
SESSION_SECRET=your_session_secret

# Redis (for background tasks)
REDIS_URL=redis://localhost:6379
```

### Database Setup
```bash
# Start MongoDB
mongod

# Create database and collections
python -c "
from core.database import connect_to_mongo
import asyncio
asyncio.run(connect_to_mongo())
print('Database connected successfully!')
"
```

## 🚀 Running the Application

### Development Mode
```bash
# Start the FastAPI server
uvicorn main:app --reload --host 0.0.0.0 --port 8000

# Start Redis (for background tasks)
redis-server

# Start Celery worker (in another terminal)
celery -A services.celery_app worker --loglevel=info
```

### Production Mode
```bash
# Build and run with Docker
docker build -t invoice-backend .
docker run -p 8000:8000 invoice-backend

# Or use gunicorn
gunicorn main:app -w 4 -k uvicorn.workers.UvicornWorker
```

## 📚 API Documentation

### Interactive Docs
Once running, visit:
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

### Key Endpoints
- **Authentication**: `/auth/*`
- **Invoices**: `/api/invoices/*`
- **Email Accounts**: `/api/email-accounts/*`
- **Text Invoice Processing**: `/api/invoices/process-text-invoice`
- **Vendors**: `/api/vendors/*`

## 🔧 Configuration

### Google OAuth Setup
1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select existing
3. Enable Google+ API and Gmail API
4. Create OAuth 2.0 credentials
5. Add redirect URIs to authorized redirects
6. Set environment variables

### Gemini AI Setup
1. Visit [Google AI Studio](https://aistudio.google.com/app/apikey)
2. Create API key
3. Set `GEMINI_API_KEY` environment variable

### Google Drive Integration
1. Enable Google Drive API in Google Cloud Console
2. Ensure OAuth scope includes `https://www.googleapis.com/auth/drive.file`
3. The system automatically creates organized folder structure

## 🧪 Testing

### Run Test Suites
```bash
# Text-based invoice processing
python test_text_invoice_processing.py

# Google Drive integration
python test_drive_integration.py

# Database connectivity
python check_db.py

# Vendor synchronization
python test_vendor_sync.py
```

### Test Coverage
- **Unit Tests**: Individual service testing
- **Integration Tests**: End-to-end workflow testing
- **API Tests**: Endpoint functionality testing
- **AI Tests**: Gemini processing validation

## 📊 Monitoring

### Logging
- **Structured Logging**: JSON format for easy parsing
- **Log Levels**: DEBUG, INFO, WARNING, ERROR
- **File Rotation**: Automatic log management
- **Performance Metrics**: Response times and throughput

### Health Checks
- **Database Connectivity**: MongoDB connection status
- **AI Service Status**: Gemini API availability
- **Drive Service Status**: Google Drive API health
- **System Resources**: Memory, CPU, and disk usage

## 🔒 Security

### Authentication & Authorization
- **JWT Tokens**: Secure token-based authentication
- **OAuth 2.0**: Google account integration
- **User Isolation**: Data separation between users
- **Role-Based Access**: Future implementation planned

### Data Protection
- **Input Validation**: Pydantic schema validation
- **SQL Injection Prevention**: MongoDB parameterized queries
- **File Upload Security**: Type and size validation
- **HTTPS Enforcement**: Production requirement

## 🚀 Deployment

### Docker Deployment
```dockerfile
FROM python:3.9-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .
EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### Kubernetes Deployment
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: invoice-backend
spec:
  replicas: 3
  selector:
    matchLabels:
      app: invoice-backend
  template:
    metadata:
      labels:
        app: invoice-backend
    spec:
      containers:
      - name: invoice-backend
        image: invoice-backend:latest
        ports:
        - containerPort: 8000
```

## 📈 Performance

### Optimization Features
- **Async Processing**: Non-blocking I/O operations
- **Connection Pooling**: Database connection optimization
- **Caching**: Redis-based caching layer
- **Background Tasks**: Celery for heavy operations

### Scaling Considerations
- **Horizontal Scaling**: Multiple worker instances
- **Load Balancing**: Nginx or cloud load balancer
- **Database Sharding**: MongoDB cluster setup
- **CDN Integration**: Static file delivery

## 🔄 Updates & Maintenance

### Regular Maintenance
- **Dependency Updates**: Security patches and feature updates
- **Database Optimization**: Index maintenance and cleanup
- **Log Rotation**: Archive old logs
- **Performance Monitoring**: Track system metrics

### Backup Strategy
- **Database Backups**: MongoDB dump/restore
- **File Backups**: Local and Google Drive redundancy
- **Configuration Backups**: Environment and config files
- **Disaster Recovery**: Complete system restoration

## 🤝 Contributing

### Development Workflow
1. Fork the repository
2. Create feature branch
3. Make changes with tests
4. Submit pull request
5. Code review and merge

### Code Standards
- **Python**: PEP 8 compliance
- **Type Hints**: Full type annotation
- **Documentation**: Docstrings for all functions
- **Testing**: Minimum 80% coverage

## 📞 Support

### Getting Help
- **Documentation**: Check `/docs` folder
- **Issues**: GitHub issue tracker
- **Discussions**: GitHub discussions
- **Email**: Contact development team

### Common Issues
- **OAuth Errors**: Check redirect URIs and scopes
- **AI Processing Failures**: Verify Gemini API key
- **Drive Storage Issues**: Check OAuth permissions
- **Database Connection**: Verify MongoDB status

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🙏 Acknowledgments

- **Google Gemini AI**: Advanced AI capabilities
- **FastAPI**: Modern web framework
- **MongoDB**: Flexible document database
- **Open Source Community**: Libraries and tools

---

**Note**: This system requires proper Google OAuth setup and API keys for full functionality. Ensure all environment variables are configured before running. 