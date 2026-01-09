# UPager License Server

Flask-based license validation server for UPager.

## Endpoints

- `POST /activate` - Activate a license
- `POST /verify` - Verify a license
- `POST /deactivate` - Deactivate a license
- `POST /admin/create` - Create new license (requires admin_secret)
- `GET /health` - Health check
- `GET /admin/stats` - License statistics

## Environment Variables

- `PORT` - Server port (default: 5001)
- `UPAGER_ADMIN_SECRET` - Admin authentication secret

## Local Development
```bash
pip install -r requirements.txt
python license_server.py
```

## Creating Licenses
```bash
python create_license.py email@example.com pro_lifetime



```


# 🔐 UPager License Server

Flask-based license validation server with **GitHub persistence** for Render free tier.

## 🌟 Features

- ✅ **GitHub Backup** - Automatic persistence to GitHub (survives Render restarts)
- ✅ **Free Tier Compatible** - Works with Render + GitHub free tiers
- ✅ **Auto-Recovery** - Restores data automatically when server wakes up
- ✅ **Rate Limited** - Smart backup cooldown to avoid API abuse
- ✅ **License Types** - Lifetime and annual billing support
- ✅ **Multi-Activation** - Support for multiple machine activations

---

## 📋 Endpoints

### Public Endpoints
- `POST /activate` - Activate a license on a machine
- `POST /verify` - Verify a license is valid
- `POST /deactivate` - Deactivate a license from a machine
- `GET /health` - Health check and status

### Admin Endpoints (requires `admin_secret`)
- `POST /admin/create` - Create new license
- `POST /admin/backup` - Manual backup to GitHub
- `POST /admin/restore` - Manual restore from GitHub

---

## 🚀 Deployment Setup

### 1. GitHub Setup

Create a **private repository** on GitHub:
```
Repository: upager-license-backup
Visibility: Private
Initialize: Yes (with README)
```

Generate a **Personal Access Token**:
- Go to: Settings → Developer settings → Personal access tokens → Tokens (classic)
- Generate new token with scope: `repo` (full control)
- Copy the token (starts with `ghp_`)

### 2. Render Setup

Deploy to Render with these environment variables:

```bash
GITHUB_TOKEN=ghp_your_token_here
GITHUB_REPO=YourUsername/upager-license-backup
GITHUB_BRANCH=main
UPAGER_ADMIN_SECRET=?
PORT=5001
```

### 3. Repository Setup

Push your code to your Git repository:
```bash
git init
git add .
git commit -m "Initial commit"
git remote add origin https://github.com/YourUsername/upager-license-server.git
git push -u origin main
```

Connect the repository to Render and deploy.

---

## 💻 Local Development

### Install Dependencies
```bash
pip install -r requirements.txt
```

### Set Environment Variables
```bash
export UPAGER_ADMIN_SECRET="?"
export GITHUB_TOKEN="ghp_your_token_here"
export GITHUB_REPO="YourUsername/upager-license-backup"
```

### Run Server
```bash
python license_server.py
```

Server will start at `http://localhost:5001`

---

## 🎫 Creating Licenses

### Basic Usage
```bash
# Create pro lifetime license
python create_license.py customer@example.com

# Create pro annual license
python create_license.py customer@example.com pro_annual

# Create enterprise license with 5 activations
python create_license.py business@example.com enterprise_lifetime 5
```

### Check Server Health
```bash
python create_license.py health
```

### Manual Backup/Restore
```bash
# Force backup to GitHub
python create_license.py backup

# Force restore from GitHub
python create_license.py restore
```

---

## 📚 Available License Tiers

| Tier | Billing | Features |
|------|---------|----------|
| `free` | N/A | Free tier features |
| `pro_lifetime` | One-time | Pro features, lifetime license |
| `pro_annual` | Annual | Pro features, annual renewal |
| `enterprise_lifetime` | One-time | Enterprise features, lifetime license |
| `enterprise_annual` | Annual | Enterprise features, annual renewal |

---

## 🔌 API Usage Examples

### Activate License
```bash
curl -X POST https://upager-license-server.onrender.com/activate \
  -H "Content-Type: application/json" \
  -d '{
    "key": "UPAGER-XXXX-XXXX-XXXX-XXXX",
    "email": "customer@example.com",
    "machine_id": "unique-machine-id",
    "ip": "192.168.1.1"
  }'
```

### Verify License
```bash
curl -X POST https://upager-license-server.onrender.com/verify \
  -H "Content-Type: application/json" \
  -d '{
    "key": "UPAGER-XXXX-XXXX-XXXX-XXXX",
    "machine_id": "unique-machine-id"
  }'
```

### Deactivate License
```bash
curl -X POST https://upager-license-server.onrender.com/deactivate \
  -H "Content-Type: application/json" \
  -d '{
    "key": "UPAGER-XXXX-XXXX-XXXX-XXXX",
    "machine_id": "unique-machine-id"
  }'
```

---

## 🔧 How It Works

### GitHub Persistence Strategy

1. **On Server Start**: Downloads `licenses.json` from GitHub and restores to SQLite
2. **On License Changes**: Exports SQLite to JSON and uploads to GitHub (30s cooldown)
3. **On Render Restart**: Automatically restores from GitHub backup

### Why This Works for Free Tiers

- **No Git Clone**: Uses GitHub REST API (faster, lighter, no disk space)
- **Rate Limiting**: 30-second cooldown between backups
- **Ephemeral Storage**: Uses `/tmp` directory (Render requirement)
- **Automatic Recovery**: Always restores latest data on wake-up

---

## 🛠️ Troubleshooting

### Server Returns 404/503
- **Reason**: Render free tier puts server to sleep after inactivity
- **Solution**: First request wakes it up (takes ~30 seconds), then retry

### GitHub Backup Failing
- **Check**: `GITHUB_TOKEN` is set correctly in Render environment
- **Check**: Token has `repo` scope
- **Check**: Repository exists and is accessible

### License Not Found After Restart
- **Check**: GitHub backup was successful before restart
- **Solution**: Run manual restore: `python create_license.py restore`

---

## 📊 File Structure

```
upager-license-server/
├── license_server.py      # Main Flask server
├── create_license.py      # CLI tool for creating licenses
├── requirements.txt       # Python dependencies
├── Procfile              # Render deployment config
├── .gitignore            # Git ignore rules
└── README.md             # This file
```

---

## 🔒 Security Notes

- Never commit `UPAGER_ADMIN_SECRET` to Git
- Keep GitHub token secure (use environment variables)
- Use private GitHub repository for license data
- License keys are generated with `secrets.token_hex()` (cryptographically secure)

---

## 📝 License

Proprietary - UPager Project

---

## 🆘 Support

For issues or questions, contact the development team.