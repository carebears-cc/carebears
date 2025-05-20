#!/bin/bash

# Define variables
DOMAIN="app.carebears.cc" # Replace with your primary domain
RSA_KEY_SIZE=2048
DATA_PATH="/etc/letsencrypt" # Where Certbot will store its config and certs on the host
EMAIL="vaibhavb@gmail.com" # Replace with your email for urgent renewals

# Ensure directories exist on the host for the named volumes
mkdir -p "$DATA_PATH/conf"
mkdir -p "$DATA_PATH/www"

# Check if certificates already exist
if [ -d "$DATA_PATH/conf/live/$DOMAIN" ]; then
  echo "Existing certificates found for $DOMAIN. Skipping initial certificate generation."
  echo "To force renewal, remove the directory $DATA_PATH/conf/live/$DOMAIN and rerun."
else
  echo "### Requesting Let's Encrypt certificate for $DOMAIN ###"

  # Use --staging for testing to avoid hitting Let's Encrypt rate limits
  # Remove --staging for production
  STAGE_FLAG="--staging"

  # Generate a dummy certificate to allow Nginx to start without real certs
  # This step is often skipped if Nginx is configured to start without SSL first
  # and then reloaded after real certs are obtained.
  # However, if your Nginx config *requires* certs at startup, this is needed.
  echo "### Creating dummy certificate for $DOMAIN ###"
  docker compose run --rm certbot \
    certonly --webroot -w /var/www/certbot \
    --email "$EMAIL" \
    -d "$DOMAIN" -d \
    --rsa-key-size "$RSA_KEY_SIZE" \
    --agree-tos \
    --no-eff-email \
    --force-renewal \
    --dry-run \
    --cert-name "$DOMAIN" || true # Allow it to fail, we just need the folders to be created

  # Stop Nginx if it's running with the real config, as Certbot needs port 80 for the challenge
  echo "### Stopping Nginx to allow Certbot to use port 80 ###"
  docker compose stop nginx

  echo "### Deleting dummy certificate for $DOMAIN ###"
  rm -Rf "$DATA_PATH/conf/live/$DOMAIN"
  rm -Rf "$DATA_PATH/conf/archive/$DOMAIN"
  rm -Rf "$DATA_PATH/conf/renewal/$DOMAIN.conf"

  # Request the real certificate
  echo "### Requesting real Let's Encrypt certificate for $DOMAIN ###"
  docker compose run --rm certbot \
    certonly --webroot -w /var/www/certbot \
    --email "$EMAIL" \
    -d "$DOMAIN" \
    --rsa-key-size "$RSA_KEY_SIZE" \
    --agree-tos \
    --no-eff-email \
    $STAGE_FLAG # Use --staging for testing, remove for production

  echo "### Restarting Nginx with new certificates ###"
  docker compose start nginx
fi

echo "### Done! You can now access your site via HTTPS. ###"
