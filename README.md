# TaskFlow

TaskFlow is a context-aware, multi-device task handoff system. It captures the browser tabs you have open, works out which tabs belong together as tasks and broader activities, decides the smallest amount of state needed to reopen each tab elsewhere, and delivers the result to another desktop or to an Android phone.

This project was built as a Mobile and Pervasive Computing course project.

## Table of Contents

1. [Overview](#overview)
2. [Features](#features)
3. [How It Works](#how-it-works)
4. [Project Structure](#project-structure)
5. [Prerequisites](#prerequisites)
6. [Installation](#installation)
7. [Configuration and API Keys](#configuration-and-api-keys)
8. [Running TaskFlow](#running-taskflow)
9. [Input Data Format](#input-data-format)
10. [API Reference](#api-reference)
11. [Testing](#testing)
12. [Troubleshooting](#troubleshooting)
13. [Security and Privacy Notes](#security-and-privacy-notes)
14. [License](#license)

## Overview

TaskFlow has four cooperating parts:

| Component | Location | Role |
|---|---|---|
| Chrome extension | `chrome_extension/` | Captures open tabs (title, URL, visible text, scroll position, form values) and provides the user interface for processing and sending activities. |
| Task and cloud API | `backend/cloud_handoff_server.py` | FastAPI service that runs task and activity discovery on captured tabs, manages device pairing, and stores and forwards desktop-to-desktop handoffs in SQLite. |
| LAN receiver | `backend/run_lan_server.py` | FastAPI service that generates a handoff from a capture and delivers it to the Android app over the same Wi-Fi network. |
| Android app | `mobile/` | Kotlin app that receives, displays, and reopens handoff packages. It can also load the bundled sample or import a JSON file. |

A Windows native messaging host (`native_host/`) supplies device information to the extension for the desktop-to-desktop flow.

## Features

- Captures tab metadata, visible page text, and interaction state through a Manifest V3 Chrome extension.
- Groups tabs into tasks using semantic embeddings (`sentence-transformers/all-mpnet-base-v2`) combined with lexical, relational, and temporal evidence.
- Groups related tasks into broader activities.
- Produces task and activity labels locally with YAKE keyphrase extraction, with optional higher-quality labels from an LLM through the NVIDIA API.
- Selects the cheapest state representation that is still sufficient to reconstruct each tab (`url`, `url_with_metadata`, or `url_with_content`), then removes redundant contexts while preserving coverage.
- Optionally enriches Google Sheets tabs with spreadsheet contents using a read-only Google OAuth scope.
- Desktop-to-desktop handoff through the cloud API, using 8-digit pairing codes that expire after 5 minutes and per-device credentials stored only as hashes.
- Laptop-to-Android handoff over local Wi-Fi using a temporary pairing token.
- Android app that lists activities, tasks, and contexts and reopens each context in the phone's browser.

## How It Works

```
                    +--------------------------------------------+
                    |              Chrome extension              |
                    |  capture tabs | review activities | send   |
                    +----+----------------+----------------+-----+
                         |                |                |
        POST /process-contexts     device pairing     POST /handoff/generate
        and cloud handoff          and handoff        (same Wi-Fi)
                         |                |                |
              +----------v----------------v---+      +-----v------------------+
              |  Task and cloud API (:8000)   |      |   LAN receiver (:8001) |
              |  backend/task_engine pipeline |      |   in-memory device     |
              |  SQLite: devices, handoffs    |      |   inboxes              |
              +-------------------------------+      +-----+------------------+
                                                           |
                                              poll /devices/{id}/handoffs/next
                                                           |
                                                     +-----v------+
                                                     | Android app |
                                                     +------------+
```

The processing pipeline in `backend/task_engine/` runs these stages:

1. **Normalize.** Extension capture JSON becomes `ContextItem` objects (`normalizer.py`).
2. **Extract features and embeddings.** Tokens, entities, and timestamps (`features.py`) plus sentence embeddings (`embeddings.py`).
3. **Discover tasks.** Pairwise similarity (`similarity.py`) and membership evidence (`membership.py`) cluster contexts into tasks (`task_inference.py`).
4. **Discover activities.** Related tasks are clustered into broader activities (`activity_inference.py`).
5. **Select state.** Candidate representations are generated (`state_representation.py`), checked for sufficiency (`sufficiency.py`), and the lowest-cost sufficient one is chosen per context (`state_selector.py`).
6. **Minimize.** Redundant contexts are removed while preserving information coverage (`minimum_context_selector.py`).
7. **Build handoff packages.** Task-level and activity-level packages are assembled (`handoff.py`) and delivered to the target device.

## Project Structure

```
TaskFlow/
├── main.py                          Diagnostic end-to-end run on data/real_session.json
├── test_activity_inference.py       Generates an Android-format handoff JSON from a capture
├── test_google_sheets.py            Google Sheets API connectivity check
├── test_sheets_adapter.py           Reads a Google Sheets URL through GoogleSheetsAdapter
├── requirements.txt                 Python dependencies
├── HANDOFF_SETUP.md                 Windows notes for the same-Wi-Fi Android handoff
├── taskflow_native_host.spec        PyInstaller spec for the native messaging host
├── backend/
│   ├── cloud_handoff_server.py      Task processing, device pairing, cloud handoff (SQLite)
│   ├── handoff_server.py            Same-Wi-Fi receiver application (in-memory state)
│   ├── run_lan_server.py            Starts the receiver on the laptop's private Wi-Fi address
│   ├── handoff_pipeline.py          Capture to Android handoff document, with validation
│   └── task_engine/
│       ├── api.py                   POST /process-contexts router
│       ├── models.py                Data classes (ContextItem, TaskCandidate, ...)
│       ├── normalizer.py            Capture JSON to ContextItem
│       ├── features.py              Tokens, entities, timestamps, stopwords
│       ├── embeddings.py            Sentence-transformer embeddings
│       ├── similarity.py            Semantic, lexical, temporal, activity similarity
│       ├── membership.py            Task membership scoring
│       ├── task_inference.py        Task discovery and local labeling (YAKE)
│       ├── activity_inference.py    Activity discovery
│       ├── task_label_generator.py  NVIDIA API client for optional LLM labels
│       ├── state_representation.py  Candidate state representations per context
│       ├── sufficiency.py           Sufficiency check for each representation
│       ├── state_selector.py        Chooses the lowest-cost sufficient representation
│       ├── minimum_context_selector.py  Removes redundant contexts
│       ├── reconstruction.py        Rebuilds a resource from a representation
│       ├── handoff.py               Task and activity handoff packages
│       ├── google_auth.py           Google OAuth (read-only Sheets scope)
│       └── google_sheets_adapter.py Reads spreadsheet contents
├── chrome_extension/                Manifest V3 extension (popup, service worker, content script)
├── mobile/                          Android app (Kotlin, Gradle)
├── native_host/                     Windows native messaging host and installer script
├── data/
│   ├── real_session.json            Sample extension capture (7 contexts)
│   ├── test_session.json            Larger sample capture (12 contexts) used by the test scripts
│   ├── google_sheets_test.json      Sample Google Sheets adapter output
│   └── activity_handoff.json        Sample Android-format handoff (also bundled in the app)
└── tests/                           Standalone test scripts for individual engine modules
```

## Prerequisites

| Requirement | Needed for | Notes |
|---|---|---|
| Python 3.10 or newer | Backend | The code uses `X \| None` type syntax. |
| Google Chrome | Extension | The extension does not run in Incognito windows. |
| Internet access on first run | Backend | The embedding model is downloaded from Hugging Face the first time it is used, and PyTorch is installed as a dependency. Allow several gigabytes of free disk space. |
| Windows 10 or 11 | Native host, firewall steps | The commands below use PowerShell. Equivalents for macOS and Linux are shown where the Python commands differ. |
| Android Studio, JDK 17 | Android app | The project uses Android Gradle Plugin 8.12.1, Gradle 8.13, Kotlin 2.1.10, compile SDK 36, and Build Tools 36.1.0. Android Studio offers to install missing SDK components. |
| Android 7.0 (API 24) or newer phone | Android app | A physical device on the same Wi-Fi network as the laptop. |
| NVIDIA API key | LLM labeling | Optional. See [Configuration and API Keys](#configuration-and-api-keys). |
| Google OAuth client file | Google Sheets enrichment | Optional, except for `main.py`. See [Configuration and API Keys](#configuration-and-api-keys). |

## Installation

Clone the repository and create a virtual environment from the project root.

**Windows (PowerShell)**

```powershell
git clone https://github.com/navyasripenmetsa/TaskFlow.git
cd TaskFlow

py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

If PowerShell blocks script activation, skip the `Activate.ps1` line and call the interpreter directly in every command below, for example `.\.venv\Scripts\python.exe -m pip install -r requirements.txt`.

**macOS and Linux**

```bash
git clone https://github.com/navyasripenmetsa/TaskFlow.git
cd TaskFlow

python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

All remaining commands assume the virtual environment is active and that you are in the project root, because the backend is run as the `backend` package (`python -m backend...`).

The NLTK stopword corpus is not required. If it is not installed, `features.py` automatically uses scikit-learn's English stopword list.

## Configuration and API Keys

TaskFlow runs without any API keys, using local fallbacks. Add the credentials below to enable the optional features.

### 1. NVIDIA API key (optional, recommended)

The NVIDIA API is used to generate natural task and activity labels and goals. Without a key, the backend prints `LLM labeling unavailable. Using local fallback` and labels tasks locally with keyphrase extraction. This message is expected and harmless.

1. Create an account at [build.nvidia.com](https://build.nvidia.com) and generate an API key. Keys typically begin with `nvapi-`.
2. In the project root (the same folder as `requirements.txt`), create a file named `.env`:

   ```env
   # Required for LLM-based task and activity labels
   NVIDIA_API_KEY=your_nvidia_api_key_here

   # Optional: override the default model
   # NVIDIA_MODEL=nvidia/nemotron-3-nano-omni-30b-a3b-reasoning
   ```

3. Restart any running backend server so the key is picked up.

Notes:

- The client calls `https://integrate.api.nvidia.com/v1` through the OpenAI-compatible Python SDK.
- Values in `.env` override variables already set in your shell (`load_dotenv(override=True)`).
- If the default model is not available to your key, set `NVIDIA_MODEL` to one that is.
- `.env` is listed in `.gitignore`. Never commit it.

### 2. Google Sheets OAuth credentials (optional)

Only needed if you want TaskFlow to read the contents of Google Sheets tabs it captures. Access is read-only (`spreadsheets.readonly`).

1. In the [Google Cloud Console](https://console.cloud.google.com), create or select a project.
2. Enable the **Google Sheets API** for the project.
3. Configure the OAuth consent screen. While the app is in testing mode, add your own Google account as a test user.
4. Create an **OAuth client ID** of type **Desktop app**.
5. Download the client file, rename it to `credentials.json`, and place it in the project root.
6. On first use, a browser window opens for Google sign-in and consent. The resulting token is saved to `token.json` in the project root and refreshed automatically afterwards.

Notes:

- `credentials.json` and `token.json` are listed in `.gitignore`. Never commit them.
- The API server (`/process-contexts`) only attempts Sheets access when a captured tab is a Google Sheets URL. If credentials are missing or expired, it logs a warning and continues without spreadsheet contents.
- `main.py` creates the Sheets adapter unconditionally, so it fails with `Google OAuth credentials not found` unless `credentials.json` exists. Use `test_activity_inference.py` if you do not have Google credentials.
- To delete the stored consent, remove `token.json`.

### 3. Environment variable reference

Set these in `.env` or in the shell before starting the relevant server. In PowerShell: `$env:NAME = "value"`. In bash: `export NAME=value`.

| Variable | Default | Used by | Description |
|---|---|---|---|
| `NVIDIA_API_KEY` | none | Task and activity labeling | NVIDIA API key. Optional. Without it, local labeling is used. |
| `NVIDIA_MODEL` | `nvidia/nemotron-3-nano-omni-30b-a3b-reasoning` | Task and activity labeling | Model name sent to the NVIDIA API. |
| `TASKFLOW_PAIRING_TOKEN` | `change-this-local-dev-token` | Cloud API | Shared secret for registering devices and issuing credentials. Mandatory when the app runs on Render, where startup fails without it. |
| `TASKFLOW_DB_PATH` | `taskflow_cloud.db` | Cloud API | Path of the SQLite database file. Created automatically. |
| `TASKFLOW_BIND_HOST` | auto-detected | LAN receiver | Private IPv4 address of your Wi-Fi adapter. Set it if auto-detection fails. |
| `TASKFLOW_PORT` | `8000` | LAN receiver | Port for the LAN receiver (1 to 65535). |

The LAN receiver generates a fresh random pairing token every time it starts and prints it to the console. It is not configured by an environment variable.

### 4. Server address and token used by the Chrome extension

The extension's cloud settings are constants in the source rather than input fields. Edit `chrome_extension/popup.js` if your setup differs from the local default, then click **Reload** for the extension on `chrome://extensions`.

| Constant or value in `popup.js` | Default | Change it when |
|---|---|---|
| `PROCESSING_API_URL` | `http://127.0.0.1:8000/process-contexts` | The task API runs on another host or port. |
| `CLOUD_URL` | `http://127.0.0.1:8000` | The cloud API runs on another host or port, for example when pairing two different computers or after deploying it. |
| Token fallback inside `getCloudConfig()` | `change-this-local-dev-token` | You set `TASKFLOW_PAIRING_TOKEN` on the server to anything else. The two values must match. |

The Android handoff does not use these constants. Its server address and token are entered in the extension's **Mobile connection** panel and in the Android app's **Connection Settings**.

## Running TaskFlow

### Option A: Generate a handoff from sample data (no extension, no phone)

This is the quickest way to confirm the installation works. It runs the full inference pipeline on a bundled capture and writes an Android-format JSON file.

```bash
python test_activity_inference.py --input data/real_session.json --output data/generated_activity_handoff.json
```

The first run downloads the embedding model, so it can take a few minutes. The output is a new file and does not overwrite `data/activity_handoff.json`. You can import the generated file into the Android app with **Import JSON**.

For a verbose diagnostic run that prints similarity matrices, discovered tasks, and handoff package statistics, use:

```bash
python main.py
```

`main.py` requires `credentials.json` (see [Google Sheets OAuth credentials](#2-google-sheets-oauth-credentials-optional)).

### Option B: Full system

#### Step 1. Start the task and cloud API

From the project root, in a dedicated terminal:

```powershell
python -m uvicorn backend.cloud_handoff_server:app --host 127.0.0.1 --port 8000
```

Check that it is running at <http://127.0.0.1:8000/health>. Interactive API documentation is available at <http://127.0.0.1:8000/docs>. The SQLite database `taskflow_cloud.db` is created in the folder you started the server from. The embedding model is loaded on the first processing request, so the first **Capture & Process** is slower than later ones.

#### Step 2. Load the Chrome extension

1. Open `chrome://extensions`.
2. Turn on **Developer mode**.
3. Click **Load unpacked** and select the `chrome_extension` folder.
4. Pin the TaskFlow extension to the toolbar.

#### Step 3. Capture and process tabs

1. Open the tabs you want to hand off.
2. Click the TaskFlow extension and choose **Capture & Process**.
3. Review the discovered activities, tasks, and contexts in the popup.

The popup can also copy or download the raw captured JSON, import a handoff JSON, and clear the stored activity history (all under **Advanced Tools**).

#### Step 4a. Hand off to another desktop

This flow uses the cloud API from Step 1 and needs the native messaging host, which reads the device name and operating system for registration. The native host is Windows-only.

**Build and register the native host (once per Windows account)**

```powershell
python -m pip install pyinstaller
pyinstaller --clean --noconfirm taskflow_native_host.spec
```

Copy the extension ID shown for TaskFlow on `chrome://extensions` (32 characters), then register the host:

```powershell
.\native_host\install_taskflow_host.ps1 -ExtensionId <32-character-extension-id>
```

The script validates the ID, writes `native_host/com.taskflow.native.json`, and registers it under the current user's Chrome native messaging registry key. The generated manifest is machine-specific and is ignored by Git. If **Register This Device** still reports a device detection error afterwards, reload the extension and restart Chrome.

**Register and pair devices**

1. On the first device, open the extension, expand **Manage Devices**, and click **Register This Device**. The device is registered and receives a credential.
2. On the same device, click **Generate Pairing Code**. The 8-digit code is valid for 5 minutes.
3. On the second device (another computer or Chrome profile with the extension loaded), expand **Manage Devices**, enter the code under **Pair This Device**, and click **Pair Device**.
4. On the sending device, click **Refresh Devices**, choose the destination device, select an activity (or a single task), and click **Send Activity**.
5. On the receiving device, click **Check for Incoming Activity**.

Two different computers can only pair if both can reach the cloud API. Start it with `--host 0.0.0.0` (or deploy it), and set `CLOUD_URL` and `PROCESSING_API_URL` in `popup.js` to that address. Two Chrome profiles on the same machine work with the default `127.0.0.1` address.

#### Step 4b. Hand off to an Android phone over Wi-Fi

**1. Start the LAN receiver**

Open a second terminal in the project root. If the cloud API from Step 1 is also running, give the receiver a different port, because both default to 8000:

```powershell
$env:TASKFLOW_PORT = "8001"
python -m backend.run_lan_server
```

On macOS or Linux: `TASKFLOW_PORT=8001 python -m backend.run_lan_server`.

The server prints its address and a temporary pairing token, for example:

```
Laptop address: http://192.168.1.23:8001
Pairing token: <random token>
```

Keep this terminal open. The pairing token changes every time the server starts, and restarting the server clears all registered devices and pending handoffs.

If the server cannot find your Wi-Fi adapter, run `ipconfig`, find the **IPv4 Address** under your connected Wi-Fi adapter, and set it explicitly:

```powershell
$env:TASKFLOW_BIND_HOST = "192.168.1.23"
python -m backend.run_lan_server
```

Use your own address, not the example. The value must be a private IPv4 address.

If Windows Firewall prompts, allow Python on **Private networks only**. If no prompt appears, create an inbound TCP rule for the chosen port with the Private profile. Do not enable a Public profile rule or router port forwarding.

**2. Build and install the Android app**

1. Open the `mobile` folder in Android Studio and let Gradle sync. Install any SDK components Android Studio requests (Android SDK Platform 36, Build Tools 36.1.0). `local.properties` is created by Android Studio and is not committed.
2. On the phone, enable Developer options and USB debugging, connect it to the computer, and click **Run** in Android Studio.

Command-line alternative (requires the Android SDK and JDK 17):

```powershell
cd mobile
.\gradlew.bat assembleDebug
```

On macOS or Linux use `./gradlew assembleDebug`. The APK is written to `mobile/app/build/outputs/apk/debug/app-debug.apk`; install it with `adb install` or by copying it to the phone.

**3. Pair the app and the extension**

1. Connect the laptop and the phone to the same Wi-Fi network. The network must not isolate clients from each other.
2. In the Android app, tap **Connection Settings**, enter the printed server URL (for example `http://192.168.1.23:8001`) and the pairing token, and tap **Save**. Then tap **Receive Handoff**. The app registers itself and waits for a handoff.
3. In Chrome, open the TaskFlow extension, run **Capture & Process**, expand **Mobile connection** under **Send to Android over Wi-Fi**, enter the same server URL and token, and click **Save mobile connection**.
4. Click **Send to Mobile**. Keep the Android app open until it reports that the handoff was received.
5. In the app, review the activity, task, and context cards and tap **Open in browser** to reopen a context.

The server URL must be the root address only (no path). For plain HTTP the Android app accepts only `localhost` and private IPv4 ranges (`10.x.x.x`, `172.16.x.x` to `172.31.x.x`, `192.168.x.x`).

The Android app also works without any server: **Load sample handoff package** shows the bundled `activity_handoff.json`, and **Import JSON** opens any handoff file, including one generated in Option A.

## Input Data Format

The extension produces, and the backend accepts, a capture document with this shape (values shortened):

```json
{
  "schema_version": "1.0",
  "captured_at": "2026-11-03T03:49:48.527Z",
  "context_count": 1,
  "contexts": [
    {
      "context_id": "ctx_001",
      "source": { "tab_id": 123, "window_id": 456 },
      "content": {
        "title": "Page title",
        "url": "https://example.com/page",
        "domain": "example.com",
        "text": "Visible page text"
      },
      "state": {
        "active": false,
        "last_interaction": "2026-11-03T03:49:12.135Z",
        "interaction": { "scroll": { "x": 0, "y": 0 }, "selection": "", "form_values": [] }
      },
      "reconstruction": {
        "method": "url",
        "target": "https://example.com/page"
      }
    }
  ]
}
```

Validation rules enforced by `backend/handoff_pipeline.py`:

- `contexts` must be a non-empty list of at most 100 tabs with unique `context_id` values.
- `source.tab_id` and `source.window_id` must be integers.
- `content.title`, `url`, `domain`, and `text` must be strings, and `url` must be an HTTP(S) URL.
- `state.active` must be a boolean.
- `reconstruction.method` must be `url`, `url_with_metadata`, or `url_with_content`, and `target` must be an HTTP(S) URL.
- Total page text across all contexts must not exceed 1.5 million characters.

## API Reference

FastAPI generates interactive documentation at `/docs` on each running service.

### Task and cloud API (`backend.cloud_handoff_server:app`)

| Method and path | Authentication | Purpose |
|---|---|---|
| `GET /health` | none | Health check. |
| `POST /process-contexts` | none | Discover tasks and activities and build optimized handoff packages from a capture. |
| `POST /devices/register` | `X-Taskflow-Token` | Register a device. |
| `POST /devices/credentials/issue` | `X-Taskflow-Token` | Issue a credential to an already registered device. |
| `POST /pairing/create` | `X-Taskflow-Device-Credential` | Create an 8-digit pairing code valid for 5 minutes. |
| `POST /pairing/verify` | pairing code | Register a new device and issue its credential. |
| `GET /devices` | `X-Taskflow-Device-Credential` | List registered devices. |
| `POST /devices/heartbeat/{device_id}` | `X-Taskflow-Device-Credential` | Update a device's last-seen time. |
| `POST /handoff` | `X-Taskflow-Device-Credential` | Send an activity package to a target device. |
| `GET /devices/{device_id}/handoff` | `X-Taskflow-Device-Credential` | Receive the next pending handoff for this device. |

### LAN receiver (`backend.run_lan_server`)

All endpoints other than `/health`, `/pair`, and `/receiver` require the `X-Taskflow-Token` header.

| Method and path | Purpose |
|---|---|
| `GET /health` | Health check. |
| `GET /pair` | Returns the pairing token, but only to requests from the laptop itself. |
| `POST /devices/register` | Register a device (the Android app does this when you tap Receive Handoff). |
| `POST /devices/heartbeat/{device_id}` | Keep a device marked as online. |
| `GET /devices` | List devices seen within the last 30 seconds. |
| `POST /handoff/generate` | Run the inference pipeline on a capture and queue the result for a device. At most 20 handoffs may be pending per device. |
| `GET /devices/{device_id}/handoffs/next` | Return the next queued handoff, or 204 if none. |
| `POST /devices/{device_id}/handoffs/{handoff_id}/ack` | Acknowledge a handoff so it is removed from the queue. |
| `GET /receiver` | Simple browser-based receiver page. |

## Testing

The files in `tests/` are standalone scripts that print results, not pytest suites. They import the engine as `task_engine`, so put `backend` on the Python path and run them from the project root, where `data/test_session.json` is resolved:

```powershell
$env:PYTHONPATH = "backend"
python tests\test_features.py
python tests\test_selector.py
python tests\test_similarity.py
python tests\test_task_inference.py
python tests\test_membership.py
python tests\test_sufficiency.py
python tests\test_reconstruction.py
python tests\test_handoff.py
```

On macOS or Linux: `PYTHONPATH=backend python tests/test_features.py`.

Exceptions and notes:

- `tests/test_embeddings.py` opens `../data/test_session.json`, so run it from inside the `tests` folder: `cd tests`, set `$env:PYTHONPATH = "..\backend"`, then `python test_embeddings.py`.
- `test_features.py` and `test_selector.py` do not load the embedding model and run quickly. Most other scripts load it and need the first-run download.
- `test_google_sheets.py` and `test_sheets_adapter.py` (in the project root) require `credentials.json`. `test_sheets_adapter.py` prompts for a Google Sheets URL.

## Troubleshooting

| Symptom | Cause and fix |
|---|---|
| `LLM labeling unavailable. Using local fallback: NVIDIA_API_KEY is missing from the .env file.` | No key was found. Add `NVIDIA_API_KEY` to `.env` in the project root, or ignore the message to use local labels. |
| `FileNotFoundError: Google OAuth credentials not found` | `credentials.json` is missing. Only `main.py` and the Sheets scripts require it; see the Google setup section. |
| `ModuleNotFoundError: No module named 'backend'` | Run commands from the project root using `python -m ...` or `python -m uvicorn backend....`. |
| `ModuleNotFoundError: No module named 'task_engine'` | Set `PYTHONPATH=backend` when running scripts in `tests/`. |
| First **Capture & Process** or **Send to Mobile** is very slow | The embedding model is being downloaded and loaded. Later requests reuse it. |
| Port 8000 is already in use | The cloud API and LAN receiver both default to 8000. Set `TASKFLOW_PORT=8001` for the LAN receiver. |
| `Could not reach the laptop server. Check its address, same Wi-Fi, and Windows Firewall.` | Confirm the address printed by the server, that both devices share a non-isolated Wi-Fi network, and that the firewall allows Python on Private networks. |
| `Open TaskFlow Android and tap Receive Handoff first.` | The extension only lists devices seen within the last 30 seconds. Open the app, confirm Connection Settings are saved, and tap Receive Handoff. |
| `Invalid pairing token` | The LAN receiver token changes on every restart. Re-enter the new token in both the extension and the Android app. For the cloud API, the extension's token fallback in `popup.js` must equal `TASKFLOW_PAIRING_TOKEN`. |
| Android reports an invalid server address | Use the root URL such as `http://192.168.1.23:8001`, with no path, and a private IPv4 address. |
| `Device detection failed` or device registration fails | The native host is not built or registered. Rebuild it, re-run `install_taskflow_host.ps1` with the correct extension ID, and restart Chrome. |
| Extension changes have no effect | Click **Reload** for TaskFlow on `chrome://extensions` after editing any extension file. |
| Extension does not work in a private window | Incognito is disabled in `manifest.json`. Use a normal window. |

## Security and Privacy Notes

- **What is sent to NVIDIA.** When `NVIDIA_API_KEY` is set, only compact, locally extracted summaries are sent: keyphrases and task labels and descriptions. The code is written to exclude raw page text, titles, URLs, domains, and form values (see `_build_group_summary` in `task_inference.py`). Without a key, nothing leaves your machine for labeling.
- **Local development defaults are not secure.** The default cloud token `change-this-local-dev-token` is public. Set `TASKFLOW_PAIRING_TOKEN` to a long random value for any deployment beyond your own machine, and mirror it in `popup.js`.
- **CORS is open.** Both servers allow requests from any origin. Restrict `allow_origins` before exposing a server outside a trusted network.
- **The LAN receiver is for private networks.** It serves plain HTTP. Allow it through the firewall on the Private profile only, and do not forward its port on your router. The Android app permits cleartext HTTP so that it can talk to the laptop on the local network.
- **Captures contain page content.** Capture files can include page text and form field values. Review `data/real_session.json` and any file you generate before sharing or committing it.
- **Secrets.** `.env`, `credentials.json`, `token.json`, and `*.db` files are listed in `.gitignore`. Keep them out of version control.

## License

Released under the MIT License. See [LICENSE](LICENSE) for details.

Author: Navya Sri Penmetsa
