import os
import requests
import asyncio
from dotenv import load_dotenv
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)) + '/..')

from AI.tools.workflows.workflow import workflow_request

load_dotenv()
header_secret = os.getenv("HEADER_SECRET")
print(f"Secret being sent: '{header_secret}'")

# ===========================================================================================================
# book event
# ===========================================================================================================
# temp = "attendees"
# webhook_data = {
#     "user_id": 1,
#     "user_name": "harsh",
#     "user_email": "harshzazadiya@gmail.com",
#     "event_id": 1,
#     "event_title": "Fresher Party",
#     "event_venue": "Dome",
#     "event_date": "2026-03-23",
#     "ticket_count": 1,
#     "ticket_price": 100,
#     "total_amount": 100,
#     "booking_id": 1,
#     "sheet_id" : "1bORW5okEkbNJ2rqBC3JCs5qPDYDzRdA9vUccwLxSidA",
#     "sheet_name" : f"Freser_Party_{temp}"
# }

# respone = requests.post(
#     "http://localhost:5678/webhook-test/event", 
#     json = webhook_data, 
#     headers = {
#         "Authorization" : header_secret
#     }                 
# )
# print(respone)

# ===========================================================================================================
# create new user
# ===========================================================================================================

# header_secret = os.getenv("HEADER_SECRET")

# data = {
#     "id": 2,
#     "username": "harsh",
#     "email": "harshzazadiya@gmail.com",
#     "role": "user"
# }

# result = asyncio.run(workflow_request(data, "http://localhost:5678/webhook-test/new", "POST"))
# print(f"Status: {result}")

# ===========================================================================================================
# update event
# ===========================================================================================================

# webhook_data = {
#     "user_id": 1,
#     "user_name": "harsh",
#     "user_email": "harshzazadiya@gmail.com",
#     "event_id": 1,
#     "event_title": "Fresher Party",
#     "event_venue": "Dome",
#     "event_date": "2026-03-23",
#     "ticket_count": 1,
#     "ticket_price": 10,
#     "total_amount": 10,
#     "booking_id": 1,
#     "available_seats": 100
# }

# result = asyncio.run(workflow_request(webhook_data, "http://localhost:5678/webhook-test/event", "PUT"))
# print(f"Status: {result}")

# ===========================================================================================================
# promote user to host
# ===========================================================================================================

# data = {
#             "id" : 2,
#             "username" : "harsh",
#             "email" : "harshzazadiya@gmail.com",
#             "role" : "host",
#             "company_name" : "harsh",
#             "fees_paid" : 10000
#         }
        
# result = asyncio.run(workflow_request(data, "http://localhost:5678/webhook-test/promote", "POST"))
# print(f"Status: {result}")

# ===========================================================================================================
# Host an event
# ===========================================================================================================

# data = {
#   "event_id" : 1,
#   "event_name" : "Fresher Party",
#   "event_date" : "2026-03-23",
#   "sheet_name" : "Fresher_Party_attendees",
#   "host_credentials" : "harshzazadiya.aids22@scet.ac.in"
# }

# result = asyncio.run(workflow_request(data, "http://localhost:5678/webhook-test/new-event", "POST"))
# print("Status:", result.get("sheet_id"))  

# ===========================================================================================================
# Delete Booking
# ===========================================================================================================
temp = "attendees"
webhook_data = {
    "user_id": 1,
    "user_name": "harsh",
    "user_email": "harshzazadiya@gmail.com",
    "event_id": 1,
    "event_title": "Fresher Party",
    "booking_id": 1,
    "sheet_id" : "1bORW5okEkbNJ2rqBC3JCs5qPDYDzRdA9vUccwLxSidA",
    "sheet_name" : f"Freser_Party_{temp}"
}

respone = requests.delete(
    "http://localhost:5678/webhook-test/event", 
    json = webhook_data, 
    headers = {
        "Authorization" : header_secret
    }                 
)
print(respone)