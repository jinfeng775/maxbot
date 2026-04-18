---
name: security-review
description: Use this skill when adding authentication, handling user input, working with secrets, creating API endpoints, or implementing payment/sensitive features. Provides comprehensive security checklist and patterns. Adapted from Everything Claude Code for MaxBot.
category: security
priority: P0
tools_required:
  - terminal
  - file_tools
  - web_search
dependencies: []
---

# Security Review Skill (MaxBot Edition)

This skill ensures all code follows security best practices and identifies potential vulnerabilities, adapted for MaxBot's Python ecosystem.

## When to Activate

- Implementing authentication or authorization
- Handling user input or file uploads
- Creating new API endpoints
- Working with secrets or credentials
- Implementing payment features
- Storing or transmitting sensitive data
- Integrating third-party APIs

## Security Checklist

### 1. Secrets Management

#### FAIL: NEVER Do This
```python
# Hardcoded secrets in Python
API_KEY = "sk-proj-***"  # NEVER commit this
DB_PASSWORD = "password123"  # NEVER in source code
```

#### PASS: ALWAYS Do This
```python
import os
from dotenv import load_dotenv

load_dotenv()

# Read from environment
api_key = os.getenv("OPENAI_API_KEY")
db_url = os.getenv("DATABASE_URL")

# Verify secrets exist
if not api_key:
    raise ValueError("OPENAI_API_KEY not configured")

# Mark as required in .env.example
```

#### Verification Steps
- [ ] No hardcoded API keys, tokens, or passwords
- [ ] All secrets in environment variables
- [ ] `.env` in `.gitignore`
- [ ] No secrets in git history
- [ ] Production secrets in hosting platform (Docker env, K8s secrets)

### 2. Input Validation

#### Always Validate User Input
```python
from pydantic import BaseModel, EmailStr, Field, validator
from typing import Optional

class CreateUserRequest(BaseModel):
    email: EmailStr
    name: str = Field(..., min_length=1, max_length=100)
    age: int = Field(..., ge=0, le=150)
    
    @validator('name')
    def name_must_not_contain_special_chars(cls, v):
        if any(char in v for char in '<>\"\''):
            raise ValueError('Name contains invalid characters')
        return v

def create_user(input: dict) -> dict:
    """Create user with validation"""
    try:
        validated = CreateUserRequest(**input)
        return db.users.create(validated.dict())
    except ValidationError as e:
        return {"success": False, "errors": e.errors()}
```

#### File Upload Validation
```python
import magic

def validate_file_upload(file_path: str, max_size_mb: int = 5) -> bool:
    """Validate uploaded file"""
    import os
    
    # Size check
    file_size = os.path.getsize(file_path)
    max_size = max_size_mb * 1024 * 1024
    if file_size > max_size:
        raise ValueError(f"File too large (max {max_size_mb}MB)")
    
    # Type check using magic numbers
    mime = magic.from_file(file_path, mime=True)
    allowed_types = {
        'image/jpeg',
        'image/png',
        'image/gif',
        'application/pdf'
    }
    if mime not in allowed_types:
        raise ValueError(f"Invalid file type: {mime}")
    
    return True
```

#### Verification Steps
- [ ] All user inputs validated with schemas (pydantic)
- [ ] File uploads restricted (size, type, magic numbers)
- [ ] No direct use of user input in queries
- [ ] Whitelist validation (not blacklist)
- [ ] Error messages don't leak sensitive info

### 3. SQL Injection Prevention

#### FAIL: NEVER Concatenate SQL
```python
# DANGEROUS - SQL Injection vulnerability
query = f"SELECT * FROM users WHERE email = '{user_email}'"
db.execute(query)
```

#### PASS: ALWAYS Use Parameterized Queries
```python
# Safe with SQLAlchemy
user = db.query(User).filter(User.email == user_email).first()

# Safe with raw SQL (psycopg2)
cursor.execute(
    "SELECT * FROM users WHERE email = %s",
    (user_email,)
)

# Safe with SQLite
cursor.execute(
    "SELECT * FROM users WHERE email = ?",
    (user_email,)
)
```

#### Verification Steps
- [ ] All database queries use parameterized queries
- [ ] No string concatenation/f-strings in SQL
- [ ] ORM/query builder used correctly
- [ ] No dynamic table/column names from user input

### 4. Authentication & Authorization

#### JWT Token Handling
```python
import jwt
from datetime import datetime, timedelta
from fastapi import Cookie, HTTPException

# FAIL: WRONG: localStorage or insecure cookies
# def login(token):
#     return {"token": token}  # Client stores in localStorage

# PASS: CORRECT: httpOnly cookies
def set_auth_cookie(response, token: str):
    """Set secure httpOnly cookie"""
    response.set_cookie(
        key="auth_token",
        value=token,
        httponly=True,
        secure=True,  # HTTPS only
        samesite="strict",
        max_age=3600
    )
    return response

def verify_token(token: str = Cookie(...)) -> dict:
    """Verify JWT token"""
    try:
        payload = jwt.decode(
            token,
            os.getenv("JWT_SECRET"),
            algorithms=["HS256"]
        )
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")
```

#### Authorization Checks
```python
from functools import wraps
from fastapi import HTTPException

def require_admin(func):
    """Decorator requiring admin role"""
    @wraps(func)
    async def wrapper(*args, **kwargs):
        user = get_current_user()
        if user.role != "admin":
            raise HTTPException(
                status_code=403,
                detail="Admin access required"
            )
        return await func(*args, **kwargs)
    return wrapper

@require_admin
async def delete_user(user_id: str):
    """Delete user (admin only)"""
    db.users.delete(user_id)
```

#### Verification Steps
- [ ] Tokens stored in httpOnly cookies (not localStorage)
- [ ] Authorization checks before sensitive operations
- [ ] Role-based access control implemented
- [ ] Token expiration handled
- [ ] Token refresh mechanism implemented

### 5. XSS Prevention

#### Sanitize HTML
```python
import bleach

def sanitize_user_html(html: str) -> str:
    """Sanitize user-provided HTML"""
    allowed_tags = {
        'b', 'i', 'em', 'strong', 'p', 
        'br', 'ul', 'ol', 'li'
    }
    allowed_attrs = {}
    
    return bleach.clean(
        html,
        tags=allowed_tags,
        attributes=allowed_attrs,
        strip=True
    )
```

#### Content Security Policy (FastAPI)
```python
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.httpsredirect import HTTPSRedirectMiddleware

app.add_middleware(HTTPSRedirectMiddleware)

@app.middleware("http")
async def add_security_headers(request, call_next):
    response = await call_next(request)
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline'; "
        "style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data: https:; "
    )
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    return response
```

#### Verification Steps
- [ ] User-provided HTML sanitized
- [ ] CSP headers configured
- [ ] No unvalidated dynamic content rendering
- [ ] Security headers set (X-Frame-Options, X-Content-Type-Options)

### 6. CSRF Protection

#### CSRF Tokens
```python
import secrets
from fastapi import Request, HTTPException

def generate_csrf_token() -> str:
    """Generate CSRF token"""
    return secrets.token_urlsafe(32)

def verify_csrf_token(request: Request, token: str) -> bool:
    """Verify CSRF token"""
    expected = request.cookies.get("csrf_token")
    if not expected or not secrets.compare_digest(expected, token):
        raise HTTPException(status_code=403, detail="Invalid CSRF token")
    return True

# Usage in endpoints
@app.post("/api/data")
async def update_data(
    request: Request,
    csrf_token: str = Form(...)
):
    verify_csrf_token(request, csrf_token)
    # Process request
```

#### Verification Steps
- [ ] CSRF tokens on state-changing operations (POST/PUT/DELETE)
- [ ] SameSite=Strict on all cookies
- [ ] CSRF tokens validated server-side

### 7. Rate Limiting

#### API Rate Limiting (FastAPI + slowapi)
```python
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address

limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["200 per day", "50 per hour"]
)

app.state.limiter = limiter
app.add_exception_handler(
    RateLimitExceeded,
    _rate_limit_exceeded_handler
)

@app.post("/api/data")
@limiter.limit("10 per minute")
async def expensive_operation(request: Request):
    # Stricter rate limiting for expensive operations
    pass
```

#### Verification Steps
- [ ] Rate limiting on all API endpoints
- [ ] Stricter limits on expensive operations
- [ ] IP-based rate limiting
- [ ] User-based rate limiting (authenticated)

### 8. Sensitive Data Exposure

#### Logging
```python
import logging

# FAIL: WRONG: Logging sensitive data
logger.info(f"User login: {email}, {password}")

# PASS: CORRECT: Redact sensitive data
logger.info(f"User login: {email}, user_id={user_id}")

# Use structured logging with redaction
from loguru import logger

logger.info(
    "User login",
    email=email,
    user_id=user_id
    # password is NOT logged
)
```

#### Error Messages
```python
# FAIL: WRONG: Exposing internal details
try:
    result = risky_operation()
except Exception as e:
    return {
        "error": str(e),
        "stack_trace": traceback.format_exc()
    }

# PASS: CORRECT: Generic error messages
import traceback
import logging

try:
    result = risky_operation()
except Exception as e:
    # Log detailed error server-side
    logging.error(f"Operation failed: {e}", exc_info=True)
    
    # Return generic message to client
    return {
        "error": "An error occurred. Please try again."
    }
```

#### Verification Steps
- [ ] No passwords, tokens, or secrets in logs
- [ ] Error messages generic for users
- [ ] Detailed errors only in server logs
- [ ] No stack traces exposed to users

### 9. Dependency Security

#### Regular Updates
```bash
# Check for vulnerabilities
pip-audit

# Update dependencies
pip install --upgrade -r requirements.txt

# Check for outdated packages
pip list --outdated
```

#### Requirements Files
```bash
# ALWAYS commit requirements.txt and requirements.lock
pip freeze > requirements.txt

# Use pip-tools for reproducible builds
pip-compile requirements.in
```

#### Pre-commit Hook
```yaml
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/PyCQA/bandit
    rev: 1.7.5
    hooks:
      - id: bandit
        args: ['-r', 'src/']
```

#### Verification Steps
- [ ] Dependencies up to date
- [ ] No known vulnerabilities (pip-audit clean)
- [ ] Lock files committed
- [ ] Security linting (bandit) enabled
- [ ] Regular security updates

## Security Testing

### Automated Security Tests
```python
import pytest
from fastapi.testclient import TestClient
from myapp import app

client = TestClient(app)

def test_requires_authentication():
    """Test authentication is required"""
    response = client.get("/api/protected")
    assert response.status_code == 401

def test_requires_admin_role():
    """Test admin role is required"""
    # Create regular user token
    user_token = create_test_token(role="user")
    
    response = client.get(
        "/api/admin",
        headers={"Authorization": f"Bearer {user_token}"}
    )
    assert response.status_code == 403

def test_input_validation():
    """Test input validation"""
    response = client.post(
        "/api/users",
        json={"email": "not-an-email"}
    )
    assert response.status_code == 400

def test_rate_limiting():
    """Test rate limiting"""
    # Make 11 requests (limit is 10)
    for _ in range(11):
        response = client.get("/api/endpoint")
    
    # Last request should be rate limited
    assert response.status_code == 429
```

### Security Linting

```bash
# Run bandit security linter
bandit -r src/ -f json -o security_report.json

# Run safety to check for known vulnerabilities
safety check

# Run pip-audit
pip-audit --format json --output audit_report.json
```

## Pre-Deployment Security Checklist

Before ANY production deployment:

- [ ] **Secrets**: No hardcoded secrets, all in env vars
- [ ] **Input Validation**: All user inputs validated (pydantic)
- [ ] **SQL Injection**: All queries parameterized
- [ ] **XSS**: User content sanitized (bleach)
- [ ] **CSRF**: Protection enabled on state changes
- [ ] **Authentication**: Proper token handling (httpOnly cookies)
- [ ] **Authorization**: Role checks in place
- [ ] **Rate Limiting**: Enabled on all endpoints
- [ ] **HTTPS**: Enforced in production
- [ ] **Security Headers**: CSP, X-Frame-Options configured
- [ ] **Error Handling**: No sensitive data in errors
- [ ] **Logging**: No sensitive data logged
- [ ] **Dependencies**: Up to date, no vulnerabilities
- [ ] **CORS**: Properly configured
- [ ] **File Uploads**: Validated (size, type, magic numbers)
- [ ] **Security Linting**: bandit, safety, pip-audit pass

## Resources

- [OWASP Top 10](https://owasp.org/www-project-top-ten/)
- [FastAPI Security](https://fastapi.tiangolo.com/tutorial/security/)
- [Pydantic Validation](https://docs.pydantic.dev/)
- [Bandit Security Linter](https://bandit.readthedocs.io/)

---

**Remember**: Security is not optional. One vulnerability can compromise of entire platform. When in doubt, err on the side of caution.

**MaxBot-Specific Notes**:
- Use pydantic for input validation
- Use FastAPI security features (OAuth2, API keys)
- Use httpOnly cookies for token storage
- Run security linting in CI/CD pipeline
- Always review code changes with security checklist
