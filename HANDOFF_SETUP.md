# TaskFlow laptop-to-Android handoff

This local receiver transfers handoffs only between devices that can reach the
laptop on the same Wi-Fi network. It does not use the cloud server.

## Start the laptop server

From the TaskFlow project root in PowerShell:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m backend.run_lan_server
```

The server prints its laptop URL and a temporary pairing token. Keep the
terminal open. The inference model is loaded on the first Send to Mobile and
may need to download once; later sends reuse the local cache.

If the server cannot select the Wi-Fi adapter automatically, run `ipconfig`,
find the **IPv4 Address** under the connected **Wireless LAN adapter Wi-Fi**,
then start it with:

```powershell
$env:TASKFLOW_BIND_HOST = "192.168.1.23"
.\.venv\Scripts\python.exe -m backend.run_lan_server
```

Replace the example address with the Wi-Fi IPv4 address shown by `ipconfig`.
If Windows Firewall prompts, allow Python on **Private networks** only. If no
prompt appears, create an inbound TCP rule for port 8000 with the Private
profile. Do not enable a Public profile rule or router port forwarding.

## Pair the Android app and extension

1. Connect the laptop and Android phone to the same non-isolated Wi-Fi.
2. In TaskFlow Android, open **Connection Settings** and enter the printed
   server URL and pairing token. Save them, then tap **Receive Handoff**.
3. In Chrome, open the TaskFlow extension and expand **Mobile connection**.
   Enter the same server URL and token, then save.
4. Capture the desired browser tabs, then tap **Send to Mobile**. Leave the
   Android app open until it reports the handoff was received.

The server keeps pending handoffs in memory until Android acknowledges them.
Restarting the laptop server clears its registered devices and pending inboxes;
the phone and extension can register again using the new token.

## Generate a handoff JSON file locally

The same generation pipeline can be run without the server:

```powershell
.\.venv\Scripts\python.exe test_activity_inference.py --input data/real_session.json --output data/generated_activity_handoff.json
```

The default output is a separate generated file and does not replace the
bundled Android sample.
