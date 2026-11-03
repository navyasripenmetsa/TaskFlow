import re
from typing import Any, Dict, Optional
from .google_auth import authenticate

from googleapiclient.discovery import build


class GoogleSheetsAdapter:
    """Read spreadsheet data using existing Google OAuth credentials."""

    def __init__(self, credentials=None):
        if credentials is None:
            credentials = authenticate()
        self.service = build(
            "sheets",
            "v4",
            credentials=credentials
        )

    @staticmethod
    def extract_spreadsheet_id(url: str) -> Optional[str]:
        match = re.search(
            r"/spreadsheets/d/([a-zA-Z0-9-_]+)",
            url
        )
        return match.group(1) if match else None

    def extract(self, spreadsheet_url: str) -> Optional[Dict[str, Any]]:
        spreadsheet_id = self.extract_spreadsheet_id(
            spreadsheet_url
        )

        if not spreadsheet_id:
            return None

        spreadsheet = self.service.spreadsheets().get(
            spreadsheetId=spreadsheet_id,
            fields="properties(title),sheets(properties(title))"
        ).execute()

        result = {
            "spreadsheet_id": spreadsheet_id,
            "spreadsheet_title": spreadsheet["properties"]["title"],
            "sheets": []
        }

        for sheet in spreadsheet.get("sheets", []):
            title = sheet["properties"]["title"]
            safe_title = title.replace("'", "''")
            sheet_range = f"'{safe_title}'"

            values = self.service.spreadsheets().values().get(
                spreadsheetId=spreadsheet_id,
                range=sheet_range,
                valueRenderOption="FORMATTED_VALUE"
            ).execute()

            formulas = self.service.spreadsheets().values().get(
                spreadsheetId=spreadsheet_id,
                range=sheet_range,
                valueRenderOption="FORMULA"
            ).execute()

            result["sheets"].append({
                "sheet_name": title,
                "values": values.get("values", []),
                "formulas": formulas.get("values", [])
            })

        return result
