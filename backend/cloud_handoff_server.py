import json
import os
import secrets
import sqlite3
import time
from typing import Any
from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from .task_engine.api import router as task_engine_router
import hashlib

# --------------------------------------------------
# Configuration
# --------------------------------------------------

# Detect whether the application is running on Render
IS_RENDER = (
    os.getenv("RENDER", "").lower() == "true"
    or bool(os.getenv("RENDER_SERVICE_ID"))
)

# Read the pairing token from environment variables
CONFIGURED_TOKEN = os.getenv("TASKFLOW_PAIRING_TOKEN")

if IS_RENDER and not CONFIGURED_TOKEN:
    raise RuntimeError(
        "TASKFLOW_PAIRING_TOKEN must be configured on Render."
    )

# Keep the default token for local development only
APP_TOKEN = CONFIGURED_TOKEN or "change-this-local-dev-token"
DB_PATH = os.getenv("TASKFLOW_DB_PATH", "taskflow_cloud.db")

app = FastAPI(title="TaskFlow Cloud Handoff Server")
app.include_router(task_engine_router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


# --------------------------------------------------
# Database
# --------------------------------------------------

def get_db():
    connection = sqlite3.connect(DB_PATH, timeout=30)
    connection.row_factory = sqlite3.Row
    return connection


def initialize_database():
    connection = get_db()

    try:
        connection.execute("""
            CREATE TABLE IF NOT EXISTS devices (
                device_id TEXT PRIMARY KEY,
                device_name TEXT NOT NULL,
                user_agent TEXT,
                last_seen REAL NOT NULL
            )
        """)
        connection.execute("""
            CREATE TABLE IF NOT EXISTS handoffs (
                handoff_id INTEGER PRIMARY KEY AUTOINCREMENT,
                target_device_id TEXT,
                activity_package TEXT NOT NULL,
                created_at REAL NOT NULL,
                received INTEGER NOT NULL DEFAULT 0
            )
        """)
        connection.execute("""
            CREATE TABLE IF NOT EXISTS device_credentials (
                credential_hash TEXT PRIMARY KEY,
                device_id TEXT NOT NULL,
                created_at REAL NOT NULL,
                last_used REAL,
                revoked_at REAL
            )
        """)

        connection.execute("""
            CREATE INDEX IF NOT EXISTS idx_device_credentials_device_id
            ON device_credentials(device_id)
        """)
        connection.execute("""
            CREATE TABLE IF NOT EXISTS pairing_codes (
                code_hash TEXT PRIMARY KEY,
                expires_at REAL NOT NULL,
                used INTEGER NOT NULL DEFAULT 0
            )
        """)
        connection.commit()
    finally:
        connection.close()


initialize_database()


# --------------------------------------------------
# Request models
# --------------------------------------------------

class HandoffRequest(BaseModel):
    activity_package: dict[str, Any] = Field(...)
    target_device_id: str | None = None


class DeviceRegistration(BaseModel):
    device_id: str
    device_name: str
    user_agent: str = ""
class DeviceCredentialRequest(BaseModel):
    device_id: str
class PairingVerificationRequest(BaseModel):
    pairing_code: str
    device_id: str
    device_name: str
    user_agent: str = ""
# --------------------------------------------------
# Authentication
# --------------------------------------------------

def verify_token(token: str | None):
    if not token or not secrets.compare_digest(token, APP_TOKEN):
        raise HTTPException(
            status_code=401,
            detail="Invalid pairing token"
        )
def hash_device_credential(credential: str) -> str:
    return hashlib.sha256(
        credential.encode("utf-8")
    ).hexdigest()


def verify_device_credential(credential: str | None):
    if not credential:
        raise HTTPException(
            status_code=401,
            detail="Missing device credential"
        )

    credential_hash = hash_device_credential(credential)

    connection = get_db()

    try:
        row = connection.execute("""
            SELECT device_id
            FROM device_credentials
            WHERE credential_hash = ?
              AND revoked_at IS NULL
        """, (credential_hash,)).fetchone()

        if not row:
            raise HTTPException(
                status_code=401,
                detail="Invalid or revoked device credential"
            )

        connection.execute("""
            UPDATE device_credentials
            SET last_used = ?
            WHERE credential_hash = ?
        """, (time.time(), credential_hash))

        connection.commit()

        return row["device_id"]

    finally:
        connection.close()

@app.post("/devices/credentials/issue")
def issue_device_credential(
    request: DeviceCredentialRequest,
    x_taskflow_token: str | None = Header(default=None)
):
    verify_token(x_taskflow_token)

    connection = get_db()

    try:
        device = connection.execute("""
            SELECT device_id
            FROM devices
            WHERE device_id = ?
        """, (request.device_id,)).fetchone()

        if not device:
            raise HTTPException(
                status_code=404,
                detail="Device is not registered"
            )

        # Generate a unique credential
        credential = secrets.token_urlsafe(32)

        credential_hash = hash_device_credential(
            credential
        )

        connection.execute("""
            INSERT INTO device_credentials (
                credential_hash,
                device_id,
                created_at
            )
            VALUES (?, ?, ?)
        """, (
            credential_hash,
            request.device_id,
            time.time()
        ))

        connection.commit()

        return {
            "success": True,
            "device_id": request.device_id,
            "device_credential": credential,
            "message": "Device credential issued"
        }

    finally:
        connection.close()
# --------------------------------------------------
# Temporary Device Pairing
# --------------------------------------------------

@app.post("/pairing/create")
def create_pairing_code(
    x_taskflow_token: str | None = Header(default=None)
):
    verify_token(x_taskflow_token)

    # Generate a random 8-digit pairing code
    code = f"{secrets.randbelow(100_000_000):08d}"

    code_hash = hashlib.sha256(
        code.encode()
    ).hexdigest()

    expires_at = time.time() + 300  # 5 minutes

    connection = get_db()

    try:
        connection.execute("""
            INSERT INTO pairing_codes (
                code_hash, expires_at, used
            )
            VALUES (?, ?, 0)
        """, (code_hash, expires_at))

        connection.commit()
    finally:
        connection.close()

    return {
        "success": True,
        "pairing_code": code,
        "expires_in_seconds": 300
    }


@app.post("/pairing/verify")
def verify_pairing_code(request: PairingVerificationRequest):

    code_hash = hashlib.sha256(
        request.pairing_code.encode("utf-8")
    ).hexdigest()

    connection = get_db()

    try:
        connection.execute("BEGIN IMMEDIATE")

        row = connection.execute("""
            SELECT code_hash, expires_at, used
            FROM pairing_codes
            WHERE code_hash = ?
        """, (code_hash,)).fetchone()

        if (
            not row
            or row["used"] == 1
            or row["expires_at"] < time.time()
        ):
            connection.rollback()

            raise HTTPException(
                status_code=401,
                detail="Invalid, expired, or already-used pairing code"
            )

        # Generate a unique credential for the new device
        credential = secrets.token_urlsafe(32)

        credential_hash = hash_device_credential(credential)

        # Register the new device
        connection.execute("""
            INSERT INTO devices (
                device_id,
                device_name,
                user_agent,
                last_seen
            )
            VALUES (?, ?, ?, ?)
            ON CONFLICT(device_id) DO UPDATE SET
                device_name = excluded.device_name,
                user_agent = excluded.user_agent,
                last_seen = excluded.last_seen
        """, (
            request.device_id,
            request.device_name,
            request.user_agent,
            time.time()
        ))

        # Store only the credential hash
        connection.execute("""
            INSERT INTO device_credentials (
                credential_hash,
                device_id,
                created_at
            )
            VALUES (?, ?, ?)
        """, (
            credential_hash,
            request.device_id,
            time.time()
        ))

        # Consume the pairing code
        connection.execute("""
            UPDATE pairing_codes
            SET used = 1
            WHERE code_hash = ?
        """, (code_hash,))

        connection.commit()

        return {
            "success": True,
            "device_id": request.device_id,
            "device_credential": credential,
            "message": "Device paired successfully"
        }

    except HTTPException:
        raise

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()
# --------------------------------------------------
# Health check
# --------------------------------------------------

@app.get("/health")
def health():
    return {
        "status": "running",
        "service": "TaskFlow Cloud"
    }


# --------------------------------------------------
# Device registration
# --------------------------------------------------

@app.post("/devices/register")
def register_device(
    request: DeviceRegistration,
    x_taskflow_token: str | None = Header(default=None)
):
    verify_token(x_taskflow_token)

    connection = get_db()

    try:
        connection.execute("""
            INSERT INTO devices (
                device_id, device_name, user_agent, last_seen
            )
            VALUES (?, ?, ?, ?)
            ON CONFLICT(device_id) DO UPDATE SET
                device_name = excluded.device_name,
                user_agent = excluded.user_agent,
                last_seen = excluded.last_seen
        """, (
            request.device_id,
            request.device_name,
            request.user_agent,
            time.time()
        ))

        connection.commit()
    finally:
        connection.close()

    return {
        "success": True,
        "device_id": request.device_id,
        "message": "Device registered"
    }


@app.post("/devices/heartbeat/{device_id}")
def device_heartbeat(
    device_id: str,
    x_taskflow_token: str | None = Header(default=None)
):
    verify_token(x_taskflow_token)

    connection = get_db()

    try:
        cursor = connection.execute("""
            UPDATE devices
            SET last_seen = ?
            WHERE device_id = ?
        """, (time.time(), device_id))

        connection.commit()

        if cursor.rowcount == 0:
            raise HTTPException(
                status_code=404,
                detail="Device not registered"
            )
    finally:
        connection.close()

    return {"success": True}


@app.get("/devices")
def list_devices(
    x_taskflow_token: str | None = Header(default=None)
):
    verify_token(x_taskflow_token)

    connection = get_db()

    try:
        rows = connection.execute("""
            SELECT device_id, device_name, user_agent, last_seen
            FROM devices
            ORDER BY last_seen DESC
        """).fetchall()

        return {"devices": [dict(row) for row in rows]}
    finally:
        connection.close()


# --------------------------------------------------
# Send activity
# --------------------------------------------------

@app.post("/handoff")
def send_handoff(
    request: HandoffRequest,
    x_taskflow_token: str | None = Header(default=None)
):
    verify_token(x_taskflow_token)

    package = request.activity_package

    if (
        not package.get("activity_id")
        or not isinstance(package.get("contexts"), list)
        or not package["contexts"]
    ):
        raise HTTPException(
            status_code=400,
            detail="Invalid activity handoff package"
        )

    connection = get_db()

    try:
        if request.target_device_id:
            device = connection.execute("""
                SELECT device_id FROM devices
                WHERE device_id = ?
            """, (request.target_device_id,)).fetchone()

            if not device:
                raise HTTPException(
                    status_code=404,
                    detail="Target device is not registered"
                )

        connection.execute("""
            INSERT INTO handoffs (
                target_device_id, activity_package, created_at
            )
            VALUES (?, ?, ?)
        """, (
            request.target_device_id,
            json.dumps(package),
            time.time()
        ))

        connection.commit()
    finally:
        connection.close()

    return {
        "success": True,
        "activity_id": package["activity_id"],
        "context_count": len(package["contexts"])
    }


# --------------------------------------------------
# Receive latest activity (general receiver)
# --------------------------------------------------

@app.get("/handoff")
def get_latest_handoff(
    x_taskflow_token: str | None = Header(default=None)
):
    verify_token(x_taskflow_token)

    connection = get_db()

    try:
        row = connection.execute("""
            SELECT activity_package
            FROM handoffs
            WHERE target_device_id IS NULL
            ORDER BY handoff_id DESC
            LIMIT 1
        """).fetchone()

        if not row:
            raise HTTPException(
                status_code=404,
                detail="No handoff package available"
            )

        return json.loads(row["activity_package"])
    finally:
        connection.close()


# --------------------------------------------------
# Receive activity for a specific device
# --------------------------------------------------

@app.get("/devices/{device_id}/handoff")
def get_device_handoff(
    device_id: str,
    x_taskflow_token: str | None = Header(default=None)
):
    verify_token(x_taskflow_token)

    connection = get_db()

    try:
        connection.execute("BEGIN IMMEDIATE")

        row = connection.execute("""
            SELECT handoff_id, activity_package
            FROM handoffs
            WHERE target_device_id = ?
              AND received = 0
            ORDER BY handoff_id ASC
            LIMIT 1
        """, (device_id,)).fetchone()

        if not row:
            connection.rollback()
            raise HTTPException(
                status_code=404,
                detail="No pending activity for this device"
            )

        connection.execute("""
            UPDATE handoffs
            SET received = 1
            WHERE handoff_id = ?
        """, (row["handoff_id"],))

        connection.commit()

        return json.loads(row["activity_package"])

    except HTTPException:
        raise
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()