#!/usr/bin/env python3
"""List all licenses from Render server"""

import requests
import os

SERVER_URL = 'https://upager-license-server.onrender.com'
ADMIN_SECRET = os.getenv('UPAGER_ADMIN_SECRET', 'change-me')

def list_licenses():
    """List all licenses"""
    try:
        print("\n🔍 Fetching licenses from Render...")
        
        response = requests.get(
            f'{SERVER_URL}/admin/licenses',
            params={'secret': ADMIN_SECRET},
            timeout=10000
        )
        
        if response.status_code == 200:
            data = response.json()
            
            if data.get('success'):
                licenses = data.get('licenses', [])
                
                if not licenses:
                    print("\n📭 No licenses found\n")
                    return
                
                print("\n📋 All Licenses:")
                print("=" * 130)
                print(f"{'License Key':<30} {'Email':<30} {'Tier':<20} {'Status':<10} {'Acts':<10}")
                print("-" * 130)
                
                for lic in licenses:
                    key = lic['license_key']
                    email = lic['email']
                    tier = lic['tier']
                    status = lic['status']
                    acts = f"{lic['current_activations']}/{lic['max_activations']}"
                    
                    print(f"{key:<30} {email:<30} {tier:<20} {status:<10} {acts:<10}")
                
                print("=" * 130)
                print(f"Total: {len(licenses)} licenses\n")
            else:
                print(f"❌ Error: {data.get('error')}")
        else:
            print(f"❌ HTTP Error {response.status_code}")
            
    except requests.exceptions.ConnectionError:
        print(f"❌ Cannot connect to {SERVER_URL}")
    except Exception as e:
        print(f"❌ Error: {str(e)}")

if __name__ == "__main__":
    list_licenses()