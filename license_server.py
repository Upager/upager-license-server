#!/usr/bin/env python3
"""
UPager License Server - Hybrid Model (Lifetime + Annual)
Supports: free, pro_lifetime, pro_annual, enterprise_lifetime, enterprise_annual
"""

from flask import Flask, request, jsonify
from flask_cors import CORS
import sqlite3
import hashlib
import secrets
import logging
from datetime import datetime, timedelta
from pathlib import Path
import os

app = Flask(__name__)
CORS(app)



# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('license_server.log'),
        logging.StreamHandler()
    ]
)

# Database setup
DB_FILE = Path(__file__).parent / 'licenses.db'

def init_db():
    """Initialize database with hybrid license support"""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    
    # Create licenses table
    c.execute('''
        CREATE TABLE IF NOT EXISTS licenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            license_key TEXT UNIQUE NOT NULL,
            email TEXT NOT NULL,
            type TEXT NOT NULL,
            tier TEXT NOT NULL,
            billing_type TEXT NOT NULL,
            status TEXT NOT NULL,
            created_at TEXT NOT NULL,
            activated_at TEXT,
            expires_at TEXT,
            maintenance_expires_at TEXT,
            max_activations INTEGER DEFAULT 1,
            current_activations INTEGER DEFAULT 0
        )
    ''')
    
    # Create activations table
    c.execute('''
        CREATE TABLE IF NOT EXISTS activations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            license_key TEXT NOT NULL,
            machine_id TEXT NOT NULL,
            ip_address TEXT,
            activated_at TEXT NOT NULL,
            last_verified TEXT,
            status TEXT NOT NULL,
            FOREIGN KEY (license_key) REFERENCES licenses(license_key)
        )
    ''')
    
    # Create verification log
    c.execute('''
        CREATE TABLE IF NOT EXISTS verification_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            license_key TEXT NOT NULL,
            machine_id TEXT NOT NULL,
            ip_address TEXT,
            timestamp TEXT NOT NULL,
            result TEXT NOT NULL,
            message TEXT
        )
    ''')
    
    conn.commit()
    conn.close()
    logging.info("Database initialized")

init_db()

def generate_license_key(tier='pro_lifetime'):
    """Generate a license key in format: UPAGER-XXXX-XXXX-XXXX-XXXX"""
    # Generate 16 random hex characters
    random_hex = secrets.token_hex(8).upper()
    
    # Split into 4 groups of 4
    parts = [random_hex[i:i+4] for i in range(0, 16, 4)]
    
    # Create key
    key = f"UPAGER-{'-'.join(parts)}"
    
    return key

def create_license(email, tier, max_activations=1):
    """Create a new license"""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    
    key = generate_license_key(tier)
    
    # Determine type and billing_type from tier
    if tier.startswith('pro'):
        license_type = 'pro'
    elif tier.startswith('enterprise'):
        license_type = 'enterprise'
    else:
        license_type = 'free'
    
    billing_type = 'one-time' if 'lifetime' in tier else 'annual'
    
    try:
        c.execute('''
            INSERT INTO licenses 
            (license_key, email, type, tier, billing_type, status, created_at, max_activations)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (key, email, license_type, tier, billing_type, 'active', 
              datetime.utcnow().isoformat(), max_activations))
        
        conn.commit()
        logging.info(f"Created {tier} license: {key} for {email}")
        return key
    except sqlite3.IntegrityError:
        logging.error(f"Failed to create license - key collision")
        return None
    finally:
        conn.close()

@app.route('/activate', methods=['POST'])
def activate():
    """Activate a license on a machine"""
    data = request.get_json()
    
    key = data.get('key', '').strip()
    email = data.get('email', '').strip()
    machine_id = data.get('machine_id', '').strip()
    ip = data.get('ip', request.remote_addr)
    
    if not all([key, email, machine_id]):
        return jsonify({
            'success': False,
            'error': 'Missing required fields'
        }), 400
    
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    
    try:
        # Get license info
        c.execute('''
            SELECT type, tier, billing_type, status, email, 
                   max_activations, current_activations, expires_at
            FROM licenses 
            WHERE UPPER(license_key) = UPPER(?)
        ''', (key,))
        
        license_row = c.fetchone()
        
        if not license_row:
            logging.warning(f"Activation failed: Invalid key {key}")
            return jsonify({
                'success': False,
                'error': 'Invalid license key'
            }), 404
        
        (license_type, tier, billing_type, status, license_email, 
         max_activations, current_activations, expires_at) = license_row
        
        # Check status
        if status != 'active':
            return jsonify({
                'success': False,
                'error': f'License is {status}'
            }), 403
        
        # Check email match
        if email.lower() != license_email.lower():
            return jsonify({
                'success': False,
                'error': 'Email does not match license'
            }), 403
        
        # Check if already activated on this machine
        c.execute('''
            SELECT status FROM activations
            WHERE license_key = ? AND machine_id = ?
        ''', (key, machine_id))
        
        existing = c.fetchone()
        
        if existing:
            # Already activated - update last verified
            c.execute('''
                UPDATE activations
                SET last_verified = ?, ip_address = ?
                WHERE license_key = ? AND machine_id = ?
            ''', (datetime.utcnow().isoformat(), ip, key, machine_id))
            
            logging.info(f"Re-activation: {key} on {machine_id}")
        else:
            # New activation - check limit
            if current_activations >= max_activations:
                return jsonify({
                    'success': False,
                    'error': f'Maximum activations ({max_activations}) reached'
                }), 403
            
            # Create new activation
            c.execute('''
                INSERT INTO activations
                (license_key, machine_id, ip_address, activated_at, last_verified, status)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (key, machine_id, ip, 
                  datetime.utcnow().isoformat(), 
                  datetime.utcnow().isoformat(), 
                  'active'))
            
            # Increment activation count
            c.execute('''
                UPDATE licenses
                SET current_activations = current_activations + 1,
                    activated_at = COALESCE(activated_at, ?)
                WHERE license_key = ?
            ''', (datetime.utcnow().isoformat(), key))
            
            logging.info(f"New activation: {key} on {machine_id}")
        
        # Calculate expiry dates
        now = datetime.utcnow()
        
        if billing_type == 'one-time':
            # Lifetime licenses don't expire
            license_expires = None
            # Maintenance is 1 year from activation
            maintenance_expires = (now + timedelta(days=365)).isoformat()
        else:
            # Annual licenses expire in 1 year
            license_expires = (now + timedelta(days=365)).isoformat()
            maintenance_expires = license_expires
        
        # Update license expiry if not set
        if not expires_at and license_expires:
            c.execute('''
                UPDATE licenses
                SET expires_at = ?
                WHERE license_key = ?
            ''', (license_expires, key))
        
        conn.commit()
        
        return jsonify({
            'success': True,
            'message': 'License activated successfully',
            'license': {
                'type': license_type,
                'tier': tier,
                'billing_type': billing_type,
                'expires': license_expires,
                'maintenance_expires': maintenance_expires
            }
        })
        
    except Exception as e:
        logging.error(f"Activation error: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Internal server error'
        }), 500
    finally:
        conn.close()

@app.route('/verify', methods=['POST'])
def verify():
    """Verify a license"""
    data = request.get_json()
    
    key = data.get('key', '').strip()
    machine_id = data.get('machine_id', '').strip()
    
    if not all([key, machine_id]):
        return jsonify({
            'valid': False,
            'error': 'Missing required fields'
        }), 400
    
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    
    try:
        # Get license and activation info
        c.execute('''
            SELECT l.type, l.tier, l.billing_type, l.status, l.expires_at,
                   a.status as activation_status, a.activated_at
            FROM licenses l
            LEFT JOIN activations a ON UPPER(l.license_key) = UPPER(a.license_key) 
                AND a.machine_id = ?
            WHERE UPPER(l.license_key) = UPPER(?)
        ''', (machine_id, key))
        
        row = c.fetchone()
        
        if not row:
            logging.warning(f"Verification failed: Invalid key {key}")
            c.execute('''
                INSERT INTO verification_log
                (license_key, machine_id, timestamp, result, message)
                VALUES (?, ?, ?, ?, ?)
            ''', (key, machine_id, datetime.utcnow().isoformat(), 
                  'failed', 'Invalid key'))
            conn.commit()
            
            return jsonify({
                'valid': False,
                'error': 'Invalid license key'
            })
        
        (license_type, tier, billing_type, license_status, 
         expires_at, activation_status, activated_at) = row
        
        # Check license status
        if license_status != 'active':
            return jsonify({
                'valid': False,
                'error': f'License is {license_status}'
            })
        
        # Check if activated on this machine
        if not activation_status:
            return jsonify({
                'valid': False,
                'error': 'License not activated on this machine'
            })
        
        # Check expiry for annual licenses
        if billing_type == 'annual' and expires_at:
            expiry_date = datetime.fromisoformat(expires_at)
            if datetime.utcnow() > expiry_date:
                return jsonify({
                    'valid': False,
                    'error': 'License has expired'
                })
        
        # Update last verified
        c.execute('''
            UPDATE activations
            SET last_verified = ?
            WHERE license_key = ? AND machine_id = ?
        ''', (datetime.utcnow().isoformat(), key, machine_id))
        
        # Log verification
        c.execute('''
            INSERT INTO verification_log
            (license_key, machine_id, timestamp, result, message)
            VALUES (?, ?, ?, ?, ?)
        ''', (key, machine_id, datetime.utcnow().isoformat(), 
              'success', f'Verified {tier}'))
        
        conn.commit()
        
        # Calculate maintenance expiry
        if billing_type == 'one-time' and activated_at:
            activated_date = datetime.fromisoformat(activated_at)
            maintenance_expires = (activated_date + timedelta(days=365)).isoformat()
        else:
            maintenance_expires = expires_at
        
        return jsonify({
            'valid': True,
            'type': license_type,
            'tier': tier,
            'billing_type': billing_type,
            'expires': expires_at,
            'maintenance_expires': maintenance_expires
        })
        
    except Exception as e:
        logging.error(f"Verification error: {str(e)}")
        return jsonify({
            'valid': False,
            'error': 'Internal server error'
        }), 500
    finally:
        conn.close()

@app.route('/deactivate', methods=['POST'])
def deactivate():
    """Deactivate a license from a machine"""
    data = request.get_json()
    
    key = data.get('key', '').strip()
    machine_id = data.get('machine_id', '').strip()
    
    if not all([key, machine_id]):
        return jsonify({
            'success': False,
            'error': 'Missing required fields'
        }), 400
    
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    
    try:
        # Check if activation exists
        c.execute('''
            SELECT id FROM activations
            WHERE UPPER(license_key) = UPPER(?) AND machine_id = ? AND status = 'active'
        ''', (key, machine_id))
        
        if not c.fetchone():
            return jsonify({
                'success': False,
                'error': 'No active activation found'
            }), 404
        
        # Deactivate
        c.execute('''
            UPDATE activations
            SET status = 'deactivated'
            WHERE UPPER(license_key) = UPPER(?) AND machine_id = ?
        ''', (key, machine_id))
        
        # Decrement activation count
        c.execute('''
            UPDATE licenses
            SET current_activations = current_activations - 1
            WHERE license_key = ?
        ''', (key,))
        
        conn.commit()
        logging.info(f"Deactivated: {key} from {machine_id}")
        
        return jsonify({
            'success': True,
            'message': 'License deactivated successfully'
        })
        
    except Exception as e:
        logging.error(f"Deactivation error: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Internal server error'
        }), 500
    finally:
        conn.close()

@app.route('/admin/create', methods=['POST'])
def admin_create():
    """Admin endpoint to create licenses"""
    data = request.get_json()

    # Check admin secret
    if data.get('admin_secret') != os.environ.get('UPAGER_ADMIN_SECRET', 'change-me'):
        return jsonify({'success': False, 'error': 'Unauthorized'}), 401
        
    email = data.get('email', '').strip()
    tier = data.get('tier', 'pro_lifetime')
    max_activations = data.get('max_activations', 1)
    
    if not email:
        return jsonify({
            'success': False,
            'error': 'Email required'
        }), 400
    
    key = create_license(email, tier, max_activations)
    
    if key:
        return jsonify({
            'success': True,
            'license_key': key,
            'email': email,
            'tier': tier
        })
    else:
        return jsonify({
            'success': False,
            'error': 'Failed to create license'
        }), 500

@app.route('/admin/stats', methods=['GET'])
def admin_stats():
    """Get license statistics"""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    
    try:
        # Total licenses by tier
        c.execute('''
            SELECT tier, billing_type, COUNT(*) as count
            FROM licenses
            WHERE status = 'active'
            GROUP BY tier, billing_type
        ''')
        
        by_tier = [{'tier': row[0], 'billing': row[1], 'count': row[2]} 
                   for row in c.fetchall()]
        
        # Total activations
        c.execute('SELECT COUNT(*) FROM activations WHERE status = "active"')
        total_activations = c.fetchone()[0]
        
        # Recent verifications
        c.execute('''
            SELECT COUNT(*) FROM verification_log
            WHERE timestamp > datetime('now', '-7 days')
        ''')
        recent_verifications = c.fetchone()[0]
        
        return jsonify({
            'by_tier': by_tier,
            'total_activations': total_activations,
            'recent_verifications': recent_verifications
        })
        
    finally:
        conn.close()

@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.utcnow().isoformat()
    })

if __name__ == '__main__':
    
    
    # Create sample licenses for testing
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('SELECT COUNT(*) FROM licenses')
    
    if c.fetchone()[0] == 0:
        logging.info("Creating sample licenses...")
        create_license('free@example.com', 'free')
        create_license('pro_lifetime@example.com', 'pro_lifetime')
        create_license('pro_annual@example.com', 'pro_annual')
        create_license('enterprise@example.com', 'enterprise_lifetime')
    
    conn.close()
    
    logging.info("Starting UPager License Server on http://0.0.0.0:5001")
    port = int(os.environ.get('PORT', 5001))
    app.run(host='0.0.0.0', port=port, debug=False)