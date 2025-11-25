# CSRF Protection Documentation

## Overview

CSRF (Cross-Site Request Forgery) protection has been implemented for the Fog Compute FastAPI backend to prevent unauthorized state-changing requests from malicious websites.

## Implementation Details

### File Structure
```
backend/server/middleware/
├── csrf.py                   # CSRF middleware implementation
├── test_csrf.py             # Test suite for CSRF protection
├── __init__.py              # Updated to export CSRFMiddleware
└── CSRF_DOCUMENTATION.md    # This file
```

### Security Features

1. **Cryptographically Secure Tokens**
   - Uses `secrets.token_urlsafe(32)` for 256-bit secure random tokens
   - Constant-time comparison with `secrets.compare_digest()` to prevent timing attacks

2. **Secure Cookie Configuration**
   - HttpOnly: Prevents JavaScript access to CSRF token
   - SameSite=Strict: Prevents cross-site cookie transmission
   - Secure: HTTPS-only in production (disabled for localhost development)
   - Max-Age: 24 hours (86400 seconds)

3. **Automatic Protection**
   - Validates CSRF tokens on all state-changing methods: POST, PUT, DELETE, PATCH
   - Skips validation for safe methods: GET, HEAD, OPTIONS
   - Skips validation for Bearer token authenticated routes (separate protection)

4. **Comprehensive Logging**
   - Logs all CSRF validation failures with details
   - Debug logging for successful validations
   - Includes request path, method, and token presence information

## How It Works

### 1. Token Generation (Safe Methods)
When a client makes a GET request:
1. Middleware checks if CSRF token exists in cookies
2. If not, generates a new token using `secrets.token_urlsafe(32)`
3. Sets token in secure cookie with HttpOnly, SameSite=Strict flags
4. Client receives cookie automatically (browser handles storage)

### 2. Token Validation (State-Changing Methods)
When a client makes a POST/PUT/DELETE/PATCH request:
1. Middleware extracts CSRF token from cookie
2. Middleware extracts CSRF token from `X-CSRF-Token` header
3. Validates both tokens exist
4. Compares tokens using constant-time comparison (prevents timing attacks)
5. If valid: Proceeds with request
6. If invalid: Returns 403 Forbidden with clear error message

### 3. Bypass Rules (When CSRF Check is Skipped)
CSRF validation is automatically skipped for:
- **Safe methods**: GET, HEAD, OPTIONS
- **Health endpoints**: /health, /docs, /redoc, /openapi.json
- **Bearer-authenticated routes**: Any request with `Authorization: Bearer <token>` header
- **Auth endpoints**: /api/auth/login, /api/auth/register, /api/auth/refresh

## Frontend Integration

### Example: JavaScript Fetch API

```javascript
// Step 1: Get CSRF token (browser automatically stores cookie)
await fetch('http://localhost:8000/api/dashboard/stats', {
  credentials: 'include'  // Include cookies
});

// Step 2: Extract CSRF token from cookie
function getCsrfToken() {
  const match = document.cookie.match(/csrf_token=([^;]+)/);
  return match ? match[1] : null;
}

// Step 3: Include CSRF token in state-changing requests
const csrfToken = getCsrfToken();

await fetch('http://localhost:8000/api/scheduler/jobs', {
  method: 'POST',
  credentials: 'include',  // Include cookies
  headers: {
    'Content-Type': 'application/json',
    'X-CSRF-Token': csrfToken  // Include CSRF token header
  },
  body: JSON.stringify({ job_data: '...' })
});
```

### Example: Axios

```javascript
import axios from 'axios';

// Configure axios to include credentials
axios.defaults.withCredentials = true;

// Add CSRF token interceptor
axios.interceptors.request.use(config => {
  // Extract CSRF token from cookie
  const csrfToken = document.cookie
    .split('; ')
    .find(row => row.startsWith('csrf_token='))
    ?.split('=')[1];

  // Add CSRF token header for state-changing requests
  if (['post', 'put', 'delete', 'patch'].includes(config.method.toLowerCase())) {
    config.headers['X-CSRF-Token'] = csrfToken;
  }

  return config;
});

// Usage
await axios.get('/api/dashboard/stats');  // Sets CSRF cookie
await axios.post('/api/scheduler/jobs', { job_data: '...' });  // Validates CSRF token
```

## Testing

### Running Tests

```bash
# Navigate to backend directory
cd C:\Users\17175\Desktop\fog-compute\backend

# Run CSRF tests
python -m pytest server/middleware/test_csrf.py -v

# Or run directly
python server/middleware/test_csrf.py
```

### Test Coverage

The test suite covers:
1. CSRF token generation on GET requests
2. CSRF validation failure without token (403 Forbidden)
3. CSRF validation success with valid token
4. CSRF validation failure with mismatched token
5. Bearer token authentication bypass
6. Safe methods (GET, HEAD, OPTIONS) bypass

## Security Considerations

### What CSRF Protects Against
- **Cross-site attacks**: Malicious website cannot forge requests to your API
- **Session hijacking**: Even if attacker steals session cookie, they cannot make state-changing requests without CSRF token
- **CORS bypass**: CSRF provides additional layer beyond CORS

### What CSRF Does NOT Protect Against
- **XSS attacks**: If attacker can inject JavaScript, they can read CSRF token from cookie
  - Mitigation: Use Content Security Policy (CSP), input sanitization
- **Man-in-the-middle attacks**: Use HTTPS in production
- **Compromised client**: If user's device is compromised, CSRF cannot help

### Production Checklist
- [ ] Enable HTTPS (cookie_secure=True automatically enabled)
- [ ] Configure proper CORS origins (not wildcard "*")
- [ ] Implement rate limiting (already done via RateLimitMiddleware)
- [ ] Enable security headers (CSP, X-Frame-Options, etc.)
- [ ] Regular security audits

## Configuration

CSRF middleware is configured in `main.py`:

```python
app.add_middleware(
    CSRFMiddleware,
    cookie_secure=settings.API_HOST != "localhost",  # Auto-detects production
    cookie_httponly=True,                            # Prevents JS access
    cookie_samesite="strict"                         # Strict same-site policy
)
```

### Configuration Options
- `cookie_name`: Cookie name (default: "csrf_token")
- `header_name`: Header name to validate (default: "X-CSRF-Token")
- `cookie_secure`: HTTPS-only flag (auto: True in production, False on localhost)
- `cookie_httponly`: Prevents JavaScript access (recommended: True)
- `cookie_samesite`: Same-site policy (recommended: "strict")

## Troubleshooting

### Common Issues

**Issue**: "CSRF token is missing" error
- **Cause**: Frontend not including X-CSRF-Token header
- **Solution**: Ensure frontend extracts token from cookie and includes in header

**Issue**: "CSRF token mismatch" error
- **Cause**: Token expired, cookie not sent, or header token incorrect
- **Solution**: Check that cookies are included with `credentials: 'include'`

**Issue**: CSRF token not set in cookie
- **Cause**: Frontend not making GET request first
- **Solution**: Make a GET request to any endpoint before state-changing requests

**Issue**: Bearer token routes still require CSRF
- **Cause**: Authorization header not properly formatted
- **Solution**: Ensure header is `Authorization: Bearer <token>`

## Monitoring

CSRF failures are logged with WARNING level:

```
WARNING - CSRF validation failed: Missing token - path=/api/scheduler/jobs, method=POST, cookie_present=False, header_present=False
WARNING - CSRF validation failed: Token mismatch - path=/api/scheduler/jobs, method=POST
```

Monitor these logs for:
- Unusual spike in CSRF failures (potential attack)
- Legitimate failures (frontend integration issues)
- Pattern analysis (which endpoints are affected)

## References

- [OWASP CSRF Prevention Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Cross-Site_Request_Forgery_Prevention_Cheat_Sheet.html)
- [FastAPI Security Best Practices](https://fastapi.tiangolo.com/tutorial/security/)
- [Starlette Middleware Documentation](https://www.starlette.io/middleware/)

## Support

For issues or questions:
1. Check logs for detailed error messages
2. Review test suite for examples
3. Verify frontend integration matches documentation
4. Ensure HTTPS is enabled in production
