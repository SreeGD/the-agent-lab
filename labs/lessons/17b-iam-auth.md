# 17b — IAM & Auth for Agentic Systems (Session 17b)

> **Agents need identity before they can collaborate safely.** A multi-agent system without IAM is a room full of people with no name badges, no roles, and no locked doors. This session covers OAuth2/OIDC for agent identity, service-to-service auth, scoped tool permissions, JWT claims, RBAC, and zero-trust agent boundaries.

---

## Roadmap — where this lesson sits

```
═══════ TRACK F: PRODUCTION ═══════

  ✓ Session 14: Evaluation (Ragas + LangSmith)
  ✓ Session 15: Cost Optimization
  ✓ Session 16: Streaming + Web UI
  ✓ Session 17: Production Deployment + Observability
  ▶ Session 17b: IAM & AUTH FOR AGENTIC SYSTEMS  ◄ HERE
  → Session 18: System Design Interview (Track G)
```

**Why here:** You've deployed agents (Session 17). Before those agents talk to each other or to external services, they need identity and access control. Without it, any agent can call any tool, impersonate any role, and access any data — a security and compliance disaster at scale.

---

## Files involved

| File | Role |
|---|---|
| [`iam_auth.py`](../iam_auth.py) | OAuth2 client credentials flow + JWT validation |
| [`agent_identity.py`](../agent_identity.py) | Agent identity registry + scoped permission enforcement |

---

## What problem it solves

In a human organisation, identity and access control is table stakes:
- Every employee has a unique identity (email + badge)
- Roles define what they can access (engineer, admin, read-only)
- Every sensitive action is logged with who did it

Agentic systems are organisations of software agents. The same requirements apply — but most teams add IAM as an afterthought, after they've already built the agents. That leads to:

- Agent A can call Agent B's APIs without authorisation
- No audit trail of which agent accessed which resource
- A compromised agent can do anything another agent can do
- No way to revoke an agent's access without killing it

IAM for agents means every agent has a cryptographic identity, every tool call is authorised, and every action is attributable.

---

## The analogy

OAuth2 + JWT for agents is exactly the same as OAuth2 + JWT for users — **the agent is the user**.

In human auth:
- User logs in → gets an access token → presents token to call APIs

In agent auth:
- Agent starts → authenticates with identity provider → gets an access token → presents token to call other agents or tools

The **client credentials flow** (no human in the loop) is the right OAuth2 grant type for agent-to-agent auth. The agent has a `client_id` and `client_secret`; it exchanges them for a token directly.

---

## Visual: agent auth flow

```
  ┌─────────────┐          ┌──────────────────┐
  │   Agent A   │          │  Identity Provider│
  │ (client)    │─────────►│  (Keycloak / Auth0│
  │             │  POST /token               / AWS Cognito)
  │             │  client_id + secret        │
  │             │◄─────────│  access_token    │
  └──────┬──────┘          └──────────────────┘
         │ Bearer access_token
         ▼
  ┌─────────────┐
  │   Agent B   │  validates token signature
  │ (resource   │  checks scope: "tool:database:read"
  │  server)    │  checks expiry
  │             │  logs: agent_a called database at 07:00Z
  └─────────────┘
```

---

## Key patterns

### 1. Client credentials flow (service-to-service)

```python
import httpx
from pydantic import BaseModel

class AgentCredentials(BaseModel):
    client_id: str
    client_secret: str
    token_url: str
    scopes: list[str]

class TokenResponse(BaseModel):
    access_token: str
    token_type: str
    expires_in: int
    scope: str

def get_agent_token(creds: AgentCredentials) -> TokenResponse:
    response = httpx.post(
        creds.token_url,
        data={
            "grant_type": "client_credentials",
            "client_id": creds.client_id,
            "client_secret": creds.client_secret,
            "scope": " ".join(creds.scopes),
        },
    )
    response.raise_for_status()
    return TokenResponse(**response.json())
```

### 2. JWT claims for agent context

JWTs carry claims — key-value pairs baked into the token at issuance. For agents, add custom claims that identify the agent's context:

```python
# What the JWT payload looks like for an agent token
{
    "sub": "agent:farm-planner:v2",       # agent identity
    "iss": "https://auth.company.com",    # issuer
    "aud": "https://api.company.com",     # intended recipient
    "exp": 1750000000,                    # expiry (Unix timestamp)
    "iat": 1749996400,                    # issued at
    "scope": "tool:database:read tool:llm:invoke",  # what it can do
    # Custom agent claims:
    "agent_version": "2.1.0",
    "agent_session_id": "sess_abc123",
    "parent_agent": "orchestrator:v1",    # who spawned this agent
    "task_id": "task_xyz789",             # for audit trail correlation
}
```

### 3. Token validation in a receiving agent

```python
import jwt
from jwt import PyJWKClient

JWKS_URL = "https://auth.company.com/.well-known/jwks.json"
AUDIENCE = "https://api.company.com"

jwks_client = PyJWKClient(JWKS_URL)

def validate_agent_token(token: str, required_scope: str) -> dict:
    signing_key = jwks_client.get_signing_key_from_jwt(token)

    payload = jwt.decode(
        token,
        signing_key.key,
        algorithms=["RS256"],
        audience=AUDIENCE,
    )

    # Check required scope
    granted_scopes = set(payload.get("scope", "").split())
    if required_scope not in granted_scopes:
        raise PermissionError(
            f"Token lacks required scope '{required_scope}'. "
            f"Granted: {granted_scopes}"
        )

    return payload
```

### 4. RBAC for multi-agent systems

Define roles at the agent level, not just the user level:

```python
from enum import Enum
from typing import Literal

AgentRole = Literal[
    "orchestrator",     # can spawn and direct sub-agents
    "specialist",       # can use domain tools, cannot spawn agents
    "read-only",        # can read data, cannot modify or call external APIs
    "privileged",       # can access sensitive data classes (medical, financial)
]

ROLE_SCOPES: dict[AgentRole, set[str]] = {
    "orchestrator": {
        "agent:spawn", "agent:delegate", "tool:*", "data:internal"
    },
    "specialist": {
        "tool:llm:invoke", "tool:database:read", "data:internal"
    },
    "read-only": {
        "tool:database:read", "data:public"
    },
    "privileged": {
        "tool:llm:invoke", "tool:database:read", "tool:database:write",
        "data:medical", "data:financial"
    },
}

def agent_can(role: AgentRole, scope: str) -> bool:
    allowed = ROLE_SCOPES.get(role, set())
    # Support wildcard: "tool:*" matches "tool:database:read"
    return scope in allowed or any(
        s.endswith(":*") and scope.startswith(s[:-1])
        for s in allowed
    )
```

### 5. API key lifecycle and rotation

Agent API keys are secrets — treat them like passwords:

```python
import secrets
import hashlib
from datetime import datetime, timedelta
from pydantic import BaseModel

class AgentApiKey(BaseModel):
    key_id: str
    agent_id: str
    key_hash: str          # store the hash, never the raw key
    created_at: datetime
    expires_at: datetime
    scopes: list[str]
    is_active: bool = True

def issue_api_key(agent_id: str, scopes: list[str], ttl_days: int = 90) -> tuple[str, AgentApiKey]:
    raw_key = f"agk_{secrets.token_urlsafe(32)}"  # prefix for easy identification
    key_id = f"key_{secrets.token_hex(8)}"

    record = AgentApiKey(
        key_id=key_id,
        agent_id=agent_id,
        key_hash=hashlib.sha256(raw_key.encode()).hexdigest(),
        created_at=datetime.utcnow(),
        expires_at=datetime.utcnow() + timedelta(days=ttl_days),
        scopes=scopes,
    )
    # store record in DB
    return raw_key, record  # return raw key ONCE; never store it

def validate_api_key(raw_key: str, db_record: AgentApiKey) -> bool:
    if not db_record.is_active:
        return False
    if datetime.utcnow() > db_record.expires_at:
        return False
    return hashlib.sha256(raw_key.encode()).hexdigest() == db_record.key_hash
```

### 6. Bearer token in A2A calls

From Session 1b (A2A), agents call each other via HTTP. Add Bearer auth:

```python
async def delegate_to_agent(
    agent_url: str,
    task: dict,
    token: str,
) -> dict:
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{agent_url}/tasks/send",
            json=task,
            headers={
                "Authorization": f"Bearer {token}",
                "X-Agent-Session-Id": current_session_id,
                "X-Task-Id": task["id"],
            },
        )
        response.raise_for_status()
        return response.json()
```

### 7. Zero-trust agent boundaries

Zero-trust means: **no agent trusts another agent by default**, even on the same network. Every call is authenticated and authorised regardless of source.

```python
# Zero-trust middleware for a FastAPI agent endpoint
from fastapi import Depends, HTTPException, Security
from fastapi.security import HTTPBearer

security = HTTPBearer()

async def require_scope(required_scope: str):
    async def dependency(credentials = Security(security)):
        token = credentials.credentials
        try:
            payload = validate_agent_token(token, required_scope)
            return payload
        except PermissionError as e:
            raise HTTPException(status_code=403, detail=str(e))
        except Exception as e:
            raise HTTPException(status_code=401, detail=f"Invalid token: {e}")
    return dependency

# Usage on any agent endpoint:
@app.post("/tasks/send")
async def receive_task(
    task: TaskRequest,
    agent_claims = Depends(require_scope("agent:delegate")),
):
    # At this point, agent_claims contains the verified JWT payload
    log_audit(agent_claims["sub"], "delegate_task", task.id)
    ...
```

---

## Run it

```bash
pip install python-jose httpx pyjwt cryptography

# Generate a test keypair (for local dev)
python -c "
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization
key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
print(key.private_bytes(serialization.Encoding.PEM,
    serialization.PrivateFormat.TraditionalOpenSSL,
    serialization.NoEncryption()).decode())
" > test_private_key.pem

python iam_auth.py     # demonstrates full auth flow
python agent_identity.py  # demonstrates RBAC + scope enforcement
```

---

## Walk-through

### Why client credentials, not authorization code flow

| Flow | When to use | Why not for agents |
|---|---|---|
| Authorization code | User logs in via browser | Agents have no browser |
| Implicit | Single-page apps | Deprecated; tokens in URLs |
| Client credentials | Service-to-service | **Correct for agents** |
| Device code | IoT / CLI tools | Requires human to approve |

Agents use **client credentials**: the agent has a `client_id` + `client_secret` (or mTLS cert), exchanges them directly for a token, no human involved.

### Token expiry and refresh

Agent tokens should be short-lived (15-60 minutes). Implement automatic refresh:

```python
from datetime import datetime, timezone
import threading

class TokenCache:
    def __init__(self, creds: AgentCredentials):
        self._creds = creds
        self._token: TokenResponse | None = None
        self._expires_at: datetime | None = None
        self._lock = threading.Lock()

    def get_token(self) -> str:
        with self._lock:
            now = datetime.now(timezone.utc)
            if self._token is None or now >= self._expires_at:
                self._token = get_agent_token(self._creds)
                self._expires_at = now + timedelta(
                    seconds=self._token.expires_in - 60  # 60s buffer
                )
            return self._token.access_token
```

### Audit trail for compliance

Every privileged action should produce an audit entry that answers: **who did what, to what, when, and why**:

```python
from pydantic import BaseModel

class AgentAuditEntry(BaseModel):
    timestamp: str
    agent_id: str           # from JWT sub claim
    agent_session_id: str   # from JWT custom claim
    parent_agent: str | None
    task_id: str | None
    action: str             # what the agent did
    resource: str           # what resource was accessed
    scope_used: str         # which scope authorised this
    outcome: str            # "success" / "denied" / "error"
    duration_ms: int
```

This table is what a SOC 2 or HIPAA auditor will ask for. Build it from day one.

---

## Try this

1. **Client credentials demo** — set up a local Keycloak (via Docker) or use Auth0's free tier. Register an agent as a confidential client. Run `iam_auth.py` to exchange credentials for a JWT. Decode the token at jwt.io and inspect the claims.

2. **RBAC scope check** — use `agent_can()` to test every combination of role × scope from the ROLE_SCOPES table. Add a new role `"audit-only"` that can only read logs, and verify it cannot invoke LLMs.

3. **Token validation** — issue a token, tamper with one character in the signature, and run `validate_agent_token()`. Verify it rejects the tampered token. Then let the token expire and verify the expiry check fires.

4. **A2A with auth** — extend the A2A demo from Session 1b to pass a Bearer token on every inter-agent HTTP call. Add the zero-trust middleware to the specialist agent. Verify an unauthenticated call returns 401.

5. **Audit trail** — add an `AgentAuditEntry` to every tool call in the farm planner engine (Session 34). After a plan run, dump the audit log. Answer from the log alone: which agent called the database, at what time, and with which scope?

---

## Mental model in one line

> **IAM for agents is OAuth2 client credentials flow: every agent has a client_id + secret, exchanges them for a short-lived JWT, presents the JWT as a Bearer token on every call, and every receiving service validates the token signature and required scope before processing — zero-trust, all the way down.**

---

## Related

- **Previous:** [Session 17 — Production Deployment + Observability](28-production-deploy.md)
- **Next:** [Session 18 — System Design Interview](30-system-design.md)
- **Agent-to-agent calls that need auth:** [Session 1b — A2A Protocol](12b-a2a-protocol.md)
- **Governance + audit trail:** [Session 20 — AI Governance & Audit](32-governance.md)
- **Zero-trust in action:** [Session 19 — Red-teaming & Compliance](31-red-teaming.md)
- **Curriculum tracker:** Session 17b of 46
