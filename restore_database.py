#!/usr/bin/env python3
"""Restore license database to Render"""

import requests
import json
import os
import sys

SERVER_URL = 'https://upager-license-server.onrender.com'
ADMIN_SECRET = os.getenv('UPAGER_ADMIN_SECRET', 'change-me')

def restore_database(backup_file='license_backup_latest.json'):
    """Upload database backup to Render"""
    
    if not os.path.exists(backup_file):
        print(f"❌ Backup file not found: {backup_file}")
        print("\nAvailable backups:")
        for f in os.listdir('.'):
            if f.startswith('license_backup_') and f.endswith('.json'):
                print(f"  - {f}")
        return False
    
    try:
        print(f"\n🔄 Restoring database from: {backup_file}")
        
        with open(backup_file, 'r') as f:
            backup_data = json.load(f)
        
        counts = backup_data.get('counts', {})
        print(f"   Licenses:    {counts.get('licenses', 0)}")
        print(f"   Activations: {counts.get('activations', 0)}")
        
        confirm = input("\n⚠️  This will REPLACE all data on the server. Continue? (yes/no): ")
        if confirm.lower() != 'yes':
            print("❌ Restore cancelled")
            return False
        
        print("\n📤 Uploading to Render...")
        
        response = requests.post(
            f'{SERVER_URL}/admin/restore',
            json={
                'admin_secret': ADMIN_SECRET,
                'backup': backup_data
            },
            timeout=30000
        )
        
        if response.status_code == 200:
            data = response.json()
            
            if data.get('success'):
                restored = data.get('counts', {})
                print("\n✅ Restore successful!")
                print("=" * 60)
                print(f"Licenses restored:    {restored.get('licenses', 0)}")
                print(f"Activations restored: {restored.get('activations', 0)}")
                print("=" * 60)
                print()
                return True
            else:
                print(f"❌ Restore failed: {data.get('error')}")
                return False
        else:
            print(f"❌ HTTP Error {response.status_code}")
            print(f"Response: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        return False

if __name__ == "__main__":
    if len(sys.argv) > 1:
        backup_file = sys.argv[1]
    else:
        backup_file = 'license_backup_latest.json'
    
    restore_database(backup_file)