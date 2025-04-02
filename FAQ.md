# Frequently Asked Questions (FAQ)

## Deployment Questions

### What's the difference between Docker and direct installation?

**Docker Installation:**
- Easier to set up and manage
- Consistent environment across different servers
- Isolated from the host system
- Easier to update and rollback
- Better for scaling

**Direct Installation:**
- Potentially better performance
- Lower resource usage
- Simpler to debug
- More control over the system
- Might be preferable for single-server setups

Choose Docker if you want simplicity and isolation. Choose direct installation if you prefer control and are comfortable managing system dependencies.

### Which ports need to be open on my firewall?

- Port 80 (HTTP)
- Port 443 (HTTPS)
- Port 22 (SSH) for server administration

All other services (PostgreSQL, Flask application) are only accessible locally.

### How do I renew SSL certificates?

**For Docker installation:**
SSL certificates from Let's Encrypt are automatically renewed through a cron job. No manual action is required.

**For direct installation:**
Certbot sets up automatic renewal via a systemd timer. You can manually renew with:
```bash
sudo certbot renew
```

### How can I troubleshoot database connection issues?

1. Check if PostgreSQL is running:
   ```bash
   # Docker setup
   docker-compose ps db
   
   # Direct installation
   systemctl status postgresql
   ```

2. Verify database connection settings in your `.env` file:
   ```
   # For Docker setup
   DATABASE_URL=postgresql://dbuser:dbpassword@db:5432/invoicing
   
   # For direct installation
   DATABASE_URL=postgresql://dbuser:dbpassword@localhost:5432/invoicing
   ```

3. Test database connection:
   ```bash
   # Docker setup
   docker-compose exec db psql -U dbuser -d invoicing -c "SELECT 1"
   
   # Direct installation
   sudo -u postgres psql -d invoicing -c "SELECT 1"
   ```

### How do I monitor server resources?

You can install monitoring tools such as:

```bash
# Install basic monitoring tools
sudo apt-get install htop iotop

# For more advanced monitoring, consider installing:
# - Netdata: https://learn.netdata.cloud/docs/agent/packaging/installer
# - Prometheus with Grafana
# - Munin
```

### How can I update the application without losing data?

**For Docker installation:**
```bash
cd /opt/invoicing-app
./deployment/update.sh
```

**For direct installation:**
```bash
cd /opt/invoicing-app
git pull
systemctl restart invoicing
```

### How do I back up my data?

**For Docker installation:**
```bash
cd /opt/invoicing-app
./deployment/backup.sh
```

**For direct installation:**
```bash
cd /opt/invoicing-app
./deployment/direct_backup.sh
```

Backups are stored in the `/opt/invoicing-app/backups` directory.

### How can I restore from a backup?

**To restore a database backup:**

For Docker:
```bash
# First, uncompress the backup file if it's compressed
gunzip backup_file.sql.gz

# Then restore
cat backup_file.sql | docker-compose exec -T db psql -U dbuser -d invoicing
```

For direct installation:
```bash
# First, uncompress the backup file if it's compressed
gunzip backup_file.sql.gz

# Then restore
sudo -u postgres psql invoicing < backup_file.sql
```

### How do I add another domain name to my installation?

Edit the Nginx configuration to add the additional domain:

**For Docker installation:**
1. Edit `nginx/conf.d/app.conf` to add the new domain to the `server_name` directive
2. Run `docker-compose restart nginx`

**For direct installation:**
1. Edit `/etc/nginx/sites-available/invoicing` to add the new domain
2. Run `sudo nginx -t` to check the configuration
3. Run `sudo systemctl restart nginx`

### How can I scale my application for higher traffic?

**For Docker installation:**
- Increase the number of workers in the Dockerfile:
  ```
  CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "8", ...]
  ```
- Consider adding a load balancer (e.g., HAProxy, Traefik) in front of multiple application instances

**For direct installation:**
- Increase the worker count in `/etc/systemd/system/invoicing.service`:
  ```
  ExecStart=/opt/invoicing-app/venv/bin/gunicorn --workers 8 --bind 127.0.0.1:5000 main:app
  ```
- Add a second server and set up load balancing

### How do I uninstall the application?

**For Docker installation:**
```bash
cd /opt/invoicing-app
docker-compose down -v  # This will delete all containers and volumes
rm -rf /opt/invoicing-app
```

**For direct installation:**
```bash
sudo systemctl stop invoicing
sudo systemctl disable invoicing
sudo rm /etc/systemd/system/invoicing.service
sudo systemctl daemon-reload
sudo rm -rf /opt/invoicing-app
sudo -u postgres psql -c "DROP DATABASE invoicing;"
sudo -u postgres psql -c "DROP USER dbuser;"
```

### Waar kan ik de broncode van de applicatie vinden?

De broncode van de applicatie is beschikbaar op GitHub:
[https://github.com/Jjustmee23/boekhoud](https://github.com/Jjustmee23/boekhoud)

Als u problemen of vragen heeft, kunt u een issue aanmaken op GitHub of contact opnemen met de ontwikkelaar via het platform.