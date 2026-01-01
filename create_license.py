#!/usr/bin/env python3
"""
UPager License Creator - Works with admin_secret authentication
"""

import requests
import sys
import os

# Admin secret from environment variable or hardcoded
ADMIN_SECRET = os.getenv('UPAGER_ADMIN_SECRET', 'SAV#311716872386192019')
SERVER_URL = 'http://localhost:5001'

def create_license(email, tier="pro_lifetime", max_activations=1):
    """Create a new license with admin authentication"""
    try:
        response = requests.post(f'{SERVER_URL}/admin/create', 
            headers={'Content-Type': 'application/json'},
            json={
                'admin_secret': ADMIN_SECRET,  # Required for authentication
                'email': email,
                'tier': tier,
                'max_activations': max_activations
            }
        )
        
        if response.status_code == 200:
            data = response.json()
            if data.get('success'):
                # Handle both response formats
                license_key = data.get('license_key') or data.get('key')
                
                print("\n✅ License Created Successfully!")
                print("=" * 60)
                print(f"License Key:      {license_key}")
                print(f"Email:            {data.get('email')}")
                print(f"Tier:             {data.get('tier', tier)}")
                print(f"Type:             {data.get('type', 'N/A')}")
                print(f"Max Activations:  {data.get('max_activations', max_activations)}")
                if data.get('expires'):
                    print(f"Expires:          {data.get('expires')}")
                print("=" * 60)
                print(f"\n💾 Save this license key: {license_key}\n")
                return data
            else:
                print(f"❌ Error: {data.get('error')}")
                return None
        else:
            print(f"❌ HTTP Error {response.status_code}")
            print(f"Response: {response.text}")
            return None
            
    except requests.exceptions.ConnectionError:
        print(f"❌ Error: Cannot connect to server at {SERVER_URL}")
        print("Make sure the license server is running!")
        print("\nStart it with: python license_server.py")
        return None
    except Exception as e:
        print(f"❌ Unexpected error: {str(e)}")
        return None

def list_licenses():
    """List all licenses from the database"""
    try:
        import sqlite3
        from pathlib import Path
        
        db_file = Path(__file__).parent / 'licenses.db'
        if not db_file.exists():
            print("❌ Database file not found!")
            return
        
        conn = sqlite3.connect(db_file)
        c = conn.cursor()
        
        c.execute('''
            SELECT license_key, email, tier, status, created_at, 
                   current_activations, max_activations
            FROM licenses
            ORDER BY created_at DESC
        ''')
        
        rows = c.fetchall()
        
        if not rows:
            print("\n📝 No licenses found in database")
            return
        
        print("\n📋 All Licenses:")
        print("=" * 100)
        print(f"{'License Key':<30} {'Email':<25} {'Tier':<20} {'Status':<10} {'Acts':<8}")
        print("-" * 100)
        
        for row in rows:
            key, email, tier, status, created, current_acts, max_acts = row
            acts = f"{current_acts}/{max_acts}"
            print(f"{key:<30} {email:<25} {tier:<20} {status:<10} {acts:<8}")
        
        print("=" * 100)
        print(f"Total licenses: {len(rows)}\n")
        
        conn.close()
        
    except Exception as e:
        print(f"❌ Error listing licenses: {str(e)}")

def show_usage():
    """Show usage instructions"""
    print("\n📖 UPager License Creator")
    print("=" * 60)
    print("\nUsage:")
    print("  python create_license.py <email> [tier] [max_activations]")
    print("  python create_license.py list              # List all licenses")
    print("\nExamples:")
    print("  python create_license.py customer@example.com")
    print("  python create_license.py customer@example.com pro_annual")
    print("  python create_license.py business@example.com enterprise_lifetime 5")
    print("\nAvailable tiers:")
    print("  • free                    - Free tier")
    print("  • pro_lifetime (default)  - Pro with lifetime license")
    print("  • pro_annual              - Pro with annual subscription")
    print("  • enterprise_lifetime     - Enterprise with lifetime license")
    print("  • enterprise_annual       - Enterprise with annual subscription")
    print()

if __name__ == "__main__":
    # Check arguments
    if len(sys.argv) < 2 or sys.argv[1] in ['-h', '--help', 'help']:
        show_usage()
        sys.exit(0)
    
    # List licenses command
    if sys.argv[1] == 'list':
        list_licenses()
        sys.exit(0)
    
    # Parse arguments
    email = sys.argv[1]
    tier = sys.argv[2] if len(sys.argv) > 2 else "pro_lifetime"
    max_activations = int(sys.argv[3]) if len(sys.argv) > 3 else 1
    
    # Validate email
    if '@' not in email:
        print("❌ Error: Invalid email address")
        sys.exit(1)
    
    # Create license
    print(f"\n🔄 Creating {tier} license for {email}...")
    result = create_license(email, tier, max_activations)
    
    if result:
        sys.exit(0)
    else:
        sys.exit(1)