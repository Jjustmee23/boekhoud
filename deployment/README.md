# Deployment Instructions

This directory contains scripts and configuration files for deploying the application on an Ubuntu 22.04 server using Docker and PostgreSQL.

## Prerequisites

- Ubuntu 22.04 server
- Root or sudo access
- Domain name pointing to the server (for SSL setup)
- Git repository with the application code

## Step 1: Server Setup

1. Upload the contents of this repository to your server or clone it from GitHub:
   ```
   git clone https://github.com/Jjustmee23/boekhoud.git /opt/invoicing-app
   cd /opt/invoicing-app
   ```

2. Make the setup script executable and run it:
   ```
   chmod +x deployment/setup.sh
   sudo ./deployment/setup.sh
   ```

3. Log out and log back in to apply Docker group changes, or run:
   ```
   newgrp docker
   ```

## Step 2: Configuration

1. Create an environment file from the template:
   ```
   cp .env.example .env
   ```

2. Edit the .env file with your specific configuration:
   ```
   nano .env
   ```

   Be sure to set:
   - Database credentials
   - Session secret
   - Email configuration 
   - Domain name

## Step 3: Deployment

1. Make the deployment script executable and run it:
   ```
   chmod +x deployment/deploy.sh
   ./deployment/deploy.sh
   ```

2. During deployment, you will be asked if you want to set up Let's Encrypt certificates for SSL. If you choose yes, you'll need to provide your domain name.

## Step 4: Updating the Application

To update the application from GitHub without losing data:

1. Make the update script executable:
   ```
   chmod +x deployment/update.sh
   ```

2. Run the update script:
   ```
   ./deployment/update.sh
   ```

This will:
- Create a database backup
- Pull the latest changes from GitHub
- Rebuild the Docker image if requirements have changed
- Restart the application

## Database Backups

1. Make the backup script executable:
   ```
   chmod +x deployment/backup.sh
   ```

2. Run the backup script manually:
   ```
   ./deployment/backup.sh
   ```

3. To schedule regular backups, add a cron job:
   ```
   crontab -e
   ```

   Add this line to run backups daily at 2 AM:
   ```
   0 2 * * * /opt/invoicing-app/deployment/backup.sh
   ```

## Troubleshooting

- View application logs:
  ```
  cd /opt/invoicing-app
  docker-compose logs -f
  ```

- Check container status:
  ```
  docker-compose ps
  ```

- Access PostgreSQL database:
  ```
  docker-compose exec db psql -U dbuser -d invoicing
  ```

- Restart the application:
  ```
  docker-compose down
  docker-compose up -d
  ```