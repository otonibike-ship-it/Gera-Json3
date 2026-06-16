# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**AUTOMAÇÃO HYBRIS - GERADOR DE JSONs** is a web application that generates JSON files for payment binding in the Hybris e-commerce platform. Reduces processing time from 5-10 minutes to <30 seconds and errors from ~10% to <1%.

**Technology Stack:**
- Python 3.7+
- Streamlit (web interface)
- PostgreSQL (user authentication source of truth)
- streamlit-authenticator (authentication layer)
- psycopg2 (PostgreSQL driver)
- No other external dependencies for JSON generation logic

**Deployment:**
- Docker container via Coolify
- Deployed on Hostinger VPS (Ubuntu 24.04)
- IP: 72.61.58.41
- PostgreSQL container: Port mapping 3000:5432

---

## Project Structure

```
├── src/                          # Main source code
│   ├── app_streamlit.py          # Web app + authentication
│   ├── hybris_json_generator.py  # JSON generation logic
│   └── postgres_manager.py       # PostgreSQL operations
├── tools/                        # Diagnostic and maintenance scripts
│   ├── diagnostico_completo.py   # 3-layer auth diagnostic
│   ├── debug_sync.py             # Manual sync test
│   ├── verificar_usuarios_postgres.py
│   └── migrate_users_to_postgres.py
├── docs/                         # Consolidated documentation
│   ├── ESTRUTURA_PROJETO.md      # Project map (START HERE)
│   ├── AUTENTICACAO.md           # Auth system details
│   ├── TROUBLESHOOTING.md        # Problem resolution
│   └── CONEXAO_DBEAVER_COOLIFY_HOSTINGER.md
├── examples/                     # Sample JSON outputs
├── Dockerfile                    # Container definition
├── .dockerignore                 # Docker ignore rules
└── requirements.txt              # Python dependencies
```

---

## Common Commands

### Running Locally

```bash
# Install dependencies
pip install -r requirements.txt

# Run Streamlit app
streamlit run src/app_streamlit.py

# Access at http://localhost:8501
```

### Docker Build

```bash
# Build image
docker build -t hybris-generator .

# Run container
docker run -p 8501:8501 hybris-generator

# IMPORTANT: After reorganization, ensure Dockerfile copies tools/
# Line should be: COPY tools/ ./tools/
```

### Diagnostics (When Auth Issues Occur)

```bash
# Full 3-layer diagnostic (PostgreSQL → config.yaml → authenticator)
python tools/diagnostico_completo.py

# Verify PostgreSQL users
python tools/verificar_usuarios_postgres.py

# Test manual sync
python tools/debug_sync.py
```

---

## Architecture Overview

### Authentication System (Critical - Most Recent Changes)

**Three-Layer Synchronization:**

```
PostgreSQL (Source of Truth)
    ↓ [startup: load_credentials()]
credentials.json (backup)
    ↓ [startup: sync_credentials_to_config()]
config.yaml (cache for authenticator)
    ↓ [startup: load_authenticator()]
streamlit-authenticator (validates login)
```

**Critical Functions in `src/app_streamlit.py`:**

1. **`load_credentials()`** (line 90)
   - Loads users from PostgreSQL
   - Fallback to credentials.json if DB unavailable
   - Returns dict: `{"users": {...}, "version": "1.0"}`

2. **`sync_credentials_to_config(credentials_data)`** (line 155)
   - Converts PostgreSQL format → config.yaml format
   - Creates/updates config.yaml
   - **MUST be defined BEFORE being called** (Python execution order matters!)

3. **`load_authenticator()`** (line 28)
   - Reads config.yaml
   - Creates streamlit-authenticator object
   - Returns authenticator instance

**Startup Sequence** (lines 847-880 in app_streamlit.py):
```python
# PASSO 1: Load from PostgreSQL
credentials = load_credentials()

# PASSO 2: Sync to config.yaml
sync_credentials_to_config(credentials)

# PASSO 3: Initialize authenticator
authenticator = load_authenticator()

# PASSO 4: Render login widget
authenticator.login()
```

**PostgreSQL Connection** (src/postgres_manager.py):
- Host: `u48cw44ccwg4sowco4044goc` (internal hostname, use IP 72.61.58.41 externally)
- Port: 5432 (internally), mapped to 3000 on VPS host
- Database: `postgres`
- User: `postgres`
- Password: `poMaf572450+@`
- Table: `usuarios` with 4 users (marco, marcos.fernandes, kennedy.oliveira, alisson.galvao)

### JSON Generation Logic

**HybrisJSONGenerator** (src/hybris_json_generator.py):
- **Amount Handling:** All monetary values in centavos (integers). R$ 150.50 = 15050
- **Timestamp Format:** ISO 8601 UTC (e.g., "2024-10-24T15:30:00Z")
- **Transaction Types:**
  - PIX (product code 25)
  - DEBITO (product code 2000)
  - CREDITO (product code 1000) - supports 1-24 installments
  - MULTIPLAS - combines 2+ payment types

**Key Methods:**
- `create_base_order()` - Base order structure
- `create_pix_transaction()` - PIX payments
- `create_debit_transaction()` - Debit cards
- `create_credit_transaction()` - Credit cards with installments
- `create_multiplas_transaction()` - Multiple payment combinations
- `generate_json()` - Main entry point

---

## Critical Issues & Solutions

### Issue: "User not authorized" (Only 1 user can login)

**Root Cause:** PostgreSQL has 4 users but config.yaml has only 1 (sync failed)

**Diagnostic:**
```bash
python tools/diagnostico_completo.py
# Shows: PostgreSQL: 4 users, config.yaml: 1 user → NOT SYNCED
```

**Solution:** Function call order in Python matters!
- `sync_credentials_to_config()` must be DEFINED (line 155) BEFORE being CALLED (line 866)
- If called before definition → NameError
- Fixed in commit 982173e by moving startup block after all function definitions

### Issue: Dockerfile Fails After Reorganization

**Root Cause:** Scripts moved from root to `tools/` but Dockerfile still references root

**Solution:**
```dockerfile
# OLD (breaks):
COPY diagnostico_completo.py .
COPY debug_sync.py .

# NEW (works):
COPY tools/ ./tools/
```

Also update `.dockerignore`:
```
!tools/  # Must explicitly include
```

### Issue: DBeaver Cannot Connect to PostgreSQL

**Root Cause:** Hostname `u48cw44ccwg4sowco4044goc` is internal to VPS

**Solutions:**
1. Use IP instead: `72.61.58.41`
2. Use correct port mapping: Port `3000` (not 5432) due to Coolify mapping `3000:5432`
3. Verify firewall: `sudo ufw allow 3000/tcp`

See: `docs/CONEXAO_DBEAVER_COOLIFY_HOSTINGER.md`

---

## Important Patterns

### Function Definition Order (Python Module-Level Code)

**CRITICAL:** In `app_streamlit.py`, startup code executes at module level (not inside `if __name__ == "__main__"`).

Functions MUST be defined BEFORE being called:

```python
# ✅ CORRECT ORDER:
def sync_credentials_to_config(...):  # Line 155
    pass

# ... later in file ...

sync_credentials_to_config(credentials)  # Line 866 - OK!

# ❌ WRONG ORDER (causes NameError):
sync_credentials_to_config(credentials)  # Line 169 - ERROR!

def sync_credentials_to_config(...):  # Line 265 - Too late!
    pass
```

### Logging for Visibility

Use `sys.stdout.flush()` after prints in Docker/Coolify environments:

```python
print("[startup] PASSO 1: Carregando credenciais")
sys.stdout.flush()  # CRITICAL for logs to appear immediately
```

### PostgreSQL as Source of Truth

- PostgreSQL is authoritative for user credentials
- credentials.json is backup only
- config.yaml is auto-generated cache
- NEVER edit config.yaml manually (will be overwritten)

---

## Debugging Authentication Issues

### Step 1: Verify PostgreSQL

```bash
python tools/verificar_usuarios_postgres.py
# Expected: 4 users listed
```

### Step 2: Test Sync

```bash
python tools/debug_sync.py
# Expected: "Usuarios salvos no config.yaml: ['marco', 'marcos.fernandes', ...]"
```

### Step 3: Full Diagnostic

```bash
python tools/diagnostico_completo.py
# Checks all 3 layers + compares
```

### Step 4: Check Startup Logs

Look for in Coolify logs:
```
[startup] PASSO 1: Carregando credenciais
[startup] Usuarios carregados: ['marco', 'marcos.fernandes', 'kennedy.oliveira', 'alisson.galvao']
[startup] PASSO 2: Sincronizando para config.yaml
[startup] OK: Sincronizacao concluida com sucesso
[load_authenticator] OK: Authenticator inicializado com 4 usuarios
```

If missing any step → problem in that layer.

---

## Docker & Deployment

### Dockerfile Structure

1. Base: Python 3.11-slim
2. Install system dependencies (ca-certificates)
3. Copy requirements.txt → Install deps
4. Copy src/, tools/, img/, .streamlit/
5. Copy credentials.json, config.yaml (auto-generated)
6. Expose 8501
7. CMD: `streamlit run src/app_streamlit.py --server.port=8501 --server.address=0.0.0.0`

### .dockerignore Rules

- Ignore: docs/, tests/, venv/, *.md, *.log
- Keep: !src/, !tools/, !img/, !requirements.txt, !credentials.json, !config.yaml

### Coolify Deployment

- Rebuild required (not just redeploy) after file reorganization
- Check port mappings for PostgreSQL (3000:5432)
- Verify environment variables if using (DB_HOST, DB_PORT, etc.)

---

## Documentation Map

**For New Users:**
- `docs/ESTRUTURA_PROJETO.md` - Project structure overview
- `docs/GUIA_USO.md` - How to use the app

**For Developers:**
- `docs/AUTENTICACAO.md` - Authentication system deep dive
- `docs/TROUBLESHOOTING.md` - Common problems & solutions

**For DevOps:**
- `docs/CONEXAO_DBEAVER_COOLIFY_HOSTINGER.md` - Database connection
- `docs/DOCKER_CONFIG_CORRECTIONS.md` - Docker setup issues

**Historical (for reference):**
- `docs/HISTORICO_*` - Investigation and fix documentation

---

## Key Constraints

- Python 3.7+ required
- PostgreSQL must be accessible (or app uses fallback to credentials.json)
- Port 8501 for Streamlit
- Port 3000 for PostgreSQL access (Coolify mapping)
- All monetary values in centavos (multiply by 100)
- Timestamps in UTC ISO 8601
- config.yaml is auto-generated (don't edit manually)
