#!/usr/bin/env python3
"""Call the add_sub model with the KServe v2 HTTP/JSON protocol (no tritonclient dependency)."""
import json
import urllib.request

URL = "http://localhost:8000/v2/models/add_sub/infer"
payload = {
    "inputs": [
        {"name": "INPUT0", "shape": [4], "datatype": "FP32", "data": [1, 2, 3, 4]},
        {"name": "INPUT1", "shape": [4], "datatype": "FP32", "data": [10, 20, 30, 40]},
    ]
}
req = urllib.request.Request(URL, data=json.dumps(payload).encode(), headers={"Content-Type": "application/json"})
with urllib.request.urlopen(req, timeout=30) as resp:
    out = json.load(resp)

for o in out["outputs"]:
    print(f'{o["name"]}: {o["data"]}')
# OUTPUT0: [11.0, 22.0, 33.0, 44.0]
# OUTPUT1: [-9.0, -18.0, -27.0, -36.0]
