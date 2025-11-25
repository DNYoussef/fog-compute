# API Key Authentication - Quick Reference

## Files Created

1. **backend/server/auth/api_key.py** - Core API key manager
2. **backend/server/middleware/api_key_auth.py** - Authentication middleware
3. **backend/server/routes/api_keys.py** - Management endpoints
4. **backend/server/schemas/api_keys.py** - Pydantic schemas

## Files Modified

1. **backend/server/main.py** - Added api_keys router
2. **backend/server/routes/__init__.py** - Exported api_keys module
3. **backend/server/auth/__init__.py** - Exported APIKeyManager
4. **backend/tests/security/test_production_hardening.py** - Updated test at line 452

## API Endpoints

### POST /api/keys
Create new API key (requires JWT authentication)

**Request**:
```json
{
  "name": "Production Server",
  "expires_in_days": 90,
  "rate_limit": 5000
}
```

**Response** (SECRET KEY SHOWN ONLY ONCE):
```json
{
  "id": "123e4567-e89b-12d3-a456-426614174000",
  "name": "Production Server",
  "secret_key": "fog_sk_a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6q7r8s9t0u1v",
  "rate_limit": 5000,
  "is_active": true,
  "created_at": "2024-01-15T10:30:00Z",
  "expires_at": "2024-04-15T10:30:00Z"
}
```

### GET /api/keys
List all API keys for current user

**Response**:
```json
{
  "keys": [
    {
      "id": "123e4567-e89b-12d3-a456-426614174000",
      "name": "Production Server",
      "rate_limit": 5000,
      "is_active": true,
      "created_at": "2024-01-15T10:30:00Z",
      "last_used": "2024-01-20T15:45:00Z",
      "expires_at": "2024-04-15T10:30:00Z"
    }
  ],
  "total": 1
}
```

### DELETE /api/keys/{key_id}
Revoke (deactivate) API key

**Response**:
```json
{
  "success": true,
  "message": "API key 'Production Server' has been revoked",
  "key_id": "123e4567-e89b-12d3-a456-426614174000"
}
```

## Using API Keys in Endpoints

### Option 1: Require API Key
```python
from fastapi import APIRouter, Depends
from ..middleware.api_key_auth import require_api_key

router = APIRouter()

@router.get("/protected")
async def protected_endpoint(key_data: dict = Depends(require_api_key)):
    return {"user": key_data['user'].username}
```

### Option 2: Optional API Key
```python
from fastapi import APIRouter, Depends
from ..middleware.api_key_auth import get_api_key_user

@router.get("/optional")
async def optional_endpoint(key_data: dict = Depends(get_api_key_user)):
    if key_data:
        return {"authenticated": True, "user": key_data['user'].username}
    return {"authenticated": False}
```

### Option 3: With Rate Limiting
```python
from fastapi import APIRouter, Depends
from ..middleware.api_key_auth import check_api_key_rate_limit

@router.get("/rate-limited")
async def rate_limited(key_data: dict = Depends(check_api_key_rate_limit)):
    return {"message": "Success", "rate_limit": key_data['rate_limit']}
```

## Client Usage

### cURL
```bash
curl -H "X-API-Key: fog_sk_..." http://localhost:8000/api/protected
```

### Python
```python
import requests

headers = {"X-API-Key": "fog_sk_..."}
response = requests.get("http://localhost:8000/api/protected", headers=headers)
```

### JavaScript
```javascript
fetch('http://localhost:8000/api/protected', {
  headers: { 'X-API-Key': 'fog_sk_...' }
})
```

## Key Format

- Prefix: `fog_sk_`
- Length: 50 characters total
- Example: `fog_sk_a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6q7r8s9t0u1v`

## Security

- Keys hashed with SHA-256 before storage
- Plain text NEVER stored in database
- Secret key shown ONLY during creation
- Rate limiting per key (default: 1000 req/hour)
- Expiration support
- Revocation (soft delete)

## Rate Limit Headers

```
X-RateLimit-Limit: 5000
X-RateLimit-Remaining: 4999
X-RateLimit-Reset: 3456
Retry-After: 3456 (on 429 error)
```

## Testing

Test location: `backend/tests/security/test_production_hardening.py:452`

Run test:
```bash
cd backend
pytest tests/security/test_production_hardening.py::TestAuthentication::test_api_key_authentication -v
```

## Documentation

- Full guide: `backend/server/routes/EXAMPLE_API_KEY_USAGE.md`
- Summary: `backend/API_KEY_IMPLEMENTATION_SUMMARY.md`
- API docs: http://localhost:8000/docs (after starting server)
