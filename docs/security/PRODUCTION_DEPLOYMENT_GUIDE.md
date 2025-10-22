# Production Deployment Guide

## Overview

This guide provides step-by-step instructions for deploying Fog Compute to a production environment with comprehensive security hardening.

## Prerequisites

- **Infrastructure:**
  - Linux server (Ubuntu 22.04 LTS recommended)
  - Docker Engine 24.0+
  - Docker Compose 2.20+
  - 4+ CPU cores
  - 8+ GB RAM
  - 100+ GB SSD storage

- **Network:**
  - Domain name with DNS access
  - SSL certificates (Let's Encrypt or commercial)
  - Firewall with port access (80, 443, 22)

- **Accounts:**
  - GitHub account (for CI/CD)
  - Docker Hub or private registry
  - Cloud backup storage (AWS S3, Google Cloud Storage)
  - Monitoring service accounts (optional: Sentry, DataDog)

## Pre-Deployment Security Checklist

### Critical Security Items (MUST BE COMPLETED)

- [ ] **Replace all hardcoded secrets**
  - [ ] Generate new SECRET_KEY (256-bit random)
  - [ ] Set strong database password
  - [ ] Set Redis password
  - [ ] Set Grafana admin password
  - [ ] Configure JWT secret

- [ ] **Configure secrets management**
  - [ ] Set up Docker secrets or Kubernetes secrets
  - [ ] Verify no secrets in git history
  - [ ] Configure secret rotation policy

- [ ] **SSL/TLS configuration**
  - [ ] Obtain SSL certificates
  - [ ] Configure HTTPS enforcement
  - [ ] Test SSL configuration (ssllabs.com)
  - [ ] Set up auto-renewal

- [ ] **Security headers**
  - [ ] Configure Content-Security-Policy
  - [ ] Enable HSTS
  - [ ] Set X-Frame-Options
  - [ ] Set X-Content-Type-Options

- [ ] **Access controls**
  - [ ] Configure firewall rules
  - [ ] Set up SSH key-only access
  - [ ] Disable root login
  - [ ] Configure fail2ban

## Step 1: Server Preparation

### 1.1 Update System

```bash
sudo apt update && sudo apt upgrade -y
sudo reboot
```

### 1.2 Install Docker

```bash
# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# Add user to docker group
sudo usermod -aG docker $USER

# Install Docker Compose
sudo apt install docker-compose-plugin -y

# Verify installation
docker --version
docker compose version
```

### 1.3 Configure Firewall

```bash
# Install UFW
sudo apt install ufw -y

# Allow SSH
sudo ufw allow 22/tcp

# Allow HTTP/HTTPS
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp

# Enable firewall
sudo ufw enable

# Verify rules
sudo ufw status
```

### 1.4 Install fail2ban

```bash
sudo apt install fail2ban -y
sudo systemctl enable fail2ban
sudo systemctl start fail2ban
```

## Step 2: Configure Secrets

### 2.1 Create Docker Secrets

```bash
# Generate secrets
echo $(openssl rand -base64 32) | docker secret create postgres_user -
echo $(openssl rand -base64 32) | docker secret create postgres_password -
echo $(openssl rand -base64 32) | docker secret create jwt_secret -
echo $(openssl rand -base64 32) | docker secret create redis_password -
echo $(openssl rand -base64 32) | docker secret create grafana_password -
```

### 2.2 Create Environment File

```bash
cd /opt/fog-compute
cp config/production/production.env.example .env

# Edit .env with secure values
nano .env
```

**Required Variables:**
```env
SECRET_KEY=<generated-256-bit-secret>
POSTGRES_PASSWORD=<strong-password>
REDIS_PASSWORD=<strong-password>
GRAFANA_ADMIN_PASSWORD=<strong-password>
CORS_ORIGINS=https://yourdomain.com
```

## Step 3: SSL Configuration

### 3.1 Install Certbot

```bash
sudo apt install certbot python3-certbot-nginx -y
```

### 3.2 Obtain SSL Certificate

```bash
# Stop nginx if running
sudo systemctl stop nginx

# Obtain certificate
sudo certbot certonly --standalone \
  -d yourdomain.com \
  -d api.yourdomain.com \
  -d grafana.yourdomain.com \
  --email admin@yourdomain.com \
  --agree-tos \
  --no-eff-email

# Copy certificates to docker volume
sudo mkdir -p /opt/fog-compute/ssl
sudo cp /etc/letsencrypt/live/yourdomain.com/fullchain.pem /opt/fog-compute/ssl/
sudo cp /etc/letsencrypt/live/yourdomain.com/privkey.pem /opt/fog-compute/ssl/
sudo cp /etc/letsencrypt/live/yourdomain.com/chain.pem /opt/fog-compute/ssl/
```

### 3.3 Configure Auto-Renewal

```bash
# Test renewal
sudo certbot renew --dry-run

# Renewal runs automatically via systemd timer
sudo systemctl status certbot.timer
```

## Step 4: Configure DNS

### 4.1 Add DNS Records

Add the following A records to your DNS provider:

```
yourdomain.com            A    <your-server-ip>
api.yourdomain.com        A    <your-server-ip>
grafana.yourdomain.com    A    <your-server-ip>
```

### 4.2 Verify DNS Propagation

```bash
dig yourdomain.com
dig api.yourdomain.com
dig grafana.yourdomain.com
```

## Step 5: Deploy Application

### 5.1 Clone Repository

```bash
cd /opt
sudo git clone https://github.com/yourusername/fog-compute.git
cd fog-compute
```

### 5.2 Build Images

```bash
# Build production images
docker compose -f config/production/docker-compose.prod.yml build

# Verify images
docker images | grep fog
```

### 5.3 Initialize Database

```bash
# Start database only
docker compose -f config/production/docker-compose.prod.yml up -d postgres

# Wait for database to be ready
sleep 10

# Run migrations
docker compose -f config/production/docker-compose.prod.yml exec backend alembic upgrade head
```

### 5.4 Start All Services

```bash
# Start all services
docker compose -f config/production/docker-compose.prod.yml up -d

# Verify all containers are running
docker ps

# Check logs
docker compose -f config/production/docker-compose.prod.yml logs -f
```

## Step 6: Verify Deployment

### 6.1 Health Checks

```bash
# Backend health
curl https://api.yourdomain.com/health

# Frontend health
curl https://yourdomain.com/

# Expected response: 200 OK
```

### 6.2 Run Security Scan

```bash
cd /opt/fog-compute
chmod +x scripts/security/security-scan.sh
./scripts/security/security-scan.sh
```

### 6.3 Test SSL Configuration

Visit: https://www.ssllabs.com/ssltest/analyze.html?d=yourdomain.com

**Target Grade: A+**

### 6.4 Verify Rate Limiting

```bash
# Test rate limiting
for i in {1..100}; do
  curl -I https://api.yourdomain.com/api/auth/login
done

# Should receive 429 Too Many Requests
```

## Step 7: Configure Monitoring

### 7.1 Access Grafana

1. Open: https://grafana.yourdomain.com
2. Login with admin credentials from .env
3. **Change default password immediately**

### 7.2 Configure Alerts

1. Go to Alerting > Alert rules
2. Enable email notifications
3. Configure alert channels (email, Slack, PagerDuty)

### 7.3 Test Alerts

```bash
# Trigger test alert
docker compose -f config/production/docker-compose.prod.yml stop backend

# Should receive alert within 5 minutes

# Restart backend
docker compose -f config/production/docker-compose.prod.yml start backend
```

## Step 8: Configure Backups

### 8.1 Database Backups

```bash
# Edit backup script
nano scripts/backup.sh

# Configure S3 credentials in .env
AWS_ACCESS_KEY_ID=<your-key>
AWS_SECRET_ACCESS_KEY=<your-secret>
BACKUP_S3_BUCKET=fog-compute-backups

# Test backup
docker compose -f config/production/docker-compose.prod.yml exec backup /backup.sh

# Verify backup uploaded to S3
aws s3 ls s3://fog-compute-backups/
```

### 8.2 Schedule Automatic Backups

Backups run automatically via cron in the backup container (2 AM daily).

Verify:
```bash
docker compose -f config/production/docker-compose.prod.yml exec backup crontab -l
```

## Step 9: Security Hardening

### 9.1 Run Security Hardening Script

```bash
chmod +x scripts/security/security-hardening.sh
sudo ./scripts/security/security-hardening.sh
```

### 9.2 Configure SIEM (Optional)

For production environments, integrate with SIEM:
- Splunk
- ELK Stack
- DataDog

### 9.3 Set Up Intrusion Detection

```bash
# Install and configure AIDE
sudo apt install aide -y
sudo aideinit
sudo mv /var/lib/aide/aide.db.new /var/lib/aide/aide.db

# Schedule daily checks
echo "0 3 * * * /usr/bin/aide --check" | sudo crontab -
```

## Step 10: Final Verification

### 10.1 Run Full Test Suite

```bash
# Run production hardening tests
docker compose -f config/production/docker-compose.prod.yml exec backend pytest tests/security/test_production_hardening.py -v

# Expected: All tests pass
```

### 10.2 Performance Benchmarking

```bash
# Run performance tests
docker compose -f config/production/docker-compose.prod.yml exec backend pytest tests/performance/ -v

# Target metrics:
# - API response p95 < 200ms
# - Error rate < 0.1%
# - Uptime > 99.9%
```

### 10.3 Security Audit

```bash
# Run comprehensive security audit
./scripts/security/security-scan.sh

# Review report
cat security-reports/security-scan-*.txt

# Expected: 0 critical issues, < 5 warnings
```

## Post-Deployment

### Monitoring Checklist

- [ ] Set up uptime monitoring (UptimeRobot, Pingdom)
- [ ] Configure log aggregation
- [ ] Set up error tracking (Sentry)
- [ ] Enable APM (Application Performance Monitoring)
- [ ] Configure backup verification

### Maintenance Schedule

- **Daily:** Review logs, check alerts
- **Weekly:** Review security logs, backup verification
- **Monthly:** Security patches, dependency updates
- **Quarterly:** Full security audit, disaster recovery test

### Emergency Contacts

- **DevOps Lead:** devops@yourdomain.com
- **Security Team:** security@yourdomain.com
- **On-Call:** +1-XXX-XXX-XXXX

## Rollback Procedure

If deployment fails:

```bash
# Stop new deployment
docker compose -f config/production/docker-compose.prod.yml down

# Restore from backup
# 1. Restore database
pg_restore -h localhost -U fog_user -d fog_compute backups/latest.dump

# 2. Restart previous version
git checkout <previous-tag>
docker compose -f config/production/docker-compose.prod.yml up -d

# 3. Verify health
curl https://api.yourdomain.com/health
```

## Troubleshooting

### Common Issues

**Issue: Containers won't start**
```bash
# Check logs
docker compose logs -f

# Check resource usage
docker stats

# Verify secrets
docker secret ls
```

**Issue: Database connection errors**
```bash
# Check database logs
docker compose logs postgres

# Verify database is accessible
docker compose exec backend psql -h postgres -U fog_user -d fog_compute

# Check connection pool
docker compose exec backend python -c "from backend.server.database import engine; print(engine.pool.status())"
```

**Issue: SSL certificate errors**
```bash
# Verify certificate validity
openssl x509 -in /opt/fog-compute/ssl/fullchain.pem -noout -dates

# Test SSL configuration
openssl s_client -connect yourdomain.com:443 -servername yourdomain.com

# Renew certificate manually
sudo certbot renew --force-renewal
```

## Support

For production deployment support:
- Documentation: https://docs.fog-compute.io
- Community: https://community.fog-compute.io
- Enterprise Support: enterprise@fog-compute.io

---

**Last Updated:** 2025-10-22
**Version:** 1.0.0
