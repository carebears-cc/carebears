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

# Install Nginx if not already installed
if ! command -v nginx &> /dev/null; then
    echo "Installing Nginx..."
    if command -v apt &> /dev/null; then
        sudo apt update
        sudo apt install -y nginx
    else
        echo "Please install Nginx manually for your system."
        exit 1
    fi
fi

# Configure Nginx for the application
echo "Configuring Nginx for the application..."
sudo cp nginx_config /etc/nginx/sites-available/carebears
sudo ln -sf /etc/nginx/sites-available/carebears /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default  # Remove default config
sudo nginx -t  # Test configuration
sudo systemctl restart nginx

# Create data directory with correct permissions
echo "Creating data directory..."
mkdir -p data
sudo chown -R www-data:www-data data
chmod 755 data

# Create systemd service file for the application
echo "Creating systemd service file..."
cat > carebears.service << EOF
[Unit]
Description=CareBears Uvicorn Service
After=network.target

[Service]
User=www-data
Group=www-data
WorkingDirectory=$(pwd)
Environment="PATH=$(pwd)/.venv/bin"
ExecStartPre=/bin/bash -c "source $(pwd)/.env"
ExecStart=$(pwd)/.venv/bin/uvicorn main:app --host 127.0.0.1 --port 8000

[Install]
WantedBy=multi-user.target
EOF

sudo mv carebears.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable carebears.service
sudo systemctl start carebears.service

echo "Installation complete! The application is now running at http://localhost"
echo ""
echo "To control the service:"
echo "- Start: sudo systemctl start carebears"
echo "- Stop: sudo systemctl stop carebears"
echo "- Restart: sudo systemctl restart carebears"
echo "- Status: sudo systemctl status carebears"
