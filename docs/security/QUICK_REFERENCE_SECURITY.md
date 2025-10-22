# Security Quick Reference Guide

## Critical Commands

### Security Scanning
```bash
# Run comprehensive security scan
./scripts/security/security-scan.sh

# Check for secrets in codebase
git secrets --scan

# Scan Python dependencies
pip-audit

# Scan Node.js dependencies
npm audit

# Scan Rust dependencies
cargo audit
```

### Docker Security
```bash
# Scan Docker image for vulnerabilities
trivy image fog-backend:latest

# Check container security
docker scan fog-backend:latest

# Verify non-root user
docker inspect fog-backend | grep -i user
```

### SSL/TLS
```bash
# Test SSL configuration
openssl s_client -connect yourdomain.com:443 -servername yourdomain.com

# Check certificate expiration
openssl x509 -in /etc/ssl/certs/cert.pem -noout -dates

# Renew Let's Encrypt certificate
sudo certbot renew

# Test SSL with ssllabs
curl -s "https://api.ssllabs.com/api/v3/analyze?host=yourdomain.com"
```

### Monitoring
```bash
# Check service health
curl https://api.yourdomain.com/health

# View real-time logs
docker compose logs -f

# Check Prometheus targets
curl http://localhost:9090/api/v1/targets

# Check rate limiting
curl -I https://api.yourdomain.com/api/auth/login
```

## Security Checklist

### Before Deployment
- [ ] Replace SECRET_KEY
- [ ] Set strong database password
- [ ] Configure SSL certificates
- [ ] Enable HTTPS enforcement
- [ ] Configure firewall rules
- [ ] Set up fail2ban
- [ ] Configure security headers
- [ ] Enable rate limiting
- [ ] Set up monitoring
- [ ] Configure backups

### Weekly Tasks
- [ ] Review security logs
- [ ] Check for failed login attempts
- [ ] Verify backup completion
- [ ] Update dependencies
- [ ] Review access logs
- [ ] Check SSL expiration
- [ ] Test disaster recovery

### Monthly Tasks
- [ ] Run security scan
- [ ] Update all dependencies
- [ ] Review and rotate secrets
- [ ] Test backup restoration
- [ ] Review user permissions
- [ ] Update security documentation

## Common Security Issues

### 1. Hardcoded Secrets
**Problem:** Credentials in source code
**Solution:** Use environment variables or Docker secrets
```bash
# Generate secure secret
openssl rand -base64 32

# Set environment variable
export SECRET_KEY=$(openssl rand -base64 32)

# Create Docker secret
echo "my-secret" | docker secret create db_password -
```

### 2. Weak Passwords
**Problem:** Users setting weak passwords
**Solution:** Enforce password policy
```python
# Password requirements
MIN_LENGTH = 12
REQUIRE_UPPERCASE = True
REQUIRE_LOWERCASE = True
REQUIRE_DIGITS = True
REQUIRE_SPECIAL = True
```

### 3. SQL Injection
**Problem:** Unsanitized user input in queries
**Solution:** Use parameterized queries
```python
# BAD
query = f"SELECT * FROM users WHERE id = {user_id}"

# GOOD
query = select(User).where(User.id == user_id)
```

### 4. XSS Attacks
**Problem:** Unescaped user input displayed
**Solution:** Sanitize all user input
```python
import html

sanitized = html.escape(user_input)
```

### 5. Missing CSRF Protection
**Problem:** State-changing operations without CSRF tokens
**Solution:** Implement CSRF protection
```python
from fastapi_csrf_protect import CsrfProtect

@app.post("/api/action")
async def action(csrf_protect: CsrfProtect = Depends()):
    csrf_protect.validate_csrf()
```

## Emergency Procedures

### Security Breach
1. **Immediate:** Isolate affected systems
2. **Assess:** Determine scope of breach
3. **Contain:** Block attacker access
4. **Notify:** Security team and stakeholders
5. **Recover:** Restore from clean backup
6. **Analyze:** Post-mortem and improvements

### DDoS Attack
1. Enable rate limiting
2. Block malicious IPs
3. Enable Cloudflare DDoS protection
4. Scale infrastructure
5. Contact hosting provider

### Data Leak
1. Immediately revoke exposed credentials
2. Assess what data was exposed
3. Notify affected users (if applicable)
4. Review access logs
5. Implement additional safeguards

## Security Contacts

- **Security Team:** security@fog-compute.io
- **Incident Response:** incident@fog-compute.io
- **Bug Bounty:** https://fog-compute.io/security/bounty
- **Emergency:** +1-XXX-XXX-XXXX

## Resources

- [OWASP Top 10](https://owasp.org/www-project-top-ten/)
- [CWE Top 25](https://cwe.mitre.org/top25/)
- [Security Audit Report](./WEEK_6_SECURITY_AUDIT.md)
- [Production Deployment Guide](./PRODUCTION_DEPLOYMENT_GUIDE.md)

---

**Last Updated:** 2025-10-22
**Version:** 1.0.0
