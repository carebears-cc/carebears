#!/bin/bash

# Exit on error
set -e

echo "Installing dependencies for carebears app on Ubuntu 24.04..."

# Update system
sudo apt update
sudo apt upgrade -y

# Install build dependencies
sudo apt install -y build-essential libssl-dev zlib1g-dev \
libbz2-dev libreadline-dev libsqlite3-dev curl \
libncursesw5-dev xz-utils tk-dev libxml2-dev libxmlsec1-dev \
libffi-dev liblzma-dev

# Install Python 3.13
echo "Installing Python 3.13..."
cd /tmp
curl -O https://www.python.org/ftp/python/3.13.0/Python-3.13.0.tar.xz
tar -xf Python-3.13.0.tar.xz
cd Python-3.13.0
./configure --enable-optimizations
make -j $(nproc)
sudo make altinstall

# Verify Python installation
python3.13 --version

# Install uv
echo "Installing uv..."
curl -fsSL https://raw.githubusercontent.com/astral-sh/uv/main/install.sh | bash

# Create and activate virtual environment
echo "Setting up virtual environment..."
cd $HOME/carebears/app
/usr/local/bin/python3.13 -m venv .venv
source .venv/bin/activate

# Install dependencies using uv
echo "Installing dependencies with uv..."
uv pip install -e .

echo "Installation complete! To run the application:"
echo "1. Activate the virtual environment: source .venv/bin/activate"
echo "2. Run the application: uvicorn main:app --reload"