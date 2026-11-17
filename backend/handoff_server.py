import secrets
from threading import RLock
from typing import Any
from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, Response
from pydantic import BaseModel, Field
import time


app = FastAPI(title="TaskFlow Handoff Server")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "X-Taskflow-Token"],
)

# Generate a temporary pairing token when the server starts.
PAIRING_TOKEN = secrets.token_urlsafe(24)

# Holds the latest activity package in memory.
handoff_store: dict[str, Any] = {}
# Devices that have registered with TaskFlow.
registered_devices: dict[str, dict[str, Any]] = {}
# Activity packages waiting for a particular device.
device_inboxes: dict[str, dict[str, Any]] = {}
# Android receives the complete activities document through this queue.
android_handoff_queues: dict[str, list[dict[str, Any]]] = {}
_state_lock = RLock()

class HandoffRequest(BaseModel):
    activity_package: dict[str, Any] = Field(...)
    target_device_id: str | None = None
class DeviceRegistration(BaseModel):
    device_id: str = Field(..., min_length=1, max_length=128)
    device_name: str = Field(..., min_length=1, max_length=128)
    user_agent: str = ""


class GenerateHandoffRequest(BaseModel):
    capture: dict[str, Any]
    target_device_id: str = Field(..., min_length=1, max_length=128)

def verify_token(token: str | None) -> None:
    if not token or not secrets.compare_digest(token, PAIRING_TOKEN):
        raise HTTPException(status_code=401, detail="Invalid pairing token")


@app.get("/health")
def health():
    return {"status": "running", "service": "TaskFlow"}


@app.get("/pair")
def pair(request: Request):
    # Never disclose the bearer token to another device on the LAN.
    if request.client is None or request.client.host not in {"127.0.0.1", "::1"}:
        raise HTTPException(
            status_code=403,
            detail="Pairing token is available only in the server console",
        )
    return {
        "service": "TaskFlow",
        "pairing_token": PAIRING_TOKEN
    }


@app.post("/handoff")
def receive_handoff(
    request: HandoffRequest,
    x_taskflow_token: str | None = Header(default=None)
):
    verify_token(x_taskflow_token)

    package = request.activity_package

    if not package.get("activity_id") or not isinstance(
        package.get("contexts"), list
    ):
        raise HTTPException(
            status_code=400,
            detail="Invalid activity handoff package"
        )

    with _state_lock:
        handoff_store["latest"] = package
    if request.target_device_id:
        with _state_lock:
            if request.target_device_id not in registered_devices:
                raise HTTPException(
                    status_code=404,
                    detail="Target device is not registered"
                )
            device_inboxes[request.target_device_id] = package
    return {
        "success": True,
        "activity_id": package["activity_id"],
        "context_count": len(package["contexts"])
    }


@app.post("/handoff/generate")
def generate_and_send_handoff(
    request: GenerateHandoffRequest,
    x_taskflow_token: str | None = Header(default=None),
):
    """Run the existing local inference pipeline and queue its Android JSON."""
    verify_token(x_taskflow_token)
    device_id = request.target_device_id
    with _state_lock:
        if device_id not in registered_devices:
            raise HTTPException(status_code=404, detail="Target device is not registered")

    try:
        from backend.handoff_pipeline import (
            HandoffGenerationError,
            generate_activity_handoff,
        )

        document = generate_activity_handoff(request.capture)
    except HandoffGenerationError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=f"Handoff generation failed: {error}",
        ) from error

    handoff_id = secrets.token_urlsafe(12)
    with _state_lock:
        queue = android_handoff_queues.setdefault(device_id, [])
        if len(queue) >= 20:
            raise HTTPException(
                status_code=429,
                detail="The device inbox is full. Receive or clear pending handoffs first.",
            )
        queue.append({"handoff_id": handoff_id, "document": document})

    activities = document["activities"]
    context_count = sum(
        len(activity["activity_handoff_package"]["contexts"])
        for activity in activities
    )
    return {
        "success": True,
        "handoff_id": handoff_id,
        "activity_count": len(activities),
        "context_count": context_count,
    }


@app.get("/handoff")
def get_handoff(
    x_taskflow_token: str | None = Header(default=None)
):
    verify_token(x_taskflow_token)

    with _state_lock:
        if "latest" not in handoff_store:
            raise HTTPException(
                status_code=404,
                detail="No handoff package available"
            )

        return handoff_store["latest"]

@app.get("/receiver", response_class=HTMLResponse)
def mobile_receiver():
    return r"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <title>TaskFlow Mobile Receiver</title>
        <style>
            body {
                font-family: Arial, sans-serif;
                max-width: 600px;
                margin: 30px auto;
                padding: 20px;
                background: #f4f6f8;
            }
            .card {
                background: white;
                padding: 22px;
                border-radius: 12px;
            }
            input, button {
                width: 100%;
                box-sizing: border-box;
                padding: 13px;
                margin: 9px 0;
                font-size: 16px;
            }
            button {
                background: #1769aa;
                color: white;
                border: 0;
                border-radius: 7px;
            }
            .context {
                padding: 12px 0;
                border-bottom: 1px solid #ddd;
            }
            a { overflow-wrap: anywhere; }
            #status { margin-top: 15px; }
        </style>
    </head>
    <body>
        <div class="card">
            <h2>TaskFlow</h2>
            <p>Receive an activity from your other device.</p>

            <input
                id="token"
                type="password"
                placeholder="Enter pairing token"
            >

            <button id="receive">Receive Activity</button>

            <div id="status"></div>
            <div id="activity"></div>
        </div>

    <script>
    const receiveButton = document.getElementById("receive");
    const status = document.getElementById("status");
    const activity = document.getElementById("activity");

    let heartbeatTimer = null;

    function getDeviceId() {
        let deviceId = localStorage.getItem("taskflow_device_id");

        if (!deviceId) {
            deviceId = crypto.randomUUID
                ? crypto.randomUUID()
                : "device-" + Date.now() + "-" + Math.random().toString(36).slice(2);

            localStorage.setItem("taskflow_device_id", deviceId);
        }

        return deviceId;
    }

    async function registerDevice(token) {
        const deviceId = getDeviceId();
        const userAgent = navigator.userAgent;

        const deviceName = /Android/i.test(userAgent)
            ? "Android Phone"
            : /iPhone|iPad/i.test(userAgent)
                ? "iPhone/iPad"
                : "Mobile Device";

        const response = await fetch("/devices/register", {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "X-Taskflow-Token": token
            },
            body: JSON.stringify({
                device_id: deviceId,
                device_name: deviceName,
                user_agent: userAgent
            })
        });

        if (!response.ok) {
            throw new Error("Device registration failed: " + response.status);
        }

        if (heartbeatTimer) {
            clearInterval(heartbeatTimer);
        }

        heartbeatTimer = setInterval(async () => {
            try {
                await fetch("/devices/heartbeat/" + encodeURIComponent(deviceId), {
                    method: "POST",
                    headers: {
                        "X-Taskflow-Token": token
                    }
                });
            } catch (error) {
                console.error("Heartbeat failed:", error);
            }
        }, 10000);

        return deviceName;
    }

    receiveButton.addEventListener("click", async () => {
        const token = document.getElementById("token").value.trim();

        if (!token) {
            status.textContent = "Enter your pairing token.";
            return;
        }

        receiveButton.disabled = true;
        status.textContent = "Registering this device...";

        try {
            const deviceName = await registerDevice(token);
            status.textContent = deviceName + " registered. Receiving activity...";

           let data = null;

status.textContent = "Device registered. Waiting for activity...";

for (let attempt = 0; attempt < 60; attempt++) {
    const response = await fetch(
        "/devices/" + encodeURIComponent(getDeviceId()) + "/handoff",
        {
            headers: {
                "X-Taskflow-Token": token
            }
        }
    );

    if (response.ok) {
        data = await response.json();
        break;
    }

    if (response.status !== 404) {
        throw new Error("Server error: " + response.status);
    }

    await new Promise(resolve => setTimeout(resolve, 2000));
}

if (!data) {
    throw new Error("No activity received within 2 minutes.");
}

            if (!Array.isArray(data.contexts)) {
                throw new Error("Invalid activity package.");
            }

            activity.replaceChildren();

            const heading = document.createElement("h3");
            heading.textContent = data.activity_label || "Received activity";
            activity.appendChild(heading);

            const count = document.createElement("p");
            count.textContent = data.contexts.length + " contexts received.";
            activity.appendChild(count);

            data.contexts.forEach((context) => {
                const item = document.createElement("div");
                item.className = "context";

                const title = document.createElement("p");
                title.textContent =
                    context.title ||
                    context.page_title ||
                    context.state?.title ||
                    context.context_id ||
                    "Untitled context";

                item.appendChild(title);

                const url = context.reconstruction_target;

                if (typeof url === "string" && /^https?:\/\//i.test(url)) {
                    const link = document.createElement("a");
                    link.href = url;
                    link.target = "_blank";
                    link.rel = "noopener noreferrer";
                    link.textContent = "Open this context";
                    item.appendChild(link);
                } else {
                    const unavailable = document.createElement("p");
                    unavailable.textContent = "No valid URL available.";
                    item.appendChild(unavailable);
                }

                activity.appendChild(item);
            });

            status.textContent = "Device registered. Activity received successfully!";
        } catch (error) {
            status.textContent = "Receive failed: " + error.message;
        } finally {
            receiveButton.disabled = false;
        }
    });
</script>
    </body>
    </html>
    """
@app.post("/devices/register")
def register_device(
    request: DeviceRegistration,
    x_taskflow_token: str | None = Header(default=None)
):
    verify_token(x_taskflow_token)

    with _state_lock:
        registered_devices[request.device_id] = {
            "device_id": request.device_id,
            "device_name": request.device_name,
            "user_agent": request.user_agent,
            "last_seen": time.time()
        }

    return {
        "success": True,
        "message": "Device registered",
        "device_id": request.device_id
    }


@app.post("/devices/heartbeat/{device_id}")
def device_heartbeat(
    device_id: str,
    x_taskflow_token: str | None = Header(default=None)
):
    verify_token(x_taskflow_token)

    with _state_lock:
        if device_id not in registered_devices:
            raise HTTPException(status_code=404, detail="Device not registered")
        registered_devices[device_id]["last_seen"] = time.time()

    return {"success": True}


@app.get("/devices")
def list_devices(
    x_taskflow_token: str | None = Header(default=None)
):
    verify_token(x_taskflow_token)

    now = time.time()
    with _state_lock:
        online_devices = [
            dict(device) for device in registered_devices.values()
            if now - device["last_seen"] <= 30
        ]

    return {"devices": online_devices}


@app.get("/devices/{device_id}/handoffs/next")
def get_next_android_handoff(
    device_id: str,
    x_taskflow_token: str | None = Header(default=None),
):
    verify_token(x_taskflow_token)
    with _state_lock:
        device = registered_devices.get(device_id)
        if device is None:
            raise HTTPException(status_code=404, detail="Device not registered")

        device["last_seen"] = time.time()
        queue = android_handoff_queues.get(device_id, [])
        if not queue:
            return Response(status_code=204)
        return queue[0]


@app.post("/devices/{device_id}/handoffs/{handoff_id}/ack")
def acknowledge_android_handoff(
    device_id: str,
    handoff_id: str,
    x_taskflow_token: str | None = Header(default=None),
):
    verify_token(x_taskflow_token)
    with _state_lock:
        queue = android_handoff_queues.get(device_id)
        if queue is None:
            raise HTTPException(status_code=404, detail="No pending handoff for this device")

        for index, handoff in enumerate(queue):
            if secrets.compare_digest(handoff["handoff_id"], handoff_id):
                del queue[index]
                return {"success": True, "handoff_id": handoff_id}
    raise HTTPException(status_code=404, detail="Handoff is no longer pending")

@app.get("/devices/{device_id}/handoff")
def get_device_handoff(
    device_id: str,
    x_taskflow_token: str | None = Header(default=None)
):
    verify_token(x_taskflow_token)

    with _state_lock:
        if device_id not in device_inboxes:
            raise HTTPException(
                status_code=404,
                detail="No activity waiting for this device"
            )

        package = device_inboxes.pop(device_id)
        return package
