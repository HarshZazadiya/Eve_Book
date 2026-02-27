import logging
logging.getLogger("streamlit").setLevel(logging.ERROR)
from datetime import datetime
import streamlit as st
import requests

BASE_URL = "http://localhost:8000"

st.set_page_config(page_title="Event Booking Platform", layout="wide")

# =================================================
# CHAT INTERFACE
# =================================================
def chat_interface():
    """Chat interface component"""
    st.header("💬 Chat with AI Assistant")
    
    # Initialize session state for chat
    if "current_thread_id" not in st.session_state:
        st.session_state.current_thread_id = None
    if "messages" not in st.session_state:
        st.session_state.messages = []
    
    # Sidebar for thread management
    with st.sidebar:
        st.subheader("Chat History")
        
        # New chat button
        if st.button("➕ New Chat", use_container_width=True):
            st.session_state.current_thread_id = None
            st.session_state.messages = []
            st.rerun()
        
        st.divider()
        
        # Fetch user's threads
        try:
            headers = {"Authorization": f"Bearer {st.session_state.token}"}
            threads_res = requests.get(f"{BASE_URL}/chat/threads", headers=headers)
            
            if threads_res.status_code == 200:
                threads = threads_res.json()
                for thread in threads:
                    col1, col2 = st.columns([4, 1])
                    with col1:
                        preview = (thread['last_message'] or "Empty chat")[:30] + "..." if thread.get('last_message') and len(thread['last_message']) > 30 else (thread['last_message'] or "Empty chat")
                        if st.button(f"📝 {preview}", key=f"thread_{thread['id']}", use_container_width=True):
                            st.session_state.current_thread_id = thread['id']
                            # Load messages for this thread
                            msgs_res = requests.get(f"{BASE_URL}/chat/threads/{thread['id']}/messages", headers=headers)
                            if msgs_res.status_code == 200:
                                st.session_state.messages = msgs_res.json()
                            st.rerun()
                    with col2:
                        if st.button("🗑️", key=f"del_{thread['id']}"):
                            requests.delete(f"{BASE_URL}/chat/threads/{thread['id']}", headers=headers)
                            if st.session_state.current_thread_id == thread['id']:
                                st.session_state.current_thread_id = None
                                st.session_state.messages = []
                            st.rerun()
        except Exception as e:
            st.error(f"Error loading chat threads: {e}")
    
    # Display chat messages
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.write(msg["content"])
    
    # Chat input
    if prompt := st.chat_input("Ask me about events..."):
        # Add user message to UI
        with st.chat_message("user"):
            st.write(prompt)
        
        # Add to session state
        st.session_state.messages.append({"role": "user", "content": prompt})
        
        # Send to API
        try:
            headers = {"Authorization": f"Bearer {st.session_state.token}"}
            response = requests.post(
                f"{BASE_URL}/chat/ask",
                headers=headers,
                json={
                    "message": prompt,
                    "thread_id": st.session_state.current_thread_id
                }
            )
            
            if response.status_code == 200:
                data = response.json()
                
                # Update thread ID for subsequent messages
                st.session_state.current_thread_id = data["thread_id"]
                
                # Add assistant response to UI
                with st.chat_message("assistant"):
                    st.write(data["response"])
                
                # Add to session state
                st.session_state.messages.append({"role": "assistant", "content": data["response"]})
            else:
                st.error(f"Failed to get response: {response.status_code}")
        except Exception as e:
            st.error(f"Error: {e}")

# ---------------- SESSION ----------------
if "token" not in st.session_state:
    st.session_state.token = None
if "role" not in st.session_state:
    st.session_state.role = None
if "chat_open" not in st.session_state:
    st.session_state.chat_open = False
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

# ---------------- HELPERS ----------------
def headers():
    return {"Authorization": f"Bearer {st.session_state.token}"}

def login(username, password):
    return requests.post(
        f"{BASE_URL}/auth/token",
        data={"username": username, "password": password}
    )

def detect_role():
    r = requests.get(f"{BASE_URL}/auth/me", headers=headers())
    data = r.json()
    
    if data.get("role") == "admin":
        return "admin"
    return data.get("type")

# ---------------- SMART TABS ----------------
def smart_tabs(tab_list, key="tab"):
    if key not in st.session_state:
        st.session_state[key] = tab_list[0]
    
    selected = st.radio("", tab_list, horizontal=True)
    
    if selected != st.session_state[key]:
        st.session_state[key] = selected
        st.rerun()
    
    return st.session_state[key]

# ---------------- PROFILE MENU ----------------
def profile_menu():
    with st.popover("👤 Profile"):
        if st.session_state.role == "user":
            res = requests.get(f"{BASE_URL}/user/", headers=headers())
        elif st.session_state.role == "host":
            res = requests.get(f"{BASE_URL}/host/", headers=headers())
        else:
            res = requests.get(f"{BASE_URL}/auth/me", headers=headers())
        
        if res.status_code == 200:
            data = res.json()
            for k, v in data.items():
                st.write(f"**{k.capitalize()}** : {v}")
        
        st.divider()
        
        if st.button("Logout"):
            st.session_state.clear()
            st.rerun()

# ---------------- WALLET UI ----------------
def wallet_ui():
    st.header("💰 Wallet")
    
    r = requests.get(f"{BASE_URL}/myWallet", headers=headers())
    
    if r.status_code == 200:
        data = r.json()
        balance = data.get("balance") or data.get("wallet_balance") or 0
        
        # Create a nice card for wallet
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            st.metric("Current Balance", f"₹ {balance:,.2f}", delta=None)
        
        if "warning" in data:
            st.warning(data["warning"])
    
    st.divider()
    
    # Top up section
    st.subheader("Add Money to Wallet")
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col2:
        amount = st.number_input("Amount (₹)", min_value=1, value=100, step=100)
        
        if st.button("➕ Add Money", use_container_width=True):
            with st.spinner("Processing..."):
                response = requests.post(
                    f"{BASE_URL}/topUp",
                    headers=headers(),
                    json={"amount": amount}
                )
                if response.status_code == 200:
                    st.success(f"✅ Successfully added ₹{amount} to your wallet!")
                    st.rerun()
                else:
                    st.error(f"❌ Failed: {response.text}")

# =================================================
# AUTH UI
# =================================================
if not st.session_state.token:
    st.title("🎟 Event Booking Platform")
    
    tab1, tab2 = st.tabs(["Login", "Register"])
    
    with tab1:
        username = st.text_input("Username / Email", key="login_user")
        password = st.text_input("Password", type="password", key="login_pass")
        
        if st.button("Login"):
            res = login(username, password)
            
            if res.status_code == 200:
                st.session_state.token = res.json()["access_token"]
                st.session_state.role = detect_role()
                st.rerun()
            else:
                st.error("Invalid credentials")
    
    with tab2:
        role = st.radio("Register As", ["User", "Host"])
        
        if role == "User":
            username = st.text_input("Username")
            email = st.text_input("Email")
            password = st.text_input("Password", type="password")
            
            if st.button("Register User"):
                r = requests.post(
                    f"{BASE_URL}/auth/user",
                    json={"username": username, "email": email, "password": password}
                )
                if r.status_code == 201:
                    st.success("User Registered")
                else:
                    st.error(r.text)
        else:
            company = st.text_input("Company Name")
            email = st.text_input("Email")
            password = st.text_input("Password", type="password")
            
            if st.button("Register Host"):
                r = requests.post(
                    f"{BASE_URL}/auth/host",
                    json={"company_name": company, "email": email, "password": password}
                )
                if r.status_code == 201:
                    st.success("Host Registered")
                else:
                    st.error(r.text)
    
    st.stop()

role = st.session_state.role

# ---------------- HEADER ----------------
col1, col2 = st.columns([6, 1])

with col1:
    st.title(f"Dashboard — {role.upper()}")

with col2:
    profile_menu()

# =================================================
# USER DASHBOARD
# =================================================
def user_dashboard():
    menu = smart_tabs(
        ["Wallet", "Browse Events", "My Bookings", "Promote To Host", "AI ChatBot"],
        key="user_tab"
    )
    
    if menu == "AI ChatBot":
        chat_interface()
    
    if menu == "Wallet":
        wallet_ui()
    
    if menu == "Browse Events":
        res = requests.get(f"{BASE_URL}/user/events", headers=headers())
        if res.status_code != 200:
            st.info("No events available right now.")
            return
        
        events_data = res.json()
        
        # Handle response format
        if isinstance(events_data, dict) and "events" in events_data:
            events = events_data["events"]
        elif isinstance(events_data, list):
            events = events_data
        else:
            events = []
        
        if not events:
            st.info("No events available right now.")
            return
        
        for e in sorted(events, key=lambda x: x.get("id", 0), reverse=True):
            with st.container(border=True):
                st.subheader(f"{e.get('title', 'Untitled')}")
                
                c1, c2, c3, c4 = st.columns(4)
                
                c1.write(f"📅 {e.get('date', 'Unknown')}")
                c2.write(f"🎟 Seats: {e.get('available_seats', 0)}")
                c3.write(f"💰 ₹{e.get('ticket_price', 0)}")
                c4.write(f"🏢 Host: {e.get('host_name', e.get('host_id', 'Unknown'))}")
                
                if st.button("Book", key=f"book_{e.get('id', e.get('event_id', 0))}"):
                    event_id = e.get('id', e.get('event_id'))
                    book_res = requests.post(
                        f"{BASE_URL}/user/event/{event_id}", 
                        headers=headers()
                    )
                    if book_res.status_code == 200:
                        st.success("Booked successfully!")
                        st.rerun()
                    else:
                        st.error(book_res.text)
                
                if e.get("more_details"):
                    st.link_button("More Details", f"{BASE_URL}{e['more_details']}")
    
    if menu == "My Bookings":
        res = requests.get(f"{BASE_URL}/user/myEvents", headers=headers())
        if res.status_code != 200:
            st.error("Failed to fetch bookings")
            return
        
        bookings_data = res.json()
        
        # Handle response format
        if isinstance(bookings_data, dict) and "bookings" in bookings_data:
            bookings = bookings_data["bookings"]
        elif isinstance(bookings_data, list):
            bookings = bookings_data
        else:
            bookings = []
        
        if not bookings:
            st.info("No bookings found")
            return
        
        for b in bookings:
            with st.container(border=True):
                st.subheader(f"Booking #{b.get('booking_id', 'N/A')}")
                st.write(f"Event ID: {b.get('event_id', 'N/A')}")
                st.write(f"Event: {b.get('event_title', 'Unknown')}")
                st.write(f"Tickets: {b.get('ticket_count', 1)}")
                
                # Get event details for document link
                events_res = requests.get(f"{BASE_URL}/user/events", headers=headers())
                if events_res.status_code == 200:
                    events_data = events_res.json()
                    all_events = events_data.get("events", events_data) if isinstance(events_data, dict) else events_data
                    event = next(
                        (ev for ev in all_events if ev.get("id") == b.get("event_id")),
                        None
                    )
                    
                    if event and event.get("more_details"):
                        st.link_button("More Details", f"{BASE_URL}{event['more_details']}")
                
                if st.button("Cancel", key=f"cancel_{b.get('booking_id')}"):
                    cancel_res = requests.delete(
                        f"{BASE_URL}/user/booking/{b.get('booking_id')}",
                        headers=headers()
                    )
                    if cancel_res.status_code == 200:
                        st.success("Cancelled successfully!")
                        st.rerun()
                    else:
                        st.error(cancel_res.text)
    
    if menu == "Promote To Host":
        st.warning("This will cost ₹10,000 from your wallet")
        if st.button("Pay ₹10,000 & Promote to Host"):
            res = requests.post(f"{BASE_URL}/user/promote-to-host", headers=headers())
            if res.status_code == 200:
                st.success("Promoted to Host successfully! Please login again.")
                st.session_state.clear()
                st.rerun()
            else:
                st.error(res.text)

# =================================================
# HOST DASHBOARD
# =================================================
def host_dashboard():
    menu = smart_tabs(
        ["Wallet", "Create Event", "My Events", "AI ChatBot"],
        key="host_tab"
    )
    
    if menu == "AI ChatBot":
        chat_interface()
    
    if menu == "Wallet":
        wallet_ui()
    
    elif menu == "Create Event":
        with st.form("create_event_form"):
            title = st.text_input("Title")
            venue = st.text_input("Venue")
            date_val = st.date_input("Date")
            seats = st.number_input("Seats", min_value=1, value=100)
            price = st.number_input("Ticket Price (₹)", min_value=1, value=100)
            document = st.file_uploader("Upload Event PDF (optional)", type=["pdf"])
            
            submitted = st.form_submit_button("Create Event")
            
            if submitted:
                data = {
                    "title": title,
                    "venue": venue,
                    "date": str(date_val),
                    "seats": seats,
                    "ticket_price": price
                }
                
                files = {}
                if document:
                    files["document"] = (document.name, document, "application/pdf")
                
                res = requests.post(
                    f"{BASE_URL}/host/event",
                    headers=headers(),
                    data=data,
                    files=files
                )
                
                if res.status_code == 200:
                    st.success("Event Created Successfully!")
                    st.rerun()
                else:
                    st.error(res.text)
    
    elif menu == "My Events":
        res = requests.get(f"{BASE_URL}/host/events", headers=headers())
        
        if res.status_code != 200:
            st.error("Failed to fetch events")
            return
        
        events_data = res.json()
        
        # Handle response format
        if isinstance(events_data, dict) and "events" in events_data:
            events = events_data["events"]
        elif isinstance(events_data, list):
            events = events_data
        else:
            events = []
        
        if not events:
            st.info("No events created yet")
            return
        
        for e in events:
            with st.expander(f"{e.get('title', 'Untitled')} — {e.get('date', 'Unknown')}"):
                st.write(f"📍 Venue: {e.get('venue', 'Unknown')}")
                st.write(f"🎟 Seats: {e.get('available_seats', 0)} / {e.get('seats', 0)}")
                st.write(f"💰 Ticket Price: ₹{e.get('ticket_price', 0)}")
                
                st.divider()
                
                col1, col2, col3, col4 = st.columns(4)
                
                # DELETE
                with col1:
                    if st.button("Delete", key=f"del_{e.get('id')}"):
                        del_res = requests.delete(
                            f"{BASE_URL}/host/event/{e.get('id')}",
                            headers=headers()
                        )
                        if del_res.status_code == 200:
                            st.success("Event deleted")
                            st.rerun()
                        else:
                            st.error(del_res.text)
                
                # VIEW DOCUMENT
                with col2:
                    if e.get("more_details"):
                        st.link_button("View Document", f"{BASE_URL}{e['more_details']}")
                
                # EDIT TOGGLE
                with col3:
                    if st.button("Edit Event", key=f"edit_toggle_{e.get('id')}"):
                        st.session_state[f"edit_mode_{e.get('id')}"] = not st.session_state.get(
                            f"edit_mode_{e.get('id')}", False
                        )
                
                # DOCUMENT TOGGLE
                with col4:
                    if st.button("Update Document", key=f"doc_toggle_{e.get('id')}"):
                        st.session_state[f"doc_mode_{e.get('id')}"] = not st.session_state.get(
                            f"doc_mode_{e.get('id')}", False
                        )
                
                # EDIT EVENT SECTION
                if st.session_state.get(f"edit_mode_{e.get('id')}", False):
                    st.divider()
                    st.subheader("Update Event Details")
                    
                    with st.form(f"edit_form_{e.get('id')}"):
                        new_title = st.text_input("Title", value=e.get('title', ''))
                        new_venue = st.text_input("Venue", value=e.get('venue', ''))
                        new_date = st.date_input(
                            "Date",
                            value=datetime.strptime(e.get('date', '2025-01-01'), "%Y-%m-%d").date()
                        )
                        new_seats = st.number_input("Seats", value=e.get('seats', 1), min_value=1)
                        new_price = st.number_input("Ticket Price", value=e.get('ticket_price', 1), min_value=1)
                        
                        if st.form_submit_button("Save Changes"):
                            update_data = {
                                "title": new_title,
                                "venue": new_venue,
                                "date": str(new_date),
                                "seats": new_seats,
                                "ticket_price": new_price
                            }
                            
                            upd_res = requests.put(
                                f"{BASE_URL}/host/event/{e.get('id')}",
                                headers=headers(),
                                json=update_data
                            )
                            
                            if upd_res.status_code == 200:
                                st.success("Event updated")
                                st.session_state[f"edit_mode_{e.get('id')}"] = False
                                st.rerun()
                            else:
                                st.error(upd_res.text)
                
                # UPDATE DOCUMENT SECTION
                if st.session_state.get(f"doc_mode_{e.get('id')}", False):
                    st.divider()
                    st.subheader("Upload New Document (PDF Only)")
                    
                    new_doc = st.file_uploader(
                        "Select PDF",
                        type=["pdf"],
                        key=f"doc_upload_{e.get('id')}"
                    )
                    
                    if new_doc and st.button("Upload Document", key=f"upload_btn_{e.get('id')}"):
                        files = {
                            "document": (new_doc.name, new_doc, "application/pdf")
                        }
                        
                        doc_res = requests.put(
                            f"{BASE_URL}/host/event_document/{e.get('id')}",
                            headers=headers(),
                            files=files
                        )
                        
                        if doc_res.status_code == 200:
                            st.success("Document updated successfully")
                            st.session_state[f"doc_mode_{e.get('id')}"] = False
                            st.rerun()
                        else:
                            st.error(doc_res.text)

# =================================================
# ADMIN DASHBOARD
# =================================================
def admin_dashboard():
    headers_auth = headers()
    
    tab = smart_tabs(
        ["Users", "Hosts", "Transactions", "Promotions", "Wallets", "AI Chatbot"],
        key="admin_tab"
    )
    
    if tab == "AI Chatbot":
        chat_interface()
    
    # ================= USERS =================
    if tab == "Users":
        users_res = requests.get(f"{BASE_URL}/admin/users", headers=headers_auth)
        bookings_res = requests.get(f"{BASE_URL}/admin/bookings", headers=headers_auth)
        events_res = requests.get(f"{BASE_URL}/admin/events", headers=headers_auth)
        
        if users_res.status_code != 200:
            st.error(f"Failed to fetch users: {users_res.text}")
            return
        
        users_data = users_res.json()
        bookings_data = bookings_res.json() if bookings_res.status_code == 200 else {}
        events_data = events_res.json() if events_res.status_code == 200 else {}
        
        # Handle response formats
        users = users_data.get("users", []) if isinstance(users_data, dict) else (users_data if isinstance(users_data, list) else [])
        bookings = bookings_data.get("bookings", []) if isinstance(bookings_data, dict) else (bookings_data if isinstance(bookings_data, list) else [])
        events = events_data.get("events", []) if isinstance(events_data, dict) else (events_data if isinstance(events_data, list) else [])
        
        if not users:
            st.info("No users found")
            return
        
        for u in users:
            with st.expander(f"{u.get('username', 'Unknown')} — {u.get('email', 'No email')}"):
                user_bookings = [
                    b for b in bookings 
                    if b.get("username") == u.get("username") or b.get("user_id") == u.get("id")
                ]
                
                if not user_bookings:
                    st.info("No bookings")
                else:
                    for b in user_bookings:
                        st.write(f"Event: {b.get('event_title', 'Unknown')}")
                        st.write(f"Tickets: {b.get('ticket_count', 0)}")
                        # Removed payment display as requested
                        
                        col1, col2 = st.columns(2)
                        
                        with col1:
                            if st.button("Delete Booking", key=f"admin_del_booking_{b.get('booking_id')}"):
                                del_res = requests.delete(
                                    f"{BASE_URL}/admin/booking/{b.get('booking_id')}",
                                    headers=headers_auth
                                )
                                if del_res.status_code == 200:
                                    st.success("Booking deleted")
                                    st.rerun()
                                else:
                                    st.error(del_res.text)
                        
                        with col2:
                            event = next(
                                (e for e in events if e.get("event_id") == b.get("event_id")),
                                None
                            )
                            if event and event.get("more_details"):
                                st.link_button("More Details", f"{BASE_URL}{event['more_details']}")
                        
                        st.divider()
    
    # ================= HOSTS =================
    elif tab == "Hosts":
        hosts_res = requests.get(f"{BASE_URL}/admin/hosts", headers=headers_auth)
        events_res = requests.get(f"{BASE_URL}/admin/events", headers=headers_auth)
        bookings_res = requests.get(f"{BASE_URL}/admin/bookings", headers=headers_auth)
        
        if hosts_res.status_code != 200:
            st.error(f"Failed to fetch hosts: {hosts_res.text}")
            return
        
        hosts_data = hosts_res.json()
        events_data = events_res.json() if events_res.status_code == 200 else {}
        bookings_data = bookings_res.json() if bookings_res.status_code == 200 else {}
        
        # Handle response formats
        hosts = hosts_data.get("hosts", []) if isinstance(hosts_data, dict) else (hosts_data if isinstance(hosts_data, list) else [])
        events = events_data.get("events", []) if isinstance(events_data, dict) else (events_data if isinstance(events_data, list) else [])
        bookings = bookings_data.get("bookings", []) if isinstance(bookings_data, dict) else (bookings_data if isinstance(bookings_data, list) else [])
        
        if not hosts:
            st.info("No hosts found")
            return
        
        for h in hosts:
            with st.expander(f"{h.get('company_name', h.get('username', 'Unknown'))} — {h.get('email', 'No email')}"):
                # Host info
                col1, col2 = st.columns(2)
                with col1:
                    st.write(f"**Host ID:** {h.get('host_id', h.get('id', 'N/A'))}")
                    st.write(f"**Company:** {h.get('company_name', 'N/A')}")
                with col2:
                    st.write(f"**Email:** {h.get('email', 'N/A')}")
                    st.write(f"**Fee Paid:** {'✅' if h.get('is_fee_paid') else '❌'}")
                
                # Demote button
                if st.button("👇 Demote to User", key=f"demote_{h.get('host_id', h.get('id'))}"):
                    host_id = h.get('host_id', h.get('id'))
                    demote_res = requests.post(
                        f"{BASE_URL}/admin/demote-host/{host_id}",
                        headers=headers_auth
                    )
                    if demote_res.status_code == 200:
                        st.success(f"Host {h.get('company_name', '')} demoted successfully!")
                        st.rerun()
                    else:
                        st.error(demote_res.text)
                
                st.divider()
                
                host_events = [
                    e for e in events 
                    if e.get("host_email") == h.get("email") or e.get("host_id") == h.get("host_id") or e.get("host_id") == h.get("id")
                ]
                
                if not host_events:
                    st.info("No events hosted")
                else:
                    st.subheader("Events")
                    for e in host_events:
                        with st.container(border=True):
                            st.write(f"**{e.get('title', 'Untitled')}**")
                            st.write(f"📍 {e.get('venue', 'No venue')} | 📅 {e.get('date', 'Unknown')}")
                            st.write(f"🎟 Seats: {e.get('available_seats', 0)} / {e.get('total_seats', 0)}")
                            st.write(f"💰 ₹{e.get('ticket_price', 0)}")
                            
                            col1, col2 = st.columns(2)
                            
                            with col1:
                                if st.button("Delete Event", key=f"admin_del_event_{e.get('event_id')}"):
                                    del_res = requests.delete(
                                        f"{BASE_URL}/admin/event/{e.get('event_id')}",
                                        headers=headers_auth
                                    )
                                    if del_res.status_code == 200:
                                        st.success("Event deleted")
                                        st.rerun()
                                    else:
                                        st.error(del_res.text)
                            
                            with col2:
                                if e.get("more_details"):
                                    st.link_button("More Details", f"{BASE_URL}{e['more_details']}")
                            
                            event_bookings = [
                                b for b in bookings if b.get("event_id") == e.get("event_id")
                            ]
                            
                            if event_bookings:
                                st.markdown("**Bookings:**")
                                for b in event_bookings:
                                    with st.container(border=True):
                                        st.write(f"👤 {b.get('username', 'Unknown')} - {b.get('ticket_count', 0)} tickets")
                                        
                                        if st.button("Delete", key=f"admin_del_booking_{b.get('booking_id')}"):
                                            del_res = requests.delete(
                                                f"{BASE_URL}/admin/booking/{b.get('booking_id')}",
                                                headers=headers_auth
                                            )
                                            if del_res.status_code == 200:
                                                st.success("Booking deleted")
                                                st.rerun()
                                            else:
                                                st.error(del_res.text)
    
    # ================= TRANSACTIONS =================
    elif tab == "Transactions":
        subtab = smart_tabs(
            ["Booking Transactions", "Hosting Transactions"],
            key="admin_tx_tab"
        )
        
        if subtab == "Booking Transactions":
            res = requests.get(f"{BASE_URL}/admin/booking-transactions", headers=headers_auth)
            
            if res.status_code != 200:
                st.error("Failed to fetch transactions")
                return
            
            tx_data = res.json()
            transactions = tx_data.get("transactions", []) if isinstance(tx_data, dict) else (tx_data if isinstance(tx_data, list) else [])
            
            if not transactions:
                st.info("No booking transactions")
            else:
                for t in transactions:
                    with st.container(border=True):
                        st.write(f"**Booking ID:** {t.get('booking_id', 'N/A')}")
                        st.write(f"**Event:** {t.get('event_title', 'Unknown')}")
                        st.write(f"**Amount:** ₹{t.get('amount', 0)}")
                        st.write(f"**Status:** {t.get('status', 'Unknown')}")
                        st.write(f"**Date:** {t.get('created_at', 'Unknown')}")
        
        else:  # Hosting Transactions
            res = requests.get(f"{BASE_URL}/admin/hosting-transactions", headers=headers_auth)
            
            if res.status_code != 200:
                st.error("Failed to fetch host transactions")
                return
            
            tx_data = res.json()
            transactions = tx_data.get("transactions", []) if isinstance(tx_data, dict) else (tx_data if isinstance(tx_data, list) else [])
            
            if not transactions:
                st.info("No hosting transactions")
            else:
                for t in transactions:
                    with st.container(border=True):
                        st.write(f"**Company:** {t.get('company_name', 'Unknown')}")
                        st.write(f"**Host ID:** {t.get('host_id', 'N/A')}")
                        st.write(f"**Amount:** ₹{t.get('amount', 0)}")
                        st.write(f"**Status:** {t.get('status', 'Unknown')}")
                        st.write(f"**Date:** {t.get('created_at', 'Unknown')}")
    
    # ================= PROMOTIONS =================
    elif tab == "Promotions":
        res = requests.get(f"{BASE_URL}/admin/promotions", headers=headers_auth)
        
        if res.status_code != 200:
            st.error("Failed to fetch promotions")
            return
        
        promo_data = res.json()
        promotions = promo_data.get("promotions", []) if isinstance(promo_data, dict) else (promo_data if isinstance(promo_data, list) else [])
        
        if not promotions:
            st.info("No promotions found")
        else:
            for p in promotions:
                with st.container(border=True):
                    # Only show fields that exist in the data
                    if p.get('company_name'):
                        st.subheader(p.get('company_name'))
                    elif p.get('username'):
                        st.subheader(p.get('username'))
                    
                    if p.get('amount'):
                        st.write(f"**Amount:** ₹{p.get('amount')}")
                    if p.get('status'):
                        st.write(f"**Status:** {p.get('status')}")
                    if p.get('created_at'):
                        st.write(f"**Date:** {p.get('created_at')}")
    
    # ================= WALLETS =================
    elif tab == "Wallets":
        res = requests.get(f"{BASE_URL}/admin/wallets", headers=headers_auth)
        
        if res.status_code != 200:
            st.error("Failed to fetch wallets")
            return
        
        wallet_data = res.json()
        wallets = wallet_data.get("wallets", []) if isinstance(wallet_data, dict) else (wallet_data if isinstance(wallet_data, list) else [])
        
        if not wallets:
            st.info("No wallets found")
        else:
            # Summary stats
            total_balance = sum(w.get('balance', 0) for w in wallets)
            user_wallets = len([w for w in wallets if w.get('owner_type') == 'user'])
            host_wallets = len([w for w in wallets if w.get('owner_type') == 'host'])
            
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Total Balance", f"₹{total_balance:,.2f}")
            with col2:
                st.metric("User Wallets", user_wallets)
            with col3:
                st.metric("Host Wallets", host_wallets)
            
            st.divider()
            
            # Wallet list
            for w in sorted(wallets, key=lambda x: x.get('balance', 0), reverse=True):
                with st.container(border=True):
                    col1, col2, col3 = st.columns([2, 1, 1])
                    
                    with col1:
                        owner_type = w.get('owner_type', 'Unknown').upper()
                        owner_name = w.get('username') or w.get('company_name') or f"ID {w.get('owner_id', 'N/A')}"
                        st.write(f"**{owner_type}:** {owner_name}")
                        if w.get('email'):
                            st.write(f"📧 {w.get('email')}")
                    
                    with col2:
                        st.metric("Balance", f"₹{w.get('balance', 0):,}")
                    
                    with col3:
                        if w.get('owner_type') == 'host' and w.get('balance', 0) < 500:
                            st.warning("⚠️ Low")

# =================================================
# ROUTER
# =================================================
if role == "user":
    user_dashboard()
elif role == "host":
    host_dashboard()
elif role == "admin":
    admin_dashboard()