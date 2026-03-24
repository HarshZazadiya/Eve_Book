import os
import httpx
import requests
from dotenv import load_dotenv
load_dotenv()

header_secret = os.getenv("HEADER_SECRET")

async def workflow_request(data : dict, request_url : str, method : str = "POST"):
    async with httpx.AsyncClient() as client:
        response = await client.request(
            method = method.upper(),
            url = request_url,
            json = data,
            headers = {"Authorization" : header_secret}
        )
        print(f"[workflow_request] {method} {request_url} → {response.status_code}")
        return response.json()
    
# ── Sync version (use inside @tool functions) ──
def workflow_request_sync(data: dict, request_url: str, method: str = "POST"):
    response = requests.request(
        method=method.upper(),
        url=request_url,
        json=data,
        headers={"Authorization": header_secret}
    )
    print(f"[workflow_request_sync] {method} {request_url} → {response.status_code}")
    return response.json()