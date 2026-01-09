#!/usr/bin/env python3
"""
UPager License Server - GitHub Persistence for Render Free Tier
Optimized for minimal GitHub API calls and reliable data persistence
"""

from flask import Flask, request, jsonify
from flask_cors import CORS
import sqlite3
import secrets
import logging
from datetime import datetime, timedelta
import os
import json
import requests
from base64 import b64encode, b64decode
import time

app = Flask(__name__)
CORS(app)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# ============================================
# CONFIGURATION
# ============================================

# Paths (Render-safe /tmp directory)
DB_FILE = "/tmp/licenses.db"

# GitHub Configuration
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN")
GITHUB_REPO = os.environ.get("GITHUB_REPO", "Upager/upager-license-backup")
GITHUB_BRANCH = os.environ.get("GITHUB_BRANCH", "main")
GITHUB_FILE_PATH = "licenses.json"

# Rate limiting for GitHub API (stay within free tier)
LAST_BACKUP_TIME = 0
BACKUP_COOLDOWN = 30  # seconds between backups
MAX_RETRIES = 3

# ============================================
# GITHUB API FUNCTIONS (Direct API - No Git Clone)
# ============================================

def github_api_headers():
    """Get headers for GitHub API"""
    if not GITHUB_TOKEN:
        return None
    return {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json"
    }

def get_file_from_github():
    """Download licenses.json from GitHub using API"""
    try:
        if not GITHUB_TOKEN:
            logging.warning("⚠️ No GitHub token - running without persistence")
            return None
        
        url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{GITHUB_FILE_PATH}"
        params = {"ref": GITHUB_BRANCH}
        
        response = requests.get(url, headers=github_api_headers(), params=params, timeout=10)
        
        if response.status_code == 404:
            logging.info("📁 licenses.json doesn't exist yet - will create on first backup")
            return {"licenses": [], "activations": []}
        
        if response.status_code == 200:
            content = response.json()
            data = json.loads(b64decode(content["content"]).decode("utf-8"))
            logging.info(f"✅ Downloaded from GitHub: {len(data.get('licenses', []))} licenses")
            return data
        
        logging.error(f"❌ GitHub download failed: {response.status_code}")
        return None
        
    except Exception as e:
        logging.error(f"❌ GitHub download error: {e}")
        return None

def save_file_to_github(data):
    """Upload licenses.json to GitHub using API"""
    global LAST_BACKUP_TIME
    
    try:
        if not GITHUB_TOKEN:
            logging.warning("⚠️ No GitHub token - skipping backup")
            return False
        
        # Rate limiting
        now = time.time()
        if now - LAST_BACKUP_TIME < BACKUP_COOLDOWN:
            logging.info("⏳ Backup cooldown active - skipping")
            return True
        
        LAST_BACKUP_TIME = now
        
        # Get current file SHA (needed for updates)
        url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{GITHUB_FILE_PATH}"
        params = {"ref": GITHUB_BRANCH}
        response = requests.get(url, headers=github_api_headers(), params=params, timeout=10)
        
        sha = None
        if response.status_code == 200:
            sha = response.json()["sha"]
        
        # Prepare content
        content = json.dumps(data, indent=2)
        encoded_content = b64encode(content.encode("utf-8")).decode("utf-8")
        
        # Upload/update file
        payload = {
            "message": f"Backup: {len(data.get('licenses', []))} licenses, {len(data.get('activations', []))} activations",
            "content": encoded_content,
            "branch": GITHUB_BRANCH
        }
        
        if sha:
            payload["sha"] = sha  # Update existing file
        
        response = requests.put(url, headers=github_api_headers(), json=payload, timeout=15)
        
        if response.status_code in [200, 201]:
            logging.info(f"✅ Backed up to GitHub: {len(data.get('licenses', []))} licenses")
            return True
        else:
            logging.error(f"❌ GitHub upload failed: {response.status_code} - {response.text}")
            return False
            
    except Exception as e:
        logging.error(f"❌ GitHub upload error: {e}")
        return False

# ============================================
# DATABASE FUNCTIONS
# ============================================

def init_db():
    """Initialize SQLite database"""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    
    c.execute("""
        CREATE TABLE IF NOT EXISTS licenses (
            license_key TEXT PRIMARY KEY,
            email TEXT NOT NULL,
            type TEXT NOT NULL,
            tier TEXT NOT NULL,
            billing_type TEXT NOT NULL,
            status TEXT NOT NULL,
            created_at TEXT NOT NULL,
            activated_at TEXT,
            expires_at TEXT,
            max_activations INTEGER DEFAULT 1,
            current_activations INTEGER DEFAULT 0
        )
    """)
    
    c.execute("""
        CREATE TABLE IF NOT EXISTS activations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            license_key TEXT NOT NULL,
            machine_id TEXT NOT NULL,
            ip_address TEXT,
            activated_at TEXT NOT NULL,
            last_verified TEXT,
            status TEXT NOT NULL,
            UNIQUE(license_key, machine_id)
        )
    """)
    
    conn.commit()
    conn.close()
    logging.info("✅ Database initialized")

def export_db_to_json():
    """Export current database to JSON format"""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    
    # Export licenses
    c.execute("SELECT * FROM licenses")
    cols = [d[0] for d in c.description]
    licenses = [dict(zip(cols, row)) for row in c.fetchall()]
    
    # Export activations
    c.execute("SELECT * FROM activations")
    cols = [d[0] for d in c.description]
    activations = [dict(zip(cols, row)) for row in c.fetchall()]
    
    conn.close()
    
    return {
        "backup_date": datetime.utcnow().isoformat(),
        "licenses": licenses,
        "activations": activations
    }

def import_json_to_db(data):
    """Import JSON data into database"""
    if not data:
        return False
    
    try:
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        
        # Clear existing data
        c.execute("DELETE FROM activations")
        c.execute("DELETE FROM licenses")
        
        # Import licenses
        for lic in data.get("licenses", []):
            c.execute("""
                INSERT INTO licenses VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                lic["license_key"], lic["email"], lic["type"], lic["tier"],
                lic["billing_type"], lic["status"], lic["created_at"],
                lic.get("activated_at"), lic.get("expires_at"),
                lic["max_activations"], lic["current_activations"]
            ))
        
        # Import activations
        for act in data.get("activations", []):
            c.execute("""
                INSERT INTO activations (license_key, machine_id, ip_address, 
                                        activated_at, last_verified, status)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                act["license_key"], act["machine_id"], act.get("ip_address"),
                act["activated_at"], act["last_verified"], act["status"]
            ))
        
        conn.commit()
        conn.close()
        
        logging.info(f"✅ Restored: {len(data.get('licenses', []))} licenses, {len(data.get('activations', []))} activations")
        return True
        
    except Exception as e:
        logging.error(f"❌ Import failed: {e}")
        return False

# ============================================
# STARTUP SEQUENCE
# ============================================

def startup_restore():
    """Restore data from GitHub on startup"""
    logging.info("🔄 Restoring data from GitHub...")
    
    init_db()
    
    data = get_file_from_github()
    if data:
        import_json_to_db(data)
        return True
    else:
        logging.warning("⚠️ No GitHub data found - starting fresh")
        return False

# Run startup restore
startup_restore()

# ============================================
# BACKUP HELPER
# ============================================

def backup_to_github():
    """Backup current database to GitHub"""
    data = export_db_to_json()
    return save_file_to_github(data)

# ============================================
# LICENSE FUNCTIONS
# ============================================

def generate_license_key():
    """Generate license key: UPAGER-XXXX-XXXX-XXXX-XXXX"""
    hex_str = secrets.token_hex(8).upper()
    parts = [hex_str[i:i+4] for i in range(0, 16, 4)]
    return f"UPAGER-{'-'.join(parts)}"

def create_license(email, tier, max_activations=1):
    """Create new license"""
    key = generate_license_key()
    
    license_type = "pro" if tier.startswith("pro") else "free"
    billing_type = "one-time" if "lifetime" in tier else "annual"
    
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    
    try:
        c.execute("""
            INSERT INTO licenses VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            key, email, license_type, tier, billing_type,
            "active", datetime.utcnow().isoformat(),
            None, None, max_activations, 0
        ))
        
        conn.commit()
        logging.info(f"✅ Created {tier} license: {key}")
        
        backup_to_github()
        return key
        
    except Exception as e:
        logging.error(f"❌ License creation failed: {e}")
        return None
    finally:
        conn.close()

# ============================================
# API ENDPOINTS
# ============================================

@app.route('/activate', methods=['POST'])
def activate():
    """Activate license on machine"""
    data = request.get_json()
    
    key = data.get('key', '').strip().upper()
    email = data.get('email', '').strip()
    machine_id = data.get('machine_id', '').strip()
    ip = data.get('ip', request.remote_addr)
    
    if not all([key, email, machine_id]):
        return jsonify({"success": False, "error": "Missing fields"}), 400
    
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    
    try:
        # Get license
        c.execute("""
            SELECT type, tier, billing_type, status, email, 
                   max_activations, current_activations, expires_at
            FROM licenses WHERE license_key = ?
        """, (key,))
        
        lic = c.fetchone()
        if not lic:
            return jsonify({"success": False, "error": "Invalid license"}), 404
        
        (license_type, tier, billing_type, status, lic_email, 
         max_activations, current_activations, expires_at) = lic
        
        if status != "active":
            return jsonify({"success": False, "error": f"License is {status}"}), 403
        
        if email.lower() != lic_email.lower():
            return jsonify({"success": False, "error": "Email mismatch"}), 403
        
        # Check existing activation
        c.execute("""
            SELECT id FROM activations 
            WHERE license_key = ? AND machine_id = ?
        """, (key, machine_id))
        
        existing = c.fetchone()
        
        if existing:
            # Update existing
            c.execute("""
                UPDATE activations 
                SET last_verified = ?, ip_address = ?, status = 'active'
                WHERE license_key = ? AND machine_id = ?
            """, (datetime.utcnow().isoformat(), ip, key, machine_id))
        else:
            # New activation
            if current_activations >= max_activations:
                return jsonify({"success": False, "error": f"Max activations reached ({max_activations})"}), 403
            
            c.execute("""
                INSERT INTO activations 
                (license_key, machine_id, ip_address, activated_at, last_verified, status)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (key, machine_id, ip, datetime.utcnow().isoformat(), 
                  datetime.utcnow().isoformat(), "active"))
            
            c.execute("""
                UPDATE licenses 
                SET current_activations = current_activations + 1,
                    activated_at = COALESCE(activated_at, ?)
                WHERE license_key = ?
            """, (datetime.utcnow().isoformat(), key))
        
        conn.commit()
        
        # Calculate expiry
        now = datetime.utcnow()
        if billing_type == "one-time":
            license_expires = None
            maintenance_expires = (now + timedelta(days=365)).isoformat()
        else:
            license_expires = (now + timedelta(days=365)).isoformat()
            maintenance_expires = license_expires
        
        backup_to_github()
        
        return jsonify({
            "success": True,
            "license": {
                "type": license_type,
                "tier": tier,
                "billing_type": billing_type,
                "expires": license_expires,
                "maintenance_expires": maintenance_expires
            }
        })
        
    except Exception as e:
        logging.error(f"❌ Activation error: {e}")
        return jsonify({"success": False, "error": "Internal error"}), 500
    finally:
        conn.close()

@app.route('/verify', methods=['POST'])
def verify():
    """Verify license"""
    data = request.get_json()
    
    key = data.get('key', '').strip().upper()
    machine_id = data.get('machine_id', '').strip()
    
    if not all([key, machine_id]):
        return jsonify({"valid": False, "error": "Missing fields"}), 400
    
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    
    try:
        c.execute("""
            SELECT l.type, l.tier, l.billing_type, l.status, l.expires_at,
                   a.status as activation_status, a.activated_at
            FROM licenses l
            LEFT JOIN activations a ON l.license_key = a.license_key 
                AND a.machine_id = ?
            WHERE l.license_key = ?
        """, (machine_id, key))
        
        row = c.fetchone()
        if not row:
            return jsonify({"valid": False, "error": "Invalid license"})
        
        (license_type, tier, billing_type, license_status, 
         expires_at, activation_status, activated_at) = row
        
        if license_status != "active":
            return jsonify({"valid": False, "error": f"License {license_status}"})
        
        if not activation_status:
            return jsonify({"valid": False, "error": "Not activated on this machine"})
        
        # Check expiry
        if billing_type == "annual" and expires_at:
            if datetime.utcnow() > datetime.fromisoformat(expires_at):
                return jsonify({"valid": False, "error": "License expired"})
        
        # Update last verified
        c.execute("""
            UPDATE activations 
            SET last_verified = ?
            WHERE license_key = ? AND machine_id = ?
        """, (datetime.utcnow().isoformat(), key, machine_id))
        
        conn.commit()
        
        # Calculate maintenance expiry
        if billing_type == "one-time" and activated_at:
            activated_date = datetime.fromisoformat(activated_at)
            maintenance_expires = (activated_date + timedelta(days=365)).isoformat()
        else:
            maintenance_expires = expires_at
        
        return jsonify({
            "valid": True,
            "type": license_type,
            "tier": tier,
            "billing_type": billing_type,
            "expires": expires_at,
            "maintenance_expires": maintenance_expires
        })
        
    except Exception as e:
        logging.error(f"❌ Verification error: {e}")
        return jsonify({"valid": False, "error": "Internal error"}), 500
    finally:
        conn.close()

@app.route('/deactivate', methods=['POST'])
def deactivate():
    """Deactivate license"""
    data = request.get_json()
    
    key = data.get('key', '').strip().upper()
    machine_id = data.get('machine_id', '').strip()
    
    if not all([key, machine_id]):
        return jsonify({"success": False, "error": "Missing fields"}), 400
    
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    
    try:
        c.execute("""
            SELECT id FROM activations
            WHERE license_key = ? AND machine_id = ? AND status = 'active'
        """, (key, machine_id))
        
        if not c.fetchone():
            return jsonify({"success": False, "error": "No active activation"}), 404
        
        c.execute("""
            UPDATE activations 
            SET status = 'deactivated'
            WHERE license_key = ? AND machine_id = ?
        """, (key, machine_id))
        
        c.execute("""
            UPDATE licenses 
            SET current_activations = current_activations - 1
            WHERE license_key = ?
        """, (key,))
        
        conn.commit()
        
        backup_to_github()
        
        return jsonify({"success": True, "message": "Deactivated"})
        
    except Exception as e:
        logging.error(f"❌ Deactivation error: {e}")
        return jsonify({"success": False, "error": "Internal error"}), 500
    finally:
        conn.close()

@app.route('/admin/create', methods=['POST'])
def admin_create():
    """Admin: Create license"""
    data = request.get_json()
    
    if data.get('admin_secret') != os.environ.get('UPAGER_ADMIN_SECRET'):
        return jsonify({"success": False, "error": "Unauthorized"}), 401
    
    email = data.get('email', '').strip()
    tier = data.get('tier', 'pro_lifetime')
    max_activations = data.get('max_activations', 1)
    
    if not email:
        return jsonify({"success": False, "error": "Email required"}), 400
    
    key = create_license(email, tier, max_activations)
    
    if key:
        return jsonify({"success": True, "license_key": key, "email": email, "tier": tier})
    else:
        return jsonify({"success": False, "error": "Creation failed"}), 500

@app.route('/admin/backup', methods=['POST'])
def admin_backup():
    """Admin: Manual backup"""
    data = request.get_json()
    
    if data.get('admin_secret') != os.environ.get('UPAGER_ADMIN_SECRET'):
        return jsonify({"success": False, "error": "Unauthorized"}), 401
    
    success = backup_to_github()
    return jsonify({"success": success})

@app.route('/admin/restore', methods=['POST'])
def admin_restore():
    """Admin: Manual restore"""
    data = request.get_json()
    
    if data.get('admin_secret') != os.environ.get('UPAGER_ADMIN_SECRET'):
        return jsonify({"success": False, "error": "Unauthorized"}), 401
    
    data = get_file_from_github()
    success = import_json_to_db(data) if data else False
    
    return jsonify({"success": success})

@app.route('/health')
def health():
    """Health check"""
    github_status = "connected" if GITHUB_TOKEN else "disabled"
    
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM licenses")
    license_count = c.fetchone()[0]
    conn.close()
    
    return jsonify({
        "status": "healthy",
        "github": github_status,
        "licenses": license_count,
        "timestamp": datetime.utcnow().isoformat()
    })

# ============================================
# RUN
# ============================================

if __name__ == '__main__':
    logging.info("=" * 60)
    logging.info("🚀 UPager License Server - GitHub Persistence Mode")
    logging.info("=" * 60)
    
    port = int(os.environ.get('PORT', 5001))
    app.run(host='0.0.0.0', port=port, debug=False)