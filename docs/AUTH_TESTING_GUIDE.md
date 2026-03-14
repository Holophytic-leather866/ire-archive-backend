# Authentication Routes Testing Guide

This guide explains how to configure, test, and verify the MemberSuite SSO authentication routes in both development and production environments.

## Table of Contents

- [Prerequisites](#prerequisites)
- [Development Setup](#development-setup)
- [Testing in Development](#testing-in-development)
- [Production Setup](#production-setup)
- [Testing in Production](#testing-in-production)
- [Troubleshooting](#troubleshooting)

---

## Prerequisites

Before testing authentication routes, you need:

### Required Credentials (obtain from IRE)

```bash
MS_TENANT_ID         # MemberSuite tenant/partition key (integer)
MS_ASSOCIATION_ID    # Association GUID
```

**How to find these** (from MemberSuite Console):

1. Log into the MemberSuite Console
2. Click **Setup** in the Console toolbar
3. Click **Association Settings**
4. Note the "Association's ID" (GUID) and "Tenant ID" (integer)

### Test Account

- Valid IRE member credentials for testing the full authentication flow
- The test account should have `receivesMemberBenefits = true`

### Local Infrastructure

- Redis instance (for session storage)
- Docker (for running Redis locally)

---

## Development Setup

There are two approaches for local development:

1. **Local Callback Testing** - Test complete MemberSuite SSO flow with localhost callback
2. **Dev Bypass Mode** - Rapid development without MemberSuite

### Option 1: Local Callback Testing (Recommended for Integration Testing)

Since MemberSuite doesn't require domain whitelisting, you can use a localhost callback URL for complete local testing. When `FRONTEND_URL` contains "localhost", the callback URL automatically becomes `http://localhost:8000/auth/callback`.

**How it works:**

- Your local backend calls MemberSuite `/signUpSSO` with `http://localhost:8000/auth/callback`
- User authenticates on MemberSuite portal
- MemberSuite redirects back to your **local** backend callback
- Your local backend creates the session and redirects to your local frontend
- Session cookies work on localhost, enabling full end-to-end testing

#### Step 1: Start the Local Stack

Starts Redis, Qdrant, and the API with reload.

```bash
make dev-start
```

This command also ensures Redis is reachable (no need to start it separately).

#### Step 2: Create Environment File

Create `.env` in the project root:

```bash
# MemberSuite credentials (get from IRE)
MS_TENANT_ID=12345
MS_ASSOCIATION_ID=your-association-guid

# Local Redis
REDIS_URL=redis://localhost:6379

# Session secret (any 32+ character string for local dev)
SESSION_SECRET=local-dev-secret-at-least-32-characters-long-for-testing

# Frontend URL (your local dev server) - triggers localhost callback
FRONTEND_URL=http://localhost:5173

# Optional: Skip membership check for testing
# MS_REQUIRE_MEMBERSHIP=false
```

**Note**: The callback URL is automatically set based on `FRONTEND_URL`:

- Contains "localhost" → `http://localhost:8000/auth/callback`
- Production → `https://api.archive.ire.org/auth/callback`

#### Step 3: Verify Services (Optional)

```bash
make dev-status

# Optional: start the separate frontend repo locally
# https://github.com/ireapps/ire-archive-frontend
```

#### Step 4: Test the Flow

1. Visit your local backend: `http://localhost:8000/auth/status`
2. Verify status shows `configured: true` and `callback_url: "http://localhost:8000/auth/callback"`
3. Test login: `http://localhost:8000/auth/login`
4. Should redirect to MemberSuite login portal
5. Enter valid IRE member credentials
6. MemberSuite redirects back to your **local** callback: `http://localhost:8000/auth/callback?tokenGUID=...`
7. Local backend exchanges token, creates session, sets cookie, and redirects to `http://localhost:5173` (or your configured `FRONTEND_URL` if running the frontend)
8. You can now test authenticated endpoints with: `http://localhost:8000/auth/me`

**✅ Full local testing**: Session cookies work on localhost, allowing complete end-to-end testing without production dependencies.

---

### Option 2: Dev Bypass Mode (For Rapid Development)

Skip MemberSuite and use a fake session for testing.

#### Step 1: Start the Local Stack

Starts Redis, Qdrant, and the API with reload.

```bash
make dev-start
```

#### Step 2: Create Environment File

Create `.env` in the project root:

```bash
# Enable dev bypass
DEV_AUTH_BYPASS=true
ENVIRONMENT=development

# Local Redis
REDIS_URL=redis://localhost:6379

# Session secret
SESSION_SECRET=local-dev-secret-at-least-32-characters-long-for-testing

# URLs (no ngrok needed)
FRONTEND_URL=http://localhost:5173
```

#### Step 3: Start the Backend

Already running from Step 1 (API starts with reload). If you stopped it, rerun `make dev-start`.

#### Step 4: Create Test Sessions

Use the dev bypass endpoint to create fake sessions:

```bash
# Create session as an active member
curl "http://localhost:8000/auth/dev/login?email=test@ire.org&name=Test+User&member=true"

# Create session as a non-member (to test membership errors)
curl "http://localhost:8000/auth/dev/login?email=test@ire.org&name=Test+User&member=false"
```

Or visit in browser:

```
http://localhost:8000/auth/dev/login?email=dev@ire.org&name=Dev+User&member=true
```

This will set a session cookie and redirect to the frontend.

---

## Testing in Development

### Basic Endpoint Tests

```bash
# Test auth status
curl http://localhost:8000/auth/status | jq

# Test login endpoint (requires MS credentials)
curl http://localhost:8000/auth/login | jq

# Test me endpoint (requires session cookie)
curl -b cookies.txt http://localhost:8000/auth/me | jq

# Test logout (with session)
curl -X POST -b cookies.txt -c cookies.txt http://localhost:8000/auth/logout | jq
```

### Testing with httpie (Better Cookie Handling)

```bash
# Install httpie
pip install httpie

# Test login flow
http GET http://localhost:8000/auth/login
# Follow redirect_url in browser

# After login, test me endpoint
http --session=dev GET http://localhost:8000/auth/me

# Test logout
http --session=dev POST http://localhost:8000/auth/logout
```

### Testing Full Authentication Flow

1. **Start with clean state**:

   ```bash
   # Clear Redis sessions
   docker exec -it ire-redis redis-cli FLUSHDB
   ```

2. **Test login initiation**:

   ```bash
   curl http://localhost:8000/auth/login
   ```

   Expected: JSON with `redirect_url` pointing to MemberSuite portal

3. **Test callback** (simulate MemberSuite redirect):

   ```bash
   # This will fail without a real tokenGUID from MemberSuite
   curl "http://localhost:8000/auth/callback?tokenGUID=fake-token"
   ```

   Expected: Error (token exchange fails with fake token)

4. **Test session verification**:

   ```bash
   # With dev bypass:
   curl "http://localhost:8000/auth/dev/login?email=test@ire.org&member=true" -c cookies.txt

   # Then test me endpoint
   curl -b cookies.txt http://localhost:8000/auth/me
   ```

   Expected: User profile JSON

5. **Test logout**:
   ```bash
   curl -X POST -b cookies.txt http://localhost:8000/auth/logout
   ```
   Expected: `{"success": true, "message": "Logged out successfully"}`

### Verify Session Storage in Redis

```bash
# List all session keys
docker exec -it ire-redis redis-cli KEYS "session:*"

# Get a session value
docker exec -it ire-redis redis-cli GET "session:abc123..."

# Check session TTL
docker exec -it ire-redis redis-cli TTL "session:abc123..."
```

### Testing Error Cases

1. **No session cookie**:

   ```bash
   curl http://localhost:8000/auth/me
   ```

   Expected: 401 Unauthorized, `SESSION_EXPIRED`

2. **Invalid session cookie**:

   ```bash
   curl -H "Cookie: ire_session=invalid" http://localhost:8000/auth/me
   ```

   Expected: 401 Unauthorized, `SESSION_EXPIRED`

3. **Expired session** (wait for TTL):

   ```bash
   # Set short TTL for testing
   SESSION_TTL_SECONDS=5 python3 -m uvicorn app.main:app --port 8000

   # Create session, wait 6 seconds, test
   curl "http://localhost:8000/auth/dev/login?email=test@ire.org" -c cookies.txt
   sleep 6
   curl -b cookies.txt http://localhost:8000/auth/me
   ```

   Expected: 401 Unauthorized

4. **Non-member login** (if membership required):
   ```bash
   curl "http://localhost:8000/auth/dev/login?email=test@ire.org&member=false" -c cookies.txt
   curl -b cookies.txt http://localhost:8000/auth/me
   ```
   Expected: 403 Forbidden, `MEMBERSHIP_REQUIRED`

---

## Production Setup

### Required Environment Variables

Set these secrets in Fly.io:

```bash
# MemberSuite credentials (obtain from IRE)
fly secrets set MS_TENANT_ID="12345"
fly secrets set MS_ASSOCIATION_ID="your-association-guid"

# Redis connection (create Fly Redis first)
fly secrets set REDIS_URL="redis://default:YOUR_PASSWORD@your-redis-host.fly.dev:6379"

# Session signing secret (generate random)
fly secrets set SESSION_SECRET="$(openssl rand -hex 32)"

# Frontend URL (update when custom domain is ready)
fly secrets set FRONTEND_URL="https://archive.ire.org"

# Optional: MemberSuite API base (default: https://rest.membersuite.com)
# fly secrets set MS_API_BASE_URL="https://rest.membersuite.com"

# Optional: Skip membership check (NOT recommended for production)
# fly secrets set MS_REQUIRE_MEMBERSHIP="false"
```

### Create Fly Redis Instance

```bash
# Create Redis instance
fly redis create my-redis --region ord

# This will output the REDIS_URL - use it in the secrets above
```

### Deploy to Production

```bash
# Deploy the backend
fly deploy

# Check status
fly status

# View logs
fly logs
```

### Verify Deployment

```bash
# Check auth status
curl https://api.archive.ire.org/auth/status | jq

# Should show:
# {
#   "configured": true,
#   "frontend_url": "https://archive.ire.org",
#   "callback_url": "https://api.archive.ire.org/auth/callback"
# }
```

---

## Testing in Production

### Pre-deployment Checklist

- [ ] Fly Redis instance created
- [ ] All required secrets set in Fly.io
- [ ] `SESSION_SECRET` is cryptographically random (32+ chars)
- [ ] `FRONTEND_URL` matches actual frontend deployment
- [ ] Test account credentials available
- [ ] DEV_AUTH_BYPASS is NOT enabled in production

### Basic Production Tests

```bash
# Test auth status
curl https://api.archive.ire.org/auth/status | jq

# Test login endpoint
curl https://api.archive.ire.org/auth/login | jq

# Should return:
# {
#   "redirect_url": "https://[acronym].users.membersuite.com/auth/portal-login?..."
# }
```

### Full Production Flow Test

1. **Initiate login in browser**:
   - Visit: `https://api.archive.ire.org/auth/login`
   - Copy the `redirect_url`
   - Paste in browser

2. **Login with test credentials**:
   - Enter valid IRE member username/password
   - Should redirect to callback URL

3. **Verify callback creates session**:
   - After redirect, you should land on frontend with session cookie
   - Check browser DevTools → Application → Cookies
   - Look for `ire_session` cookie

4. **Test protected endpoint**:

   ```bash
   # With session cookie from browser (copy value)
   curl -H "Cookie: ire_session=YOUR_COOKIE_VALUE" \
     https://api.archive.ire.org/auth/me | jq
   ```

   Expected: User profile JSON

5. **Test logout**:
   ```bash
   curl -X POST -H "Cookie: ire_session=YOUR_COOKIE_VALUE" \
     https://api.archive.ire.org/auth/logout | jq
   ```
   Expected: Success message, cookie cleared

### Monitor Production Sessions

```bash
# SSH into Fly.io app
fly ssh console

# Inside container, connect to Redis
redis-cli -h your-redis-host.fly.dev -a YOUR_PASSWORD

# List sessions
KEYS session:*

# Check session count
DBSIZE

# Get session TTL
TTL session:abc123...

# Exit Redis and SSH
exit
exit
```

### Production Error Monitoring

```bash
# Watch logs in real-time
fly logs -f

# Filter for auth errors
fly logs | grep -i "membersuite\|auth\|session"

# Check for specific error codes
fly logs | grep "SESSION_EXPIRED\|MEMBERSHIP_REQUIRED\|TOKEN_EXCHANGE"
```

---

## Troubleshooting

### Common Issues

#### 1. "Auth service not configured" (503 error)

**Cause**: Missing required environment variables

**Solution**:

```bash
# Check current settings
fly secrets list

# Verify required secrets are set:
# - MS_TENANT_ID
# - MS_ASSOCIATION_ID
# - REDIS_URL
# - SESSION_SECRET

# Check auth status endpoint
curl https://api.archive.ire.org/auth/status | jq
```

#### 2. "Session expired" (401 error)

**Causes**:

- Session TTL expired (default: 1 hour)
- Redis connection lost
- Session cookie not sent
- Invalid signature

**Solutions**:

```bash
# Check Redis connectivity
fly redis connect my-redis
PING  # Should return PONG

# Check session exists
KEYS session:*

# Verify cookie is being sent
# In browser DevTools → Network → Request Headers → Cookie

# Try creating a new session
curl "http://localhost:8000/auth/dev/login?email=test@ire.org" -c cookies.txt
```

#### 3. "Membership required" (403 error)

**Cause**: User's `receivesMemberBenefits` is not `true`

**Solutions**:

```bash
# For testing, disable membership check
fly secrets set MS_REQUIRE_MEMBERSHIP="false"

# For production, verify test account has active membership:
# 1. Log into MemberSuite console
# 2. Find test user
# 3. Check "Receives Member Benefits" field
```

#### 4. "Token exchange failed" (502 error)

**Causes**:

- Invalid `MS_TENANT_ID` or `MS_ASSOCIATION_ID`
- `tokenGUID` expired (5-minute limit)
- MemberSuite API unreachable

**Solutions**:

```bash
# Verify credentials
fly secrets list | grep MS_

# Test MemberSuite API directly
curl "https://rest.membersuite.com/platform/v2/whoami" \
  -H "Authorization: AuthToken test"
# Should return 401 (API is reachable)

# Check timing - callback must happen within 5 minutes
fly logs | grep "auth_callback_received"
```

#### 5. Cookies Not Being Set

**Causes**:

- CORS misconfiguration
- `SameSite=none` requires HTTPS
- Browser blocking third-party cookies

**Solutions**:

```bash
# Check CORS headers
curl -I https://api.archive.ire.org/auth/callback

# Verify allow_credentials=True
# Should see: Access-Control-Allow-Credentials: true

# For local dev with Dev Bypass, use:
# - secure=False (allow HTTP)
# - samesite="lax" (less strict)

# For production:
# - secure=True (HTTPS only)
# - samesite="none" (cross-origin)
```

**Note**: When testing with production callback (Option 1), session cookies are set on the production domain, not localhost. Use Dev Bypass Mode for full local testing with cookies.

### Debugging Tips

#### Enable Verbose Logging

```bash
# Set log level
LOG_LEVEL=DEBUG python3 -m uvicorn app.main:app --reload

# Or in production
fly secrets set LOG_LEVEL="DEBUG"
```

#### Test MemberSuite API Directly

```bash
# Test signUpSSO endpoint
curl -X POST "https://rest.membersuite.com/platform/v2/signUpSSO" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "nextUrl=https://example.com/callback" \
  -d "IsSignUp=false" \
  -d "AssociationId=YOUR_ASSOCIATION_ID" \
  -i

# Should return 302 redirect with Location header
```

#### Inspect Session Data

```bash
# In Python shell
import redis
import json

r = redis.from_url("redis://localhost:6379")
keys = r.keys("session:*")
for key in keys:
    data = json.loads(r.get(key))
    print(f"Session: {key}")
    print(f"User: {data['email']}")
    print(f"Expires: {data['expires_at']}")
    print()
```

### Getting Help

If you encounter issues not covered here:

1. **Check logs**: `fly logs -f` (production) or console output (local)
2. **Review docs**: `docs/MEMBERSUITE_SSO_INTEGRATION.md`
3. **Verify config**: `curl /auth/status`
4. **Test components**: Start with status → login → callback → me
5. **Contact maintainer**: Investigative Reporters & Editors (help@ire.org)

---

## Security Checklist

Before going live:

- [ ] `SESSION_SECRET` is cryptographically random (min 32 chars)
- [ ] `DEV_AUTH_BYPASS` is NOT set in production
- [ ] Redis is on private network (not public internet)
- [ ] CORS origins whitelist is correct
- [ ] Session TTL is appropriate (default: 1 hour)
- [ ] HTTPS enforced (HTTP redirects to HTTPS)
- [ ] Cookies set with `httponly=True`, `secure=True`, `samesite="none"`
- [ ] AuthToken never sent to browser (stored only in Redis)
- [ ] Test account credentials rotated after testing

---

## Quick Reference

### Environment Variables

| Variable                | Required | Default                        | Description                     |
| ----------------------- | -------- | ------------------------------ | ------------------------------- |
| `MS_TENANT_ID`          | Yes      | -                              | MemberSuite tenant ID           |
| `MS_ASSOCIATION_ID`     | Yes      | -                              | Association GUID                |
| `REDIS_URL`             | Yes      | -                              | Redis connection string         |
| `SESSION_SECRET`        | Yes      | -                              | Session signing key (32+ chars) |
| `FRONTEND_URL`          | No       | Vercel URL                     | Frontend origin for redirects   |
| `MS_API_BASE_URL`       | No       | `https://rest.membersuite.com` | MemberSuite API base            |
| `SESSION_TTL_SECONDS`   | No       | `3600`                         | Session lifetime (1 hour)       |
| `MS_REQUIRE_MEMBERSHIP` | No       | `true`                         | Require active membership       |
| `DEV_AUTH_BYPASS`       | No       | `false`                        | Enable dev bypass (DEV ONLY)    |

### API Endpoints

| Endpoint          | Method | Description                 |
| ----------------- | ------ | --------------------------- |
| `/auth/status`    | GET    | Check auth configuration    |
| `/auth/login`     | GET    | Get MemberSuite login URL   |
| `/auth/callback`  | GET    | Handle MemberSuite callback |
| `/auth/me`        | GET    | Get current user info       |
| `/auth/logout`    | POST   | End session                 |
| `/auth/dev/login` | GET    | Dev bypass (local only)     |

### Common Commands

```bash
# Local dev with production callback
docker run -d -p 6379:6379 redis:7-alpine
python3 -m uvicorn app.main:app --reload

# Local dev with bypass (full local testing)
DEV_AUTH_BYPASS=true python3 -m uvicorn app.main:app --reload

# Production deploy
fly secrets set SESSION_SECRET="$(openssl rand -hex 32)"
fly deploy

# Monitor production
fly logs -f
fly ssh console
```

---

**Last Updated**: December 28, 2024
**Phase**: 3 (Authentication Routes)
**Status**: Testing and verification
