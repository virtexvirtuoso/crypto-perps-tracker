#!/bin/bash

# Derivatives Signals API Startup Script

set -e

echo "=========================================="
echo "  Derivatives Signals API"
echo "=========================================="
echo ""

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "❌ Virtual environment not found. Please run:"
    echo "   python3 -m venv venv"
    echo "   source venv/bin/activate"
    echo "   pip install -r requirements.txt -r requirements-api.txt"
    exit 1
fi

# Activate virtual environment
echo "🔧 Activating virtual environment..."
source venv/bin/activate

# Check if API dependencies are installed
echo "📦 Checking dependencies..."
python -c "import fastapi" 2>/dev/null || {
    echo "❌ FastAPI not found. Installing API dependencies..."
    pip install -r requirements-api.txt
}

# Check if Redis is running (optional)
echo "🔍 Checking Redis..."
if command -v redis-cli &> /dev/null; then
    if redis-cli ping &> /dev/null; then
        echo "✅ Redis is running"
    else
        echo "⚠️  Redis is installed but not running"
        echo "   Start with: redis-server"
        echo "   Or disable in .env: REDIS_ENABLED=false"
    fi
else
    echo "ℹ️  Redis not installed (optional - will use in-memory cache)"
fi

# Check if .env exists
if [ ! -f ".env" ]; then
    echo ""
    echo "⚠️  .env file not found. Creating default..."
    cat > .env << EOF
# Derivatives Signals API Configuration

# Redis (optional - improves performance)
REDIS_ENABLED=false
REDIS_URL=redis://localhost:6379/0

# API
API_HOST=0.0.0.0
API_PORT=8000
DEBUG=false

# Rate Limiting
RATE_LIMIT_ENABLED=true
RATE_LIMIT_RPM=60

# CORS
CORS_ORIGINS=*
EOF
    echo "✅ Created .env with default settings"
fi

echo ""
echo "=========================================="
echo "  Starting API Server"
echo "=========================================="
echo ""
echo "📡 API will be available at:"
echo "   - Main API: http://localhost:8000"
echo "   - Docs: http://localhost:8000/docs"
echo "   - ReDoc: http://localhost:8000/redoc"
echo ""
echo "🔌 WebSocket: ws://localhost:8000/ws/signals/{symbol}"
echo ""
echo "Press Ctrl+C to stop"
echo ""

# Start the API server
python -m uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload
