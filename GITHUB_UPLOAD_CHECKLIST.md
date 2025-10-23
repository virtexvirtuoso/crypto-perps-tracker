# GitHub Upload Checklist

## ✅ Pre-Upload Security Verification

### 1. Credentials Check
- [x] `.env` file exists and contains secrets
- [x] `.env` is in `.gitignore`
- [x] `.env.example` exists (safe template)
- [x] `config/config.yaml` uses `${VARIABLE}` syntax
- [x] No hardcoded webhook URLs in code

### 2. Sensitive Files Protected
```bash
# Files that MUST be gitignored:
.env                    ✅ Contains Discord webhook
.env.*                  ✅ All environment variants
data/*.html             ✅ Generated reports
data/*.txt              ✅ Report outputs
docs/                   ✅ Documentation (optional)
*.log                   ✅ Log files
__pycache__/            ✅ Python cache
.claude/                ✅ Editor config
```

### 3. Clean Repository
```bash
# Files safe to commit:
✅ README.md
✅ QUICK_START.md
✅ SECURITY_SETUP.md
✅ requirements.txt
✅ .gitignore
✅ .env.example
✅ config/config.yaml (with ${} variables)
✅ scripts/*.py
✅ src/**/*.py
```

## 📋 Upload Steps

### Step 1: Initialize Git Repository
```bash
cd /Users/ffv_macmini/Desktop/crypto-perps-tracker
git init
git add .
git status  # Verify .env is NOT staged
```

### Step 2: Verify No Secrets
```bash
# Check what will be committed:
git status

# Search for potential secrets:
git grep -i "discord.com/api/webhooks" -- ':(exclude).env' ':(exclude).env.example'
# Should return nothing!

# Check staged files don't contain secrets:
git diff --cached | grep -i "webhook"
```

### Step 3: Create Initial Commit
```bash
git commit -m "Initial commit: Crypto Perpetual Futures Market Report Generator

Features:
- Automated market reports with cyberpunk amber charts
- 9 exchange coverage (Binance, Bybit, OKX, etc.)
- Spot-futures basis analysis
- Funding rate arbitrage detection
- Discord integration with scheduled reports
- Enhanced executive summary for traders
- Secure .env configuration

Powered by Virtuoso Crypto | virtuosocrypto.com"
```

### Step 4: Create GitHub Repository
1. Go to https://github.com/new
2. Repository name: `crypto-perps-tracker`
3. Description: `📊 Automated crypto perpetual futures market report with charts & Discord integration`
4. **IMPORTANT:** Make it **Private** initially
5. Do NOT initialize with README (we have one)
6. Click "Create repository"

### Step 5: Push to GitHub
```bash
# Add remote
git remote add origin https://github.com/YOUR_USERNAME/crypto-perps-tracker.git

# Push to GitHub
git branch -M main
git push -u origin main
```

## 🔒 Post-Upload Security Verification

### On GitHub Website:
1. ✅ Navigate to repository
2. ✅ Click on Files → Verify `.env` is NOT there
3. ✅ Check `.env.example` IS there (template)
4. ✅ Open `config/config.yaml` → Verify shows `${DISCORD_WEBHOOK_URL}`
5. ✅ Check repository settings → Ensure it's Private

### Test Clone (Verify Security):
```bash
# Clone to temporary location
cd /tmp
git clone https://github.com/YOUR_USERNAME/crypto-perps-tracker.git test-clone
cd test-clone

# Verify .env doesn't exist:
ls -la .env  # Should show "No such file"

# Verify .env.example exists:
cat .env.example  # Should show template

# Clean up:
cd /tmp && rm -rf test-clone
```

## ⚠️ What If Secrets Were Accidentally Committed?

### Emergency Cleanup (If Webhook Exposed):
```bash
# 1. Regenerate Discord webhook immediately!
#    Go to Discord → Server Settings → Integrations → Webhooks → Edit → Regenerate URL

# 2. Update .env with new webhook:
echo "DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/NEW_ID/NEW_TOKEN" > .env

# 3. Remove from git history:
git filter-branch --force --index-filter \
  "git rm --cached --ignore-unmatch .env" \
  --prune-empty --tag-name-filter cat -- --all

# 4. Force push (DANGEROUS - only if just created repo):
git push origin --force --all
```

## 📊 Repository Details

**Name:** crypto-perps-tracker
**Visibility:** Private (recommended) or Public
**Topics:** `cryptocurrency`, `trading`, `market-analysis`, `discord-bot`, `perpetual-futures`, `binance`, `bybit`, `python`

**Description:**
```
📊 Automated cryptocurrency perpetual futures market report generator with
cyberpunk amber charts and Discord integration. Tracks 9 exchanges, analyzes
funding rates, spot-futures basis, and detects arbitrage opportunities.
```

**README Features to Highlight:**
- ⚡ Automated reports at 7am/7pm EST
- 📈 4 cyberpunk amber visualization charts
- 💰 Funding rate arbitrage detection
- 📊 Spot-futures basis analysis
- 🎯 Enhanced trader-focused executive summary
- 🔒 Secure .env credential management

## 🚀 Making Repository Public (Optional)

### Before Going Public:
1. ✅ Triple-check no credentials in commit history
2. ✅ Review all markdown files for sensitive info
3. ✅ Add LICENSE file (MIT recommended)
4. ✅ Ensure README has setup instructions
5. ✅ Remove any VPS-specific paths

### Make Public:
```
GitHub → Settings → Danger Zone → Change visibility → Make public
```

## 📝 Recommended .github Files (Optional)

### .github/workflows/security-scan.yml
```yaml
name: Security Scan
on: [push]
jobs:
  scan:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Check for secrets
        run: |
          ! git grep -i "discord.com/api/webhooks" -- ':(exclude).env.example'
```

---

**Status:** ✅ Ready for GitHub Upload
**Last Verified:** October 23, 2025
**Security Level:** Production-Ready
