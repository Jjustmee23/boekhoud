#!/bin/bash
# Application deployment script
# Run from the application directory

set -e  # Exit on error

# Check if .env file exists
if [ ! -f ".env" ]; then
    echo "Error: .env file not found! Please create .env file from .env.example"
    exit 1
fi

# Check if SSL certificates exist or prompt to use Let's Encrypt
if [ ! -f "nginx/ssl/fullchain.pem" ] || [ ! -f "nginx/ssl/privkey.pem" ]; then
    echo "SSL certificates not found in nginx/ssl/"
    read -p "Do you want to set up Let's Encrypt certificates? (y/n): " setup_ssl
    
    if [ "$setup_ssl" == "y" ]; then
        # Get domain name
        read -p "Enter your domain name (e.g., example.com): " domain_name
        
        # Install certbot
        apt-get update
        apt-get install -y certbot
        
        # Create directories for certbot verification
        mkdir -p nginx/www/.well-known/acme-challenge
        
        # Start nginx temporarily for domain verification
        docker-compose up -d nginx
        
        # Get certificates
        certbot certonly --webroot -w nginx/www -d $domain_name -d www.$domain_name
        
        # Copy certificates to nginx SSL directory
        mkdir -p nginx/ssl
        cp /etc/letsencrypt/live/$domain_name/fullchain.pem nginx/ssl/
        cp /etc/letsencrypt/live/$domain_name/privkey.pem nginx/ssl/
        
        # Update nginx configuration with correct domain name
        sed -i "s/example.com/$domain_name/g" nginx/conf.d/app.conf
        
        # Stop nginx
        docker-compose down
        
        # Set up auto-renewal
        echo "0 0 * * * certbot renew --quiet && cp /etc/letsencrypt/live/$domain_name/fullchain.pem /opt/invoicing-app/nginx/ssl/ && cp /etc/letsencrypt/live/$domain_name/privkey.pem /opt/invoicing-app/nginx/ssl/ && docker-compose -f /opt/invoicing-app/docker-compose.yml exec nginx nginx -s reload" | crontab -
    else
        echo "Please place your SSL certificates in nginx/ssl/ directory as fullchain.pem and privkey.pem"
        exit 1
    fi
fi

# Build and start the containers
echo "Building and starting containers..."
docker-compose up -d --build

echo "Application deployed successfully!"
echo "-------------------------------"
echo "The application is now running at your domain with HTTPS."
echo "Database backups are stored in /var/lib/docker/volumes/invoicing-app_postgres_data"
echo "To view logs: docker-compose logs -f"
echo "To stop the application: docker-compose down"