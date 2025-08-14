#!/bin/bash
# DigitalOcean Deployment Setup Script
# Run this on a fresh Ubuntu droplet

set -e  # Exit on any error

echo "🚀 Setting up Close Apollo Integration on DigitalOcean"
echo "=================================================="

# Update system
echo "📦 Updating system packages..."
sudo apt update && sudo apt upgrade -y

# Install Python and essential packages
echo "🐍 Installing Python and dependencies..."
sudo apt install -y python3 python3-pip python3-venv git nginx supervisor certbot python3-certbot-nginx

# Create application user
echo "👤 Creating application user..."
sudo useradd -m -s /bin/bash closeapollo || echo "User already exists"

# Create application directory
echo "📁 Setting up application directory..."
sudo mkdir -p /opt/close_apollo_integration
sudo chown closeapollo:closeapollo /opt/close_apollo_integration

# Switch to application user for remaining setup
sudo -u closeapollo bash << 'EOF'
cd /opt/close_apollo_integration

# Clone repository (replace with your actual repo URL)
echo "📥 Cloning repository..."
git clone https://github.com/YOUR_USERNAME/close_apollo_integration.git . || echo "Repository already cloned"

# Create virtual environment
echo "🔧 Setting up Python virtual environment..."
python3 -m venv venv
source venv/bin/activate

# Install Python dependencies
echo "📦 Installing Python packages..."
pip install -r deploy/requirements.txt

# Create data directories
echo "📂 Creating data directories..."
python3 file_manager.py setup

# Create environment file template
echo "🔑 Creating environment file template..."
cat > .env << 'ENVEOF'
# CLOSE CRM API KEY
CLOSE_API_KEY=your_close_api_key_here

# APOLLO API KEY  
APOLLO_API_KEY=your_apollo_api_key_here

# PRODUCTION SETTINGS
FLASK_ENV=production
PORT=5000
HOST=0.0.0.0

# WEBHOOK URL (will be your domain)
WEBHOOK_URL=https://your-domain.com

# FILE MANAGEMENT
DATA_RETENTION_DAYS=7
CLEANUP_SCHEDULE=daily
ENVEOF

echo "✅ Environment file created at /opt/close_apollo_integration/.env"
echo "⚠️  IMPORTANT: Edit .env file with your actual API keys!"

EOF

# Setup Nginx
echo "🌐 Configuring Nginx..."
sudo tee /etc/nginx/sites-available/close-apollo << 'NGINXEOF'
server {
    listen 80;
    server_name your-domain.com;  # Replace with your actual domain
    
    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # For webhook timeouts
        proxy_read_timeout 300;
        proxy_connect_timeout 300;
        proxy_send_timeout 300;
    }
    
    # Serve static files directly (if any)
    location /static {
        alias /opt/close_apollo_integration/static;
        expires 1d;
    }
}
NGINXEOF

# Enable the site
sudo ln -sf /etc/nginx/sites-available/close-apollo /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t

# Setup Supervisor for process management
echo "👨‍💼 Configuring Supervisor..."
sudo tee /etc/supervisor/conf.d/close-apollo.conf << 'SUPERVISOREOF'
[program:webhook-server]
command=/opt/close_apollo_integration/venv/bin/python webhook_server.py
directory=/opt/close_apollo_integration
user=closeapollo
autostart=true
autorestart=true
redirect_stderr=true
stdout_logfile=/opt/close_apollo_integration/data/logs/webhook_server.log
stdout_logfile_maxbytes=10MB
stdout_logfile_backups=5
environment=PATH="/opt/close_apollo_integration/venv/bin"

[program:file-cleanup]
command=/opt/close_apollo_integration/venv/bin/python file_manager.py cleanup
directory=/opt/close_apollo_integration
user=closeapollo
autostart=false
autorestart=false
redirect_stderr=true
stdout_logfile=/opt/close_apollo_integration/data/logs/cleanup.log
SUPERVISOREOF

# Setup daily cleanup cron job
echo "⏰ Setting up daily cleanup..."
sudo -u closeapollo bash << 'CRONEOF'
# Add cleanup job to crontab
(crontab -l 2>/dev/null; echo "0 2 * * * cd /opt/close_apollo_integration && /opt/close_apollo_integration/venv/bin/python file_manager.py cleanup") | crontab -
CRONEOF

# Create systemd service for better management
echo "🔧 Creating systemd service..."
sudo tee /etc/systemd/system/close-apollo.service << 'SERVICEEOF'
[Unit]
Description=Close Apollo Integration Webhook Server
After=network.target

[Service]
Type=exec
User=closeapollo
WorkingDirectory=/opt/close_apollo_integration
Environment=PATH=/opt/close_apollo_integration/venv/bin
ExecStart=/opt/close_apollo_integration/venv/bin/python webhook_server.py
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
SERVICEEOF

# Reload systemd and enable service
sudo systemctl daemon-reload
sudo systemctl enable close-apollo

# Start services
echo "🚀 Starting services..."
sudo supervisorctl reread
sudo supervisorctl update
sudo systemctl restart nginx
sudo systemctl start close-apollo

# Setup firewall
echo "🔥 Configuring firewall..."
sudo ufw allow OpenSSH
sudo ufw allow 'Nginx Full'
sudo ufw --force enable

echo ""
echo "✅ SETUP COMPLETE!"
echo "=================="
echo ""
echo "Next steps:"
echo "1. Edit /opt/close_apollo_integration/.env with your API keys"
echo "2. Update domain name in /etc/nginx/sites-available/close-apollo"
echo "3. Get SSL certificate: sudo certbot --nginx -d your-domain.com"
echo "4. Restart services: sudo systemctl restart close-apollo nginx"
echo ""
echo "Service management:"
echo "  Start:   sudo systemctl start close-apollo"
echo "  Stop:    sudo systemctl stop close-apollo"
echo "  Restart: sudo systemctl restart close-apollo"
echo "  Status:  sudo systemctl status close-apollo"
echo "  Logs:    sudo journalctl -u close-apollo -f"
echo ""
echo "File cleanup:"
echo "  Manual:  sudo -u closeapollo python3 /opt/close_apollo_integration/file_manager.py cleanup"
echo "  Preview: sudo -u closeapollo python3 /opt/close_apollo_integration/file_manager.py cleanup --dry-run"
echo "  Usage:   sudo -u closeapollo python3 /opt/close_apollo_integration/file_manager.py usage"
echo ""
echo "🌐 Your webhook URL will be: https://your-domain.com/apollo-webhook"
