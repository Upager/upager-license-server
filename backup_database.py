#!/usr/bin/env python3
"""Backup license database from Render"""

import requests
import json
import os
from datetime import datetime

SERVER_URL = 'https://upager-license-server.onrender.com'
ADMIN_SECRET = os.getenv('UPAGER_ADMIN_SECRET', 'change-me')

def backup_database():
    """Download database backup"""
    try:
        print("\n🔄 Downloading database backup from Render...")
        
        response = requests.get(
            f'{SERVER_URL}/admin/backup',
            params={'secret': ADMIN_SECRET},
            timeout=30000
        )
        
        if response.status_code == 200:
            data = response.json()
            
            if data.get('success'):
                backup = data['backup']
                counts = backup['counts']
                
                # Save to file with timestamp
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                filename = f'license_backup_{timestamp}.json'
                
                with open(filename, 'w') as f:
                    json.dump(backup, f, indent=2)
                
                print(f"\n✅ Backup successful!")
                print("=" * 60)
                print(f"File:        {filename}")
                print(f"Licenses:    {counts['licenses']}")
                print(f"Activations: {counts['activations']}")
                print(f"Date:        {backup['backup_date']}")
                print("=" * 60)
                print(f"\n💾 Backup saved to: {filename}\n")
                
                # Also save as "latest" for easy restore
                with open('license_backup_latest.json', 'w') as f:
                    json.dump(backup, f, indent=2)
                print("📝 Also saved as: license_backup_latest.json\n")
                
                return True
            else:
                print(f"❌ Backup failed: {data.get('error')}")
                return False
        else:
            print(f"❌ HTTP Error {response.status_code}")
            print(f"Response: {response.text}")
            return False
            
    except requests.exceptions.ConnectionError:
        print(f"❌ Cannot connect to {SERVER_URL}")
        print("Make sure the server is running!")
        return False
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        return False

if __name__ == "__main__":
    backup_database()