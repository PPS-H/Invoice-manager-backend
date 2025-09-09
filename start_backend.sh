#!/bin/bash

# Invoice Management Backend Startup Script
# This script starts all required services for the backend

echo "🎯 Starting Invoice Management Backend"
echo "======================================"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if we're in the right directory
if [ ! -f "main.py" ]; then
    print_error "Please run this script from the backend directory"
    exit 1
fi

# Function to check if a service is running
check_service() {
    local service_name=$1
    local command=$2
    
    if eval "$command" > /dev/null 2>&1; then
        print_success "$service_name is running"
        return 0
    else
        print_warning "$service_name is not running"
        return 1
    fi
}

# Function to start a service
start_service() {
    local service_name=$1
    local start_command=$2
    local check_command=$3
    
    print_status "Starting $service_name..."
    
    if eval "$start_command" > /dev/null 2>&1; then
        sleep 2
        if check_service "$service_name" "$check_command"; then
            print_success "$service_name started successfully"
            return 0
        else
            print_error "$service_name failed to start"
            return 1
        fi
    else
        print_error "Failed to start $service_name"
        return 1
    fi
}

# Step 1: Check and start Redis
print_status "Step 1: Checking Redis..."
if check_service "Redis" "redis-cli ping"; then
    print_success "Redis is already running"
else
    print_status "Starting Redis..."
    if sudo systemctl start redis-server; then
        sleep 2
        if check_service "Redis" "redis-cli ping"; then
            print_success "Redis started successfully"
        else
            print_error "Redis failed to start"
            exit 1
        fi
    else
        print_error "Failed to start Redis. Please check your system."
        exit 1
    fi
fi

# Step 2: Start Celery Worker
print_status "Step 2: Starting Celery Worker..."
if check_service "Celery Worker" "ps aux | grep -v grep | grep 'celery.*worker'"; then
    print_success "Celery Worker is already running"
else
    print_status "Starting Celery Worker in background..."
    python3 start_celery_worker.py &
    CELERY_WORKER_PID=$!
    sleep 3
    
    if check_service "Celery Worker" "ps aux | grep -v grep | grep 'celery.*worker'"; then
        print_success "Celery Worker started successfully (PID: $CELERY_WORKER_PID)"
    else
        print_error "Celery Worker failed to start"
        exit 1
    fi
fi

# Step 3: Start Celery Beat
print_status "Step 3: Starting Celery Beat..."
if check_service "Celery Beat" "ps aux | grep -v grep | grep 'celery.*beat'"; then
    print_success "Celery Beat is already running"
else
    print_status "Starting Celery Beat in background..."
    python3 start_automatic_cleanup.py &
    CELERY_BEAT_PID=$!
    sleep 3
    
    if check_service "Celery Beat" "ps aux | grep -v grep | grep 'celery.*beat'"; then
        print_success "Celery Beat started successfully (PID: $CELERY_BEAT_PID)"
    else
        print_error "Celery Beat failed to start"
        exit 1
    fi
fi

# Step 4: Start FastAPI Server
print_status "Step 4: Starting FastAPI Server..."
if check_service "FastAPI Server" "ps aux | grep -v grep | grep 'python.*main.py'"; then
    print_success "FastAPI Server is already running"
else
    print_status "Starting FastAPI Server..."
    print_status "Server will start in foreground. Press Ctrl+C to stop."
    print_status "API will be available at: http://localhost:8000"
    print_status "API docs will be available at: http://localhost:8000/docs"
    
    # Start FastAPI server in foreground
    python3 main.py
fi

# Cleanup function
cleanup() {
    print_status "Stopping services..."
    if [ ! -z "$CELERY_WORKER_PID" ]; then
        kill $CELERY_WORKER_PID 2>/dev/null
    fi
    if [ ! -z "$CELERY_BEAT_PID" ]; then
        kill $CELERY_BEAT_PID 2>/dev/null
    fi
    print_status "Services stopped"
    exit 0
}

# Set up signal handlers
trap cleanup SIGINT SIGTERM

print_success "All services started successfully!"
print_status "Backend is ready to handle multiple users"
print_status "Press Ctrl+C to stop all services"