# Security Setup Guide

## Overview
Sensitive credentials are now stored in environment variables using `.env` files, not hardcoded in configuration files.

## Files Created

### `.env` (Local & VPS)
Contains actual sensitive credentials:
```bash
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/YOUR_ACTUAL_WEBHOOK
```

**⚠️ IMPORTANT:** This file is gitignored and should NEVER be committed to version control.

### `.env.example`
Template file showing required environment variables (no real values):
```bash
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/YOUR_WEBHOOK_ID/YOUR_WEBHOOK_TOKEN
```

**✅ Safe to commit:** This file can be shared publicly as a template.

## How It Works

### 1. Environment Variables Are Loaded
The script automatically loads `.env` file at startup:
```python
from dotenv import load_dotenv
load_dotenv()  # Loads .env from project root
```

### 2. Config References Environment Variables
`config/config.yaml` now uses variable substitution:
```yaml
discord:
  webhook_url: "${DISCORD_WEBHOOK_URL}"  # Loaded from .env
```

### 3. Script Expands Variables
The code automatically expands `${VARIABLE_NAME}` syntax:
```python
if webhook_url.startswith('${') and webhook_url.endswith('}'):
    env_var = webhook_url[2:-1]  # Extract variable name
    webhook_url = os.getenv(env_var)  # Get from environment
```

## Security Benefits

✅ **Credentials Not in Git:** `.env` is gitignored, protecting secrets
✅ **Easy Rotation:** Change webhook without editing code
✅ **Environment-Specific:** Different `.env` files for dev/staging/prod
✅ **No Hardcoded Secrets:** All sensitive data externalized
✅ **Team-Friendly:** Each developer has their own `.env`

## Setup on New Machine

1. Copy `.env.example` to `.env`:
   ```bash
   cp .env.example .env
   ```

2. Edit `.env` with real credentials:
   ```bash
   nano .env  # or your preferred editor
   ```

3. Install python-dotenv:
   ```bash
   pip3 install python-dotenv
   # or on VPS: sudo apt install python3-dotenv
   ```

4. Run normally - `.env` is loaded automatically!

## Adding New Secrets

### Step 1: Add to `.env`
```bash
echo "MY_NEW_SECRET=abc123" >> .env
```

### Step 2: Update `.env.example`
```bash
echo "MY_NEW_SECRET=your_secret_here" >> .env.example
```

### Step 3: Use in Code
```python
import os
my_secret = os.getenv('MY_NEW_SECRET')
```

## Security Checklist

- [x] `.env` added to `.gitignore`
- [x] `.env.example` created (safe to commit)
- [x] `python-dotenv` installed locally
- [x] `python-dotenv` installed on VPS
- [x] Discord webhook moved to environment variable
- [x] Config updated to use `${VARIABLE}` syntax
- [x] Code updated to expand environment variables
- [x] Tested and working on VPS

## Current Protected Credentials

| Variable | Purpose | Location |
|----------|---------|----------|
| `DISCORD_WEBHOOK_URL` | Market report Discord notifications | `.env` |

## Future Additions

When you need exchange API keys, add them like this:

```bash
# .env
BINANCE_API_KEY=your_binance_key
BINANCE_API_SECRET=your_binance_secret
BYBIT_API_KEY=your_bybit_key
BYBIT_API_SECRET=your_bybit_secret
```

Then use in code:
```python
binance_key = os.getenv('BINANCE_API_KEY')
binance_secret = os.getenv('BINANCE_API_SECRET')
```

## Troubleshooting

### "ModuleNotFoundError: No module named 'dotenv'"
Install python-dotenv:
```bash
pip3 install python-dotenv
# or: sudo apt install python3-dotenv
```

### "Discord webhook not working"
Check `.env` file exists and contains correct webhook URL:
```bash
cat .env | grep DISCORD_WEBHOOK_URL
```

### "Config shows ${DISCORD_WEBHOOK_URL} literally"
The environment variable expansion code is working. The `${}` syntax in config.yaml is correct - it gets replaced at runtime.

---

**Last Updated:** October 23, 2025
**Security Status:** ✅ Production-Ready
