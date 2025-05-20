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
STAGE_FLAG="" # For production, change to empty string: STAGE_FLAG=""

# --- Step 1: Check if certificates already exist in the Docker volume ---
# We'll use a temporary certbot container to check the volume contents
echo "### Checking for existing certificates in Docker volume for $DOMAIN ###"
if docker compose run --rm "$CERTBOT_SERVICE" test -d "/etc/letsencrypt/live/$DOMAIN"; then
  echo "Existing certificates found in Docker volume for $DOMAIN. Skipping initial certificate generation."
  echo "To force renewal, manually remove the Docker volume 'certbot_etc' and rerun."
  # If you want to force renewal even if certs exist, you'd add 'certbot renew' here
  # docker compose run --rm "$CERTBOT_SERVICE" renew --webroot -w /var/www/certbot --post-hook "docker compose restart $NGINX_SERVICE"
else
  echo "### No existing certificates found. Proceeding with initial request for $DOMAIN and $WWW_DOMAIN ###"

  # --- Step 2: Create dummy certificates (optional, but good if Nginx requires certs at startup) ---
  # This step ensures the /etc/letsencrypt/live/$DOMAIN/ directory exists in the volume
  # before Nginx tries to mount it.
  echo "### Attempting to create dummy certificates to satisfy Nginx startup ###"
  docker compose run --rm "$CERTBOT_SERVICE" \
    certonly --webroot -w /var/www/certbot \
    --email "$EMAIL" \
    -d "$DOMAIN" -d "$WWW_DOMAIN" \
    --rsa-key-size "$RSA_KEY_SIZE" \
    --agree-tos \
    --no-eff-email \
    --force-renewal \
    --dry-run \
    --cert-name "$DOMAIN" || true # Allow failure, just need directory structure

  # --- Step 3: Stop Nginx for ACME challenge ---
  echo "### Stopping Nginx to allow Certbot to use port 80 for challenge ###"
  docker compose stop "$NGINX_SERVICE"

  # --- Step 4: Clean up dummy certificates from the Docker volume ---
  # This command directly interacts with the named Docker volume
  echo "### Cleaning up dummy certificates from Docker volume ###"
  docker compose run --rm "$CERTBOT_SERVICE" rm -Rf "/etc/letsencrypt/live/$Dencrypt/archive/$DOMAIN" "/etc/letsencrypt/renewal/$DOMAIN.conf"OMAIN" "/etc/lets

  # --- Step 5: Request real certificates ---
  echo "### Requesting real Let's Encrypt certificate for $DOMAIN and $WWW_DOMAIN ###"
  docker compose run --rm "$CERTBOT_SERVICE" \
    certonly --webroot -w /var/www/certbot \
    --email "$EMAIL" \
    -d "$DOMAIN" \
    --rsa-key-size "$RSA_KEY_SIZE" \
    --agree-tos \
    --no-eff-email \
    $STAGE_FLAG # Use --staging for testing, remove for production

  # --- Step 6: Restart Nginx with new certificates ---
  echo "### Restarting Nginx with new certificates ###"
  docker compose start "$NGINX_SERVICE"
fi

echo "### Certificate process complete. Check your domain: https://$DOMAIN ###"
