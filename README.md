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