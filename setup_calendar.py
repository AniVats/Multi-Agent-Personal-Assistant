import os
import google.auth
from googleapiclient.discovery import build
from google.auth.transport.requests import Request
from google.auth import impersonated_credentials
from dotenv import load_dotenv

load_dotenv('av_pa/.env')
SA_EMAIL = os.environ.get("SERVICE_ACCOUNT_EMAIL")

def setup_sa_calendar():
    if not SA_EMAIL:
        raise ValueError("SERVICE_ACCOUNT_EMAIL is missing. Please ensure it is set correctly in your executive_assistant/.env file.")

    print(f"Authenticating to impersonate {SA_EMAIL}...")
    
    # 1. Base credentials
    creds, _ = google.auth.default(scopes=["https://www.googleapis.com/auth/cloud-platform"])
    creds.refresh(Request())

    # 2. Impersonate the Service Account
    impersonated = impersonated_credentials.Credentials(
        source_credentials=creds,
        target_principal=SA_EMAIL,
        target_scopes=["https://www.googleapis.com/auth/calendar"],
    )
    service = build("calendar", "v3", credentials=impersonated)

    # 3. Create the calendar
    print("Creating independent Service Account calendar...")
    calendar = service.calendars().insert(body={
        "summary": "AI Assistant (SA Owned)",
        "description": "An independent calendar managed purely by the AI."
    }).execute()
    
    calendar_id = calendar['id']
    
    # 4. Save the ID
    with open("av_pa/.env", "a") as f:
        f.write(f"\nCALENDAR_ID={calendar_id}\n")
    print(f"Setup complete! CALENDAR_ID {calendar_id} added to .env")

if __name__ == "__main__":
    setup_sa_calendar()