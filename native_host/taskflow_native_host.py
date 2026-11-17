
import json
import os
import platform
import socket
import struct
import sys


def read_message():
    raw_length = sys.stdin.buffer.read(4)

    if not raw_length:
        return None

    message_length = struct.unpack("<I", raw_length)[0]
    message = sys.stdin.buffer.read(message_length)

    return json.loads(message.decode("utf-8"))


def send_message(data):
    encoded = json.dumps(data).encode("utf-8")
    sys.stdout.buffer.write(struct.pack("<I", len(encoded)))
    sys.stdout.buffer.write(encoded)
    sys.stdout.buffer.flush()


def get_device_info(request):
    profile_label = request.get("profile_label", "Default")

    hostname = socket.gethostname()
    os_name = platform.system()

    return {
        "success": True,
        "device_name": hostname,
        "hostname": hostname,
        "device_type": "windows",
        "manufacturer": "",
        "model": platform.machine(),
        "os_name": os_name,
        "os_version": platform.release(),
        "app_name": "TaskFlow Chrome Extension",
        "profile_label": profile_label
    }


def main():
    try:
        request = read_message()

        if request is None:
            return

        response = get_device_info(request)
        send_message(response)

    except Exception as error:
        send_message({
            "success": False,
            "error": str(error)
        })


if __name__ == "__main__":
    main()
