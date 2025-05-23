0 12 * * * docker-compose exec certbot certbot renew --quiet && docker-compose restart nginx
