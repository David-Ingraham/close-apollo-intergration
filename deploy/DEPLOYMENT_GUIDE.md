# DigitalOcean Deployment Guide
Close Apollo Integration - Production Setup

## 🚀 Quick Setup

### 1. Create DigitalOcean Droplet
- **Size**: Basic Droplet ($6/month) - 1 GB RAM, 1 vCPU, 25 GB SSD
- **OS**: Ubuntu 22.04 LTS
- **Options**: Add SSH key, enable monitoring

### 2. Connect and Deploy
```bash
# SSH into your droplet
ssh root@your-droplet-ip

# Download and run setup script
wget https://raw.githubusercontent.com/YOUR_USERNAME/close_apollo_integration/main/deploy/setup_digitalocean.sh
chmod +x setup_digitalocean.sh
./setup_digitalocean.sh
```

### 3. Configure API Keys
```bash
# Edit environment file
sudo -u closeapollo nano /opt/close_apollo_integration/.env

# Add your API keys:
CLOSE_API_KEY=your_actual_close_api_key
APOLLO_API_KEY=your_actual_apollo_api_key
WEBHOOK_URL=https://your-domain.com
```

### 4. Setup Domain & SSL
```bash
# Update Nginx config with your domain
sudo nano /etc/nginx/sites-available/close-apollo
# Replace 'your-domain.com' with your actual domain

# Get SSL certificate
sudo certbot --nginx -d your-domain.com

# Restart services
sudo systemctl restart close-apollo nginx
```

## 📂 File Management

### Directory Structure
```
/opt/close_apollo_integration/
├── app/                    # Application code
├── data/                   # Managed data storage
│   ├── results/           # Enrichment results (7 days)
│   ├── logs/              # Application logs (7 days)
│   ├── webhooks/          # Webhook responses (7 days)
│   └── temp/              # Temporary files (1 day)
├── config/                # Configuration files
└── deploy/                # Deployment scripts
```

### Automatic Cleanup
- **Daily cleanup**: Runs at 2 AM via cron
- **Retention**: 7 days for results/logs/webhooks, 1 day for temp files
- **Manual cleanup**: `python3 file_manager.py cleanup`

## 🔧 Service Management

### Webhook Server
```bash
# Start/stop/restart
sudo systemctl start close-apollo
sudo systemctl stop close-apollo  
sudo systemctl restart close-apollo

# Check status
sudo systemctl status close-apollo

# View logs
sudo journalctl -u close-apollo -f
```

### Run Pipeline
```bash
# Switch to app user
sudo -u closeapollo -i

# Navigate to app directory
cd /opt/close_apollo_integration

# Activate virtual environment
source venv/bin/activate

# Run pipeline
python3 deploy/production_orchestrator.py run --mode production
```

### File Management
```bash
# Check storage usage
python3 file_manager.py usage

# Preview cleanup
python3 file_manager.py cleanup --dry-run

# Run cleanup
python3 file_manager.py cleanup
```

## 🌐 API Endpoints

Your webhook server will be available at:
- **Webhook**: `https://your-domain.com/apollo-webhook`
- **Health**: `https://your-domain.com/webhook-health`
- **Storage**: `https://your-domain.com/storage-usage`

## 📊 Monitoring

### Health Checks
```bash
# Check webhook server health
curl https://your-domain.com/webhook-health

# Check storage usage
curl https://your-domain.com/storage-usage
```

### Log Files
- **Webhook logs**: `/opt/close_apollo_integration/data/logs/webhook_server_YYYYMMDD.log`
- **Pipeline logs**: `/opt/close_apollo_integration/data/logs/orchestrator_YYYYMMDD.log`
- **Cleanup logs**: `/opt/close_apollo_integration/data/logs/cleanup.log`

## 🔒 Security

### Firewall (UFW)
- SSH (port 22) - allowed
- HTTP (port 80) - allowed  
- HTTPS (port 443) - allowed
- All other ports - blocked

### SSL Certificate
- Auto-renewal via certbot
- HTTPS redirect enabled

## 💰 Cost Estimate

**Monthly Costs:**
- DigitalOcean Droplet: $6/month
- Domain name: ~$12/year
- **Total**: ~$7/month

**API Usage:**
- Apollo credits: Variable based on usage
- Close CRM: Based on your plan

## 🆘 Troubleshooting

### Webhook Server Not Starting
```bash
# Check logs
sudo journalctl -u close-apollo -f

# Check port availability
sudo netstat -tlnp | grep :5000

# Restart service
sudo systemctl restart close-apollo
```

### SSL Certificate Issues
```bash
# Renew certificate
sudo certbot renew

# Test renewal
sudo certbot renew --dry-run
```

### Storage Issues
```bash
# Check disk usage
df -h

# Force cleanup
python3 file_manager.py cleanup

# Check largest files
du -sh /opt/close_apollo_integration/data/*
```

## 📞 Support

If you need help:
1. Check the logs first
2. Try restarting services
3. Check firewall/SSL settings
4. Verify API keys in .env file

For pipeline-specific issues, check the orchestrator and individual script logs.
