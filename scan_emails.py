"""Script to scan emails from August 2025 and auto-process them."""
import requests
import sys

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

BASE_URL = 'http://localhost:5000'

print("Scanning emails from August 2025 with expanded keywords...")

# Scan emails from August 2025 (about 170 days back from Jan 2026)
# Using max_results=1000 to catch more emails
response = requests.post(
    f'{BASE_URL}/api/emails/scan', 
    json={'days_back': 180, 'max_results': 1000},
    headers={'Content-Type': 'application/json'}
)

if response.status_code == 200:
    data = response.json()
    print(f"Scanned: {data.get('scanned', 0)} emails")
    print(f"New emails found: {data.get('new_emails', 0)}")
else:
    print(f"Scan failed: {response.status_code} - {response.text[:200]}")
    sys.exit(1)

print("\nAuto-processing emails into applications...")

# Auto-process the emails with lower confidence threshold
response = requests.post(
    f'{BASE_URL}/api/emails/auto-process',
    json={'min_confidence': 0.3},
    headers={'Content-Type': 'application/json'}
)

if response.status_code == 200:
    data = response.json()
    print(f"Processed: {data.get('processed', 0)} emails")
    print(f"Applications created: {data.get('created', 0)}")
    
    if data.get('applications'):
        print("\nCreated applications:")
        for app in data['applications'][:15]:
            status = app.get('status', 'unknown')
            rejected_at = app.get('rejected_at_stage', '')
            stage_info = f" ({rejected_at})" if rejected_at else ""
            print(f"  - {app.get('company_name', 'Unknown')} | {app.get('position_title', 'Unknown')} | Status: {status}{stage_info}")
else:
    print(f"Auto-process failed: {response.status_code} - {response.text[:200]}")

print("\nDone! Check your dashboard at http://localhost:5000")
