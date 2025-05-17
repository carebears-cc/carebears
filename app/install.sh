#!/bin/bash

# Exit on error
set -e

echo "Installing carebears app..."

# Check if Python 3.13+ is available
if ! command -v python3 &> /dev/null || [[ $(python3 --version | cut -d' ' -f2) < "3.13" ]]; then
    echo "Python 3.13 or higher is required but not found."
    
    # Check if running on Ubuntu/Debian
    if command -v apt &> /dev/null; then
        echo "Installing Python dependencies on Ubuntu/Debian..."
        # Install deadsnakes PPA for Ubuntu to get newer Python versions
        sudo apt update
        sudo apt install -y software-properties-common
        sudo add-apt-repository -y ppa:deadsnakes/ppa
        sudo apt update
        sudo apt install -y python3.13 python3.13-venv python3.13-dev
    else
        echo "Please install Python 3.13 or higher manually for your system."
        exit 1
    fi
fi

# Set up virtual environment
echo "Setting up virtual environment..."
python3.13 -m venv .venv
source .venv/bin/activate

# Install the package
echo "Installing the app and its dependencies..."
pip install -e .

echo "Installation complete! To run the application:"
echo "1. Activate the virtual environment: source .venv/bin/activate"
echo "2. Run the application: uvicorn main:app --reload"