import json
import re
from pathlib import Path

from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

# Read-only permission
SCOPES = ["https://www.googleapis.com/auth/spreadsheets.readonly"]

PROJECT_ROOT = Path(__file__).resolve().parent
CREDENTIALS_FILE = PROJECT_ROOT / "credentials.json"
TOKEN_FILE = PROJECT_ROOT / "token.json"


def authenticate():
    creds = None

    if TOKEN_FILE.exists():
        creds = Credentials.from_authorized_user_file(
            str(TOKEN_FILE), SCOPES
        )

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                str(CREDENTIALS_FILE), SCOPES
            )
            creds = flow.run_local_server(port=0)

        TOKEN_FILE.write_text(creds.to_json(), encoding="utf-8")

    return creds


def main():
    if not CREDENTIALS_FILE.exists():
        raise FileNotFoundError("credentials.json not found in project root.")

    url = input("Paste your Google Sheets URL: ").strip()
    match = re.search(r"/spreadsheets/d/([a-zA-Z0-9-_]+)", url)

    if not match:
        raise ValueError("That doesn't look like a valid Google Sheets URL.")

    spreadsheet_id = match.group(1)

    print("\nConnecting to Google Sheets...")
    service = build("sheets", "v4", credentials=authenticate())

    spreadsheet = service.spreadsheets().get(
        spreadsheetId=spreadsheet_id,
        fields="properties(title),sheets(properties(title))"
    ).execute()

    result = {
        "spreadsheet_title": spreadsheet["properties"]["title"],
        "sheets": []
    }

    for sheet in spreadsheet.get("sheets", []):
        title = sheet["properties"]["title"]
        safe_title = title.replace("'", "''")
        sheet_range = f"'{safe_title}'"

        values = service.spreadsheets().values().get(
            spreadsheetId=spreadsheet_id,
            range=sheet_range,
            valueRenderOption="FORMATTED_VALUE"
        ).execute()

        formulas = service.spreadsheets().values().get(
            spreadsheetId=spreadsheet_id,
            range=sheet_range,
            valueRenderOption="FORMULA"
        ).execute()

        result["sheets"].append({
            "sheet_name": title,
            "values": values.get("values", []),
            "formulas": formulas.get("values", [])
        })

        print(f"Read sheet: {title}")

    output_file = PROJECT_ROOT / "data" / "google_sheets_test.json"
    output_file.parent.mkdir(parents=True, exist_ok=True)

    output_file.write_text(
        json.dumps(result, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )

    print("\nGoogle Sheets connection successful!")
    print(f"Spreadsheet: {result['spreadsheet_title']}")
    print(f"Sheets read: {len(result['sheets'])}")
    print(f"Saved data to: {output_file}")


if __name__ == "__main__":
    main()