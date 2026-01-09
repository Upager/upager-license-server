#!/usr/bin/env python3
"""
UPager License Creator - Works with GitHub-backed server
"""

import requests
import sys
import os

# Configuration
ADMIN_SECRET = os.getenv('UPAGER_ADMIN_SECRET', 'SAV#311716872386192019')
SERVER_URL = os.getenv('SERVER_URL', 'https://upager-license-server.onrender.com')

def create_license(email, tier="pro_lifetime", max_activations=1):
    """Create a new license with admin authentication"""
    try:
        response = requests.post(f'{SERVER_URL}/admin/create', 
            headers={'Content-Type': 'application/json'},
            json={
                'admin_secret': ADMIN_SECRET,
                'email': email,
                'tier': tier,
                'max_activations': max_activations
            },
            timeout=30
        )
        
        if response.status_code == 200:
            data = response.json()
            if data.get('success'):
                license_key = data.get('license_key')
                
                print("\n✅ License Created Successfully!")
                print("=" * 60)
                print(f"License Key:      {license_key}")
                print(f"Email:            {data.get('email')}")
                print(f"Tier:             {data.get('tier', tier)}")
                print(f"Max Activations:  {max_activations}")
                print("=" * 60)
                print(f"\n💾 Save this license key: {license_key}")
                print(f"🔗 Backed up to GitHub automatically\n")
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
        return None
    except requests.exceptions.Timeout:
        print(f"❌ Error: Request timeout (server may be waking up on Render)")
        print("Try again in 30 seconds...")
        return None
    except Exception as e:
        print(f"❌ Unexpected error: {str(e)}")
        return None

def check_server_health():
    """Check if server is healthy"""
    try:
        response = requests.get(f'{SERVER_URL}/health', timeout=10)
        if response.status_code == 200:
            data = response.json()
            print("\n✅ Server Status:")
            print("=" * 60)
            print(f"Status:           {data.get('status')}")
            print(f"GitHub:           {data.get('github')}")
            print(f"Licenses:         {data.get('licenses')}")
            print(f"Timestamp:        {data.get('timestamp')}")
            print("=" * 60 + "\n")
            return True
        return False
    except Exception as e:
        print(f"❌ Server health check failed: {e}")
        return False

def manual_backup():
    """Trigger manual backup to GitHub"""
    try:
        response = requests.post(f'{SERVER_URL}/admin/backup',
            headers={'Content-Type': 'application/json'},
            json={'admin_secret': ADMIN_SECRET},
            timeout=30
        )
        
        if response.status_code == 200:
            data = response.json()
            if data.get('success'):
                print("\n✅ Manual backup to GitHub completed!")
            else:
                print(f"❌ Backup failed: {data.get('message')}")
        else:
            print(f"❌ HTTP Error {response.status_code}")
    except Exception as e:
        print(f"❌ Backup error: {e}")

def manual_restore():
    """Trigger manual restore from GitHub"""
    try:
        response = requests.post(f'{SERVER_URL}/admin/restore',
            headers={'Content-Type': 'application/json'},
            json={'admin_secret': ADMIN_SECRET},
            timeout=30
        )
        
        if response.status_code == 200:
            data = response.json()
            if data.get('success'):
                print("\n✅ Manual restore from GitHub completed!")
            else:
                print(f"❌ Restore failed: {data.get('message')}")
        else:
            print(f"❌ HTTP Error {response.status_code}")
    except Exception as e:
        print(f"❌ Restore error: {e}")

def show_usage():
    """Show usage instructions"""
    print("\n📖 UPager License Creator")
    print("=" * 60)
    print("\nUsage:")
    print("  python create_license.py <email> [tier] [max_activations]")
    print("  python create_license.py health            # Check server status")
    print("  python create_license.py backup            # Manual GitHub backup")
    print("  python create_license.py restore           # Manual GitHub restore")
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
    print("\nEnvironment Variables:")
    print(f"  SERVER_URL:          {SERVER_URL}")
    print(f"  UPAGER_ADMIN_SECRET: {'Set' if ADMIN_SECRET else 'Not set'}")
    print()

if __name__ == "__main__":
    # Check arguments
    if len(sys.argv) < 2 or sys.argv[1] in ['-h', '--help', 'help']:
        show_usage()
        sys.exit(0)
    
    # Special commands
    if sys.argv[1] == 'health':
        check_server_health()
        sys.exit(0)
    
    if sys.argv[1] == 'backup':
        manual_backup()
        sys.exit(0)
    
    if sys.argv[1] == 'restore':
        manual_restore()
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