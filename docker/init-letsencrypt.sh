#!/bin/bash
# Define variables
DOMAIN="app.carebears.cc"
RSA_KEY_SIZE=2048
EMAIL="vaibhavb@gmail.com"
# Define the Docker Compose service names for easier reference
NGINX_SERVICE="nginx"
CERTBOT_SERVICE="certbot"
# Use --staging for testing to avoid hitting Let's Encrypt rate limits
# Remove --staging for production
STAGE_FLAG="--staging" # For production, change to empty string: STAGE_FLAG=""

# --- Step 1: Check if certificates already exist in the Docker volume ---
echo "### Checking for existing certificates in Docker volume for $DOMAIN ###"
if docker compose run --rm "$CERTBOT_SERVICE" test -d "/etc/letsencrypt/live/$DOMAIN"; then
  echo "Existing certificates found in Docker volume for $DOMAIN. Skipping initial certificate generation."
  echo "To force renewal, manually remove the Docker volume 'certbot_etc' and rerun."
  # If you want to force renewal even if certs exist, you'd add 'certbot renew' here
  # docker compose run --rm "$CERTBOT_SERVICE" renew --webroot -w /var/www/certbot --post-hook "docker compose restart $NGINX_SERVICE"
else
  echo "### No existing certificates found. Proceeding with initial request for $DOMAIN ###"
  
  # --- Step 2: Start Nginx with a basic configuration ---
  echo "### Starting Nginx with temporary configuration ###"
  docker compose up -d "$NGINX_SERVICE"
  
  # --- Step 3: Wait for Nginx to start ---
  echo "### Waiting for Nginx to initialize ###"
  sleep 10
  
  # --- Step 4: Request real certificates ---
  echo "### Requesting Let's Encrypt certificate for $DOMAIN ###"
  docker compose run --rm "$CERTBOT_SERVICE" \
    certonly --webroot -w /var/www/certbot \
    --email "$EMAIL" \
    -d "$DOMAIN" \
    --rsa-key-size "$RSA_KEY_SIZE" \
    --agree-tos \
    --no-eff-email \
    $STAGE_FLAG # Use --staging for testing, remove for production
  
  # --- Step 5: Restart Nginx with new certificates ---
  echo "### Restarting Nginx with new certificates ###"
  docker compose restart "$NGINX_SERVICE"
fi

echo "### Certificate process complete. Check your domain: https://$DOMAIN ###"
