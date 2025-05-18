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
sudo chown -R carebear:carebear data
chmod 755 data

# Create a separate systemd service file for the application
echo "Creating systemd service file..."
cat > carebears.service.template << 'EOF'
[Unit]
Description=CareBears Uvicorn Service
After=network.target

[Service]
User=carebear
Group=carebear
WorkingDirectory=WORKING_DIR
Environment="PATH=WORKING_DIR/.venv/bin"
EnvironmentFile=WORKING_DIR/.env
ExecStart=WORKING_DIR/.venv/bin/uvicorn main:app --host 127.0.0.1 --port 8000

[Install]
WantedBy=multi-user.target
EOF

# Verify .env file exists before proceeding
if [ ! -f ".env" ]; then
    echo "ERROR: .env file not found!"
    echo "Please create .env file with required environment variables before proceeding."
    echo "Required variables: GOOGLE_API_KEY, LOGFIRE_TOKEN"
    exit 1
fi

# Set absolute paths to avoid systemd issues
APP_DIR="$(pwd)"

# Replace placeholders with actual paths
sed "s|WORKING_DIR|${APP_DIR}|g" carebears.service.template > carebears.service

# Validate the service file before installation
echo "Validating service file..."
cat carebears.service

# Install the service
sudo mv carebears.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable carebears.service

# Check if .env file is readable by the service user
sudo -u carebear test -r "${APP_DIR}/.env" || {
    echo "Warning: .env file is not readable by carebear user"
    sudo chown carebear:carebear "${APP_DIR}/.env"
    sudo chmod 600 "${APP_DIR}/.env"
}

# Start the service and check status
sudo systemctl restart carebears.service
sleep 2
sudo systemctl status carebears.service

echo "Installation complete! The application is now running at http://localhost"
echo ""
echo "To control the service:"
echo "- Start: sudo systemctl start carebears"
echo "- Stop: sudo systemctl stop carebears"
echo "- Restart: sudo systemctl restart carebears"
echo "- Status: sudo systemctl status carebears"
