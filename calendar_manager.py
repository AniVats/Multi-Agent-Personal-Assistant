import os
from datetime import datetime, timedelta, timezone

import google.auth
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from google.adk.agents.llm_agent import Agent

def _get_calendar_service():
    """Build the Google Calendar API service using Service Account Impersonation."""
    from google.auth.transport.requests import Request
    from google.auth import impersonated_credentials

    target_principal = os.environ.get("SERVICE_ACCOUNT_EMAIL")
    if not target_principal:
        raise ValueError("SERVICE_ACCOUNT_EMAIL environment variable is missing.")

    base_scopes = ["https://www.googleapis.com/auth/cloud-platform"]
    creds, _ = google.auth.default(scopes=base_scopes)
    creds.refresh(Request())

    target_scopes = ["https://www.googleapis.com/auth/calendar"]
    impersonated = impersonated_credentials.Credentials(
        source_credentials=creds,
        target_principal=target_principal,
        target_scopes=target_scopes,
    )
    
    return build("calendar", "v3", credentials=impersonated)

def _format_event(event: dict) -> dict:
    """Format a raw Calendar API event into a clean dict for the LLM."""
    start = event.get("start", {})
    end = event.get("end", {})
    return {
        "id": event.get("id"),
        "title": event.get("summary", "(No title)"),
        "start": start.get("dateTime", start.get("date")),
        "end": end.get("dateTime", end.get("date")),
        "location": event.get("location", ""),
        "description": event.get("description", ""),
        "attendees": [
            {"email": a["email"], "status": a.get("responseStatus", "unknown")}
            for a in event.get("attendees", [])
        ],
        "link": event.get("htmlLink", ""),
        "conference_link": (
            event.get("conferenceData", {}).get("entryPoints", [{}])[0].get("uri", "")
            if event.get("conferenceData")
            else ""
        ),
        "status": event.get("status", ""),
    }

def list_events(days_ahead: int = 7) -> dict:
    """List upcoming calendar events."""
    calendar_id = os.environ.get("CALENDAR_ID")
    try:
        service = _get_calendar_service()
        now = datetime.now(timezone.utc).isoformat()
        end = (datetime.now(timezone.utc) + timedelta(days=days_ahead)).isoformat()

        events_result = service.events().list(
            calendarId=calendar_id, timeMin=now, timeMax=end,
            maxResults=50, singleEvents=True, orderBy="startTime"
        ).execute()

        events = events_result.get("items", [])
        if not events:
            return {"status": "success", "count": 0, "events": []}

        return {"status": "success", "count": len(events), "events": [_format_event(e) for e in events]}
    except HttpError as e:
        return {"status": "error", "message": f"Calendar API error: {e}"}

def create_event(title: str, start_time: str, end_time: str, description: str = "", location: str = "", attendees: str = "", add_google_meet: bool = False) -> dict:
    """Create a new calendar event."""
    calendar_id = os.environ.get("CALENDAR_ID")
    try:
        service = _get_calendar_service()
        event_body = {
            "summary": title,
            "start": {"dateTime": start_time},
            "end": {"dateTime": end_time},
        }
        if description: event_body["description"] = description
        if location: event_body["location"] = location
        if attendees:
            email_list = [e.strip() for e in attendees.split(",") if e.strip()]
            event_body["attendees"] = [{"email": e} for e in email_list]

        conference_version = 0
        if add_google_meet:
            event_body["conferenceData"] = {
                "createRequest": {"requestId": f"event-{datetime.now().strftime('%Y%m%d%H%M%S')}", "conferenceSolutionKey": {"type": "hangoutsMeet"}}
            }
            conference_version = 1

        event = service.events().insert(calendarId=calendar_id, body=event_body, conferenceDataVersion=conference_version).execute()
        return {"status": "success", "message": f"Event created ✅", "event": _format_event(event)}
    except HttpError as e:
        return {"status": "error", "message": f"Calendar API error: {e}"}

def update_event(event_id: str, title: str = "", start_time: str = "", end_time: str = "", description: str = "") -> dict:
    """Update an existing calendar event."""
    calendar_id = os.environ.get("CALENDAR_ID")
    try:
        service = _get_calendar_service()
        patch_body = {}
        if title: patch_body["summary"] = title
        if start_time: patch_body["start"] = {"dateTime": start_time}
        if end_time: patch_body["end"] = {"dateTime": end_time}
        if description: patch_body["description"] = description
        if not patch_body: return {"status": "error", "message": "No fields to update."}

        event = service.events().patch(calendarId=calendar_id, eventId=event_id, body=patch_body).execute()
        return {"status": "success", "message": "Event updated ✅", "event": _format_event(event)}
    except HttpError as e:
        return {"status": "error", "message": f"Calendar API error: {e}"}

def delete_event(event_id: str) -> dict:
    """Delete a calendar event by its ID."""
    calendar_id = os.environ.get("CALENDAR_ID")
    try:
        service = _get_calendar_service()
        service.events().delete(calendarId=calendar_id, eventId=event_id).execute()
        return {"status": "success", "message": f"Event '{event_id}' deleted ✅"}
    except HttpError as e:
        return {"status": "error", "message": f"Calendar API error: {e}"}

def quick_add_event(text: str) -> dict:
    """Create an event using natural language (e.g. 'Lunch with Sarah next Monday noon')."""
    calendar_id = os.environ.get("CALENDAR_ID")
    try:
        service = _get_calendar_service()
        event = service.events().quickAdd(calendarId=calendar_id, text=text).execute()
        return {"status": "success", "message": "Event created from text ✅", "event": _format_event(event)}
    except HttpError as e:
        return {"status": "error", "message": f"Calendar API error: {e}"}

calendar_agent = Agent(
    model='gemini-2.5-flash',
    name='calendar_specialist',
    description='Manages the user schedule and calendar events.',
    instruction='''
    You manage the user's Google Calendar.
    - Use list_events to check the schedule.
    - Use quick_add_event for simple, conversational scheduling requests (e.g., "Lunch tomorrow at noon").
    - Use create_event for complex meetings that require attendees, specific durations, or Google Meet links.
    - Use update_event to change details of an existing event.
    - Use delete_event to cancel or remove an event.
    
    CRITICAL: For update_event and delete_event, you must provide the exact `event_id`. 
    If the user does not provide the ID, you MUST call list_events first to find the correct `event_id` before attempting the update or deletion.
    
    Always use the current date/time context provided by the root agent to resolve relative dates like "tomorrow".
    ''',
    tools=[list_events, create_event, update_event, delete_event, quick_add_event],
)