# script.py
import sys
import json

def process(data):
    # Example: Uppercase the input payload
    msg = json.loads(data)
    payload = msg.get("payload", "")
    return json.dumps({"payload": payload.upper()})

if __name__ == "__main__":
    input_data = sys.stdin.read()
    result = process(input_data)
    print(result)