# Installation Guide for Private Server Deployment

This guide will help you set up this Flask-based invoicing application on your private Ubuntu 22.04 server with Docker, PostgreSQL, and SSL support.

## Prerequisites

Before you begin, make sure you have:

1. A clean Ubuntu 22.04 server with root access
2. A domain name pointing to your server's IP address
3. Basic knowledge of the Linux command line

## Step 1: Initial Server Setup

Connect to your server via SSH:

```bash
ssh root@your-server-ip
```

Update the system:

```bash
apt-get update && apt-get upgrade -y
```

Create a non-root user with sudo privileges (optional but recommended):

```bash
adduser yourusername
usermod -aG sudo yourusername
```

Switch to the new user:

```bash
su - yourusername
```

## Step 2: Clone the Repository

Install Git if it's not already installed:

```bash
sudo apt-get install git -y
```

Clone the repository:

```bash
git clone https://github.com/Jjustmee23/boekhoud.git /opt/invoicing-app
cd /opt/invoicing-app
```

## Step 3: Run the Setup Script

Make the setup script executable and run it:

```bash
chmod +x deployment/setup.sh
sudo ./deployment/setup.sh
```

This script will:
- Update your system
- Install Docker and Docker Compose
- Configure the firewall (UFW)
- Create necessary directories

Log out and log back in, or run:

```bash
newgrp docker
```

## Step 4: Configure Environment Variables

Create your environment file:

```bash
cp .env.example .env
```

Edit the file to add your specific settings:

```bash
nano .env
```

At minimum, configure:
- Database credentials
- Session secret
- Email settings if you're using email functionality
- Domain name

Example:
```
# Database Configuration
POSTGRES_USER=your_db_user
POSTGRES_PASSWORD=your_secure_password
POSTGRES_DB=invoicing
DATABASE_URL=postgresql://your_db_user:your_secure_password@db:5432/invoicing

# Flask Configuration
SESSION_SECRET=your_very_secure_random_string
FLASK_ENV=production

# Domain Settings
DOMAIN_NAME=yourdomain.com
```

## Step 5: Deploy the Application

Make the deployment script executable:

```bash
chmod +x deployment/deploy.sh
```

Run the deployment script:

```bash
./deployment/deploy.sh
```

During deployment, you'll be asked if you want to set up SSL certificates using Let's Encrypt. If you choose yes:

1. Enter your domain name when prompted
2. The script will automatically:
   - Set up Let's Encrypt certificates
   - Configure Nginx with SSL
   - Set up auto-renewal for certificates

If you already have SSL certificates, place them in:
- `nginx/ssl/fullchain.pem`
- `nginx/ssl/privkey.pem`

## Step 6: Set Up Automatic Updates and Backups

Make the scripts executable:

```bash
chmod +x deployment/backup.sh
chmod +x deployment/update.sh
chmod +x deployment/system_update.sh
```

Set up regular database backups (daily at 2 AM):

```bash
(crontab -l 2>/dev/null; echo "0 2 * * * /opt/invoicing-app/deployment/backup.sh") | crontab -
```

Set up regular system updates (weekly on Sunday at 3 AM):

```bash
sudo bash -c '(crontab -l 2>/dev/null; echo "0 3 * * 0 /opt/invoicing-app/deployment/system_update.sh") | crontab -'
```

## Step 7: Updating from GitHub

Whenever you want to update from GitHub without losing data:

```bash
cd /opt/invoicing-app
./deployment/update.sh
```

This will:
1. Create a database backup
2. Pull the latest changes from GitHub
3. Rebuild the application if necessary
4. Restart the services

## Troubleshooting

### Check Application Logs

```bash
cd /opt/invoicing-app
docker-compose logs -f
```

### Check Container Status

```bash
docker-compose ps
```

### Check Database Connection

```bash
docker-compose exec db psql -U your_db_user -d invoicing
```

### Restart the Application

```bash
docker-compose down
docker-compose up -d
```

### View Nginx Logs

```bash
docker-compose logs nginx
```

### Check SSL Certificate Status

```bash
certbot certificates
```

## Security Recommendations

1. **Keep your server updated**: Regular updates are critical for security.
2. **Secure database passwords**: Use strong, unique passwords.
3. **Restrict SSH access**: Consider using key-based authentication only.
4. **Regular backups**: Test your backup restore process occasionally.
5. **Firewall configuration**: Only open ports that are necessary.
6. **Monitoring**: Consider setting up monitoring for your server.

## Advanced Configuration

For more advanced configuration options, check the following files:

- `docker-compose.yml`: Adjust container settings.
- `nginx/conf.d/app.conf`: Customize Nginx settings.
- `Dockerfile`: Modify the container build process.

## Support

If you encounter any issues, please:

1. Check the logs as described in the troubleshooting section
2. Refer to the project documentation
3. Create an issue on the GitHub repository: https://github.com/Jjustmee23/boekhoud