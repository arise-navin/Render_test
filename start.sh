#!/bin/bash

echo "=================================="
echo "ServiceNow AI Copilot - Launcher"
echo "=================================="
echo ""

# Check if Python is installed
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 is not installed"
    exit 1
fi

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
echo "Activating virtual environment..."
source venv/bin/activate

# Install dependencies
echo "Installing dependencies..."
pip install -r requirements.txt

# Run setup check
echo ""
echo "Running setup check..."
python3 setup.py

# Ask if user wants to start the server
echo ""
read -p "Start the server now? (y/n) " -n 1 -r
echo ""

if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo ""
    echo "Starting ServiceNow AI Copilot..."
    echo "Dashboard: http://127.0.0.1:8000/"
    echo "Press CTRL+C to stop"
    echo ""
    python -m uvicorn main:app --reload
fi
