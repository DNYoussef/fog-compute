# API Key Authentication Usage Examples

This document shows how to use API key authentication in your endpoints.

## Basic Usage

### Option 1: Require API Key (Strict)

```python
from fastapi import APIRouter, Depends
from ..middleware.api_key_auth import require_api_key

router = APIRouter()

@router.get("/protected-endpoint")
async def protected_endpoint(
    key_data: dict = Depends(require_api_key)
):
    """
    This endpoint REQUIRES a valid API key in X-API-Key header.
    Returns 401 if no key or invalid key.
    """
    user = key_data['user']
    key_name = key_data['key_name']

    return {
        "message": "Access granted",
        "user": user.username,
        "key_name": key_name
    }
```

### Option 2: Optional API Key

```python
from fastapi import APIRouter, Depends
from ..middleware.api_key_auth import get_api_key_user

router = APIRouter()

@router.get("/optional-auth")
async def optional_auth(
    key_data: dict = Depends(get_api_key_user)
):
    """
    This endpoint accepts API key but doesn't require it.
    Returns different responses based on authentication.
    """
    if key_data:
        return {
            "message": "Authenticated access",
            "user": key_data['user'].username,
            "key_name": key_data['key_name']
        }
    else:
        return {
            "message": "Anonymous access",
            "limited": True
        }
```

### Option 3: Hybrid Auth (JWT or API Key)

```python
from fastapi import APIRouter, Depends, HTTPException, status
from ..middleware.api_key_auth import get_api_key_user
from ..auth.dependencies import get_current_active_user

router = APIRouter()

@router.get("/hybrid-auth")
async def hybrid_auth(
    api_key_user: dict = Depends(get_api_key_user),
    jwt_user: User = Depends(get_current_active_user)
):
    """
    This endpoint accepts EITHER API key OR JWT token.
    Useful for endpoints that serve both web users and services.
    """
    if api_key_user:
        # Authenticated via API key
        user = api_key_user['user']
        auth_method = "API Key"
    elif jwt_user:
        # Authenticated via JWT
        user = jwt_user
        auth_method = "JWT"
    else:
        # No authentication
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required"
        )

    return {
        "user": user.username,
        "auth_method": auth_method
    }
```

### Option 4: With Rate Limiting

```python
from fastapi import APIRouter, Depends
from ..middleware.api_key_auth import check_api_key_rate_limit

router = APIRouter()

@router.get("/rate-limited")
async def rate_limited(
    key_data: dict = Depends(check_api_key_rate_limit)
):
    """
    This endpoint enforces the API key's rate limit.
    Returns 429 if rate limit exceeded.
    """
    return {
        "message": "Success",
        "rate_limit": key_data['rate_limit']
    }
```

## Client Examples

### Python Client

```python
import requests

API_KEY = "fog_sk_a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6q7r8s9t0u1v"
BASE_URL = "http://localhost:8000"

# Make authenticated request
response = requests.get(
    f"{BASE_URL}/api/protected-endpoint",
    headers={"X-API-Key": API_KEY}
)

print(response.json())
```

### cURL Example

```bash
curl -H "X-API-Key: fog_sk_a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6q7r8s9t0u1v" \
     http://localhost:8000/api/protected-endpoint
```

### JavaScript/Fetch Example

```javascript
const API_KEY = 'fog_sk_a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6q7r8s9t0u1v';
const BASE_URL = 'http://localhost:8000';

fetch(`${BASE_URL}/api/protected-endpoint`, {
  headers: {
    'X-API-Key': API_KEY
  }
})
  .then(response => response.json())
  .then(data => console.log(data));
```

## Security Best Practices

1. **Store Keys Securely**
   - Use environment variables or secret management systems
   - Never commit keys to version control
   - Rotate keys periodically

2. **Use HTTPS in Production**
   - API keys should ONLY be transmitted over HTTPS
   - Configure Nginx/reverse proxy with TLS certificates

3. **Set Appropriate Rate Limits**
   - Production services: 1000-5000 req/hour
   - Development/testing: 100-500 req/hour
   - Internal services: 10000+ req/hour

4. **Set Expiration Dates**
   - Short-lived keys (7-30 days) for testing
   - Medium-lived keys (90-180 days) for production
   - Long-lived keys (1 year+) only for critical infrastructure

5. **Monitor Key Usage**
   - Check `last_used` field to identify unused keys
   - Revoke keys that haven't been used in 90+ days
   - Monitor rate limit violations

## API Key Management Flow

1. **Create Key**
   ```bash
   POST /api/keys
   Authorization: Bearer <jwt-token>
   Body: {
     "name": "Production Server",
     "expires_in_days": 90,
     "rate_limit": 5000
   }

   Response: {
     "secret_key": "fog_sk_...",  # SAVE THIS!
     "id": "...",
     "name": "Production Server"
   }
   ```

2. **List Keys**
   ```bash
   GET /api/keys
   Authorization: Bearer <jwt-token>

   Response: {
     "keys": [...],
     "total": 3
   }
   ```

3. **Revoke Key**
   ```bash
   DELETE /api/keys/{key_id}
   Authorization: Bearer <jwt-token>

   Response: {
     "success": true,
     "message": "API key revoked"
   }
   ```

## Database Schema

The API key is stored as a SHA-256 hash in the database:

```python
class APIKey:
    id: UUID
    user_id: UUID (FK to users)
    key_hash: str  # SHA-256 hash of "fog_sk_..."
    name: str
    is_active: bool
    rate_limit: int  # requests per hour
    created_at: datetime
    last_used: datetime
    expires_at: datetime
```

## Rate Limiting Details

- **Window**: 1 hour (3600 seconds)
- **Limit**: Configured per API key (default: 1000 req/hour)
- **Headers**:
  - `X-RateLimit-Limit`: Maximum requests allowed
  - `X-RateLimit-Remaining`: Requests remaining in window
  - `X-RateLimit-Reset`: Seconds until window resets
  - `Retry-After`: Seconds to wait (on 429 error)

## Error Responses

### 401 Unauthorized (Missing Key)
```json
{
  "detail": "API key required"
}
```

### 401 Unauthorized (Invalid Key)
```json
{
  "detail": "Invalid API key"
}
```

### 429 Too Many Requests
```json
{
  "detail": {
    "error": "Rate limit exceeded",
    "message": "API key rate limit exceeded. Try again in 3456 seconds",
    "retry_after": 3456
  }
}
```
Headers: `Retry-After: 3456`
