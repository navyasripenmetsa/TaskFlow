from backend.task_engine.google_sheets_adapter import GoogleSheetsAdapter
# Authenticate and connect to Google Sheets
adapter = GoogleSheetsAdapter()

# Read the spreadsheet URL
url = input("Paste your Google Sheets URL: ").strip()

print("\nReading spreadsheet...")
result = adapter.extract(url)

if result is None:
    print("Could not extract a spreadsheet ID from that URL.")
else:
    print("\nGoogle Sheets adapter working!")
    print("Spreadsheet:", result["spreadsheet_title"])
    print("Sheets found:", len(result["sheets"]))

    for sheet in result["sheets"]:
        print(
            f"- {sheet['sheet_name']}: "
            f"{len(sheet['values'])} rows of data"
        )
