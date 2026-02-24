from datetime import datetime

import streamlit as st
import requests

BASE_URL = "http://localhost:8000"

st.set_page_config(page_title="Event Booking Platform", layout="wide")

# ---------------- SESSION ----------------
if "token" not in st.session_state:
    st.session_state.token = None
if "role" not in st.session_state:
    st.session_state.role = None


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
        st.metric("Current Balance", f"₹ {balance}")

    st.divider()

    col1, col2 = st.columns([2, 1])

    with col1:
        amount = st.number_input("Top Up Amount", min_value=1)

    with col2:
        if st.button("➕ Add Money"):
            requests.post(
                f"{BASE_URL}/topUp",
                headers=headers(),
                json={"amount": amount}
            )
            st.success("Wallet Updated")
            st.rerun()


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
        ["Wallet", "Browse Events", "My Bookings", "Promote To Host"],
        key="user_tab"
    )

    if menu == "Wallet":
        wallet_ui()

    if menu == "Browse Events":

        res = requests.get(f"{BASE_URL}/user/events", headers=headers())
        if res.status_code != 200:
            st.info("No events available right now.")
            return
        events = res.json()
        if not isinstance(events, list) or len(events) == 0:
            st.info("No events available right now.")
            return

        for e in sorted(events, key=lambda x: x.get("id", 0), reverse=True):
            with st.container(border=True):

                st.subheader(f"{e['title']}")

                c1, c2, c3, c4 = st.columns(4)

                c1.write(f"📅 {e['date']}")
                c2.write(f"🎟 Seats: {e['available_seats']}")
                c3.write(f"💰 ₹{e['ticket_price']}")
                c4.write(f"🏢 Host ID: {e['host_id']}")

                if st.button("Book", key=f"book_{e['id']}"):
                    requests.post(f"{BASE_URL}/user/event/{e['id']}", headers=headers())
                    st.success("Booked")
                    st.rerun()
                if e.get("more_details"):
                    st.link_button(
                        "More Details",
                        f"{BASE_URL}{e['more_details']}"
                    )

    if menu == "My Bookings":
        res = requests.get(f"{BASE_URL}/user/myEvents", headers=headers())
        if res.status_code != 200:
            st.error("Failed to fetch bookings")
            return

        bookings = res.json()
        if not isinstance(bookings, list) or len(bookings) == 0:
            st.info("No bookings found")
            return

        for b in bookings:
            with st.container(border=True):

                st.subheader(f"Booking #{b['booking_id']}")
                st.write(f"Event ID : {b['event_id']}")
                st.write(f"Tickets : {b['ticket_count']}")

                # 🔥 Fetch event details to get document
                event_res = requests.get(
                    f"{BASE_URL}/user/events",
                    headers=headers()
                )

                if event_res.status_code == 200:
                    events = event_res.json()
                    event = next(
                        (ev for ev in events if ev["id"] == b["event_id"]),
                        None
                    )

                    if event and event.get("more_details"):
                        st.link_button(
                            "More Details",
                            f"{BASE_URL}{event['more_details']}"
                        )

                if st.button("Cancel", key=f"cancel_{b['booking_id']}"):
                    requests.delete(
                        f"{BASE_URL}/user/booking/{b['booking_id']}",
                        headers=headers()
                    )
                    st.success("Cancelled")
                    st.rerun()

    if menu == "Promote To Host":
        if st.button("Pay 10000 & Promote"):
            requests.post(f"{BASE_URL}/user/promote-to-host", headers=headers())
            st.success("Promoted")
            st.rerun()


# =================================================
# HOST DASHBOARD
# =================================================
# =================================================
# HOST DASHBOARD
# =================================================
def host_dashboard():

    menu = smart_tabs(
        ["Wallet", "Create Event", "My Events"],
        key="host_tab"
    )

    # ---------------- WALLET ----------------
    if menu == "Wallet":
        wallet_ui()

    # ---------------- CREATE EVENT ----------------
    elif menu == "Create Event":

        title = st.text_input("Title")
        venue = st.text_input("Venue")
        date_val = st.date_input("Date")
        seats = st.number_input("Seats", min_value=1)
        price = st.number_input("Ticket Price", min_value=1)

        document = st.file_uploader("Upload Event PDF (optional)", type=["pdf"])

        if st.button("Create Event"):

            data = {
                "title": title,
                "venue": venue,
                "date": str(date_val),
                "seats": seats,
                "ticket_price": price
            }

            files = {}
            if document:
                files["document"] = (
                    document.name,
                    document,
                    "application/pdf"
                )

            res = requests.post(
                f"{BASE_URL}/host/event",
                headers=headers(),
                data=data,
                files=files
            )

            if res.status_code == 200:
                st.success("Event Created Successfully")
                st.rerun()
            else:
                st.error(res.text)

    # ---------------- MY EVENTS ----------------
    elif menu == "My Events":

        res = requests.get(f"{BASE_URL}/host/events", headers=headers())

        if res.status_code != 200:
            st.error("Failed to fetch events")
            return

        events = res.json()

        if not events:
            st.info("No events created yet")
            return

        for e in events:

            with st.expander(f"{e['title']} — {e['date']}"):

                # ---------------- EVENT INFO ----------------
                st.write(f"📍 Venue: {e['venue']}")
                st.write(f"🎟 Seats: {e['available_seats']} / {e['seats']}")
                st.write(f"💰 Ticket Price: ₹{e['ticket_price']}")

                st.divider()

                col1, col2, col3, col4 = st.columns(4)

                # -------- DELETE --------
                with col1:
                    if st.button("Delete", key=f"del_{e['id']}"):
                        del_res = requests.delete(
                            f"{BASE_URL}/host/event/{e['id']}",
                            headers=headers()
                        )
                        if del_res.status_code == 200:
                            st.success("Event deleted")
                            st.rerun()
                        else:
                            st.error(del_res.text)

                # -------- VIEW DOCUMENT --------
                with col2:
                    if e.get("more_details"):
                        st.link_button(
                            "View Document",
                            f"{BASE_URL}{e['more_details']}"
                        )

                # -------- EDIT TOGGLE --------
                with col3:
                    if st.button("Edit Event", key=f"edit_toggle_{e['id']}"):
                        st.session_state[f"edit_mode_{e['id']}"] = not st.session_state.get(
                            f"edit_mode_{e['id']}", False
                        )

                # -------- DOCUMENT TOGGLE --------
                with col4:
                    if st.button("Update Document", key=f"doc_toggle_{e['id']}"):
                        st.session_state[f"doc_mode_{e['id']}"] = not st.session_state.get(
                            f"doc_mode_{e['id']}", False
                        )

                # =================================================
                # EDIT EVENT SECTION
                # =================================================
                if st.session_state.get(f"edit_mode_{e['id']}", False):

                    st.divider()
                    st.subheader("Update Event Details")

                    new_title = st.text_input("Title", value=e["title"], key=f"title_{e['id']}")
                    new_venue = st.text_input("Venue", value=e["venue"], key=f"venue_{e['id']}")
                    new_date = st.date_input(
                        "Date",
                        value=datetime.strptime(e["date"], "%Y-%m-%d"),
                        key=f"date_{e['id']}"
                    )
                    new_seats = st.number_input(
                        "Seats",
                        value=e["seats"],
                        min_value=1,
                        key=f"seats_{e['id']}"
                    )
                    new_price = st.number_input(
                        "Ticket Price",
                        value=e["ticket_price"],
                        min_value=1,
                        key=f"price_{e['id']}"
                    )

                    if st.button("Save Changes", key=f"save_{e['id']}"):

                        update_data = {
                            "title": new_title,
                            "venue": new_venue,
                            "date": str(new_date),
                            "seats": new_seats,
                            "ticket_price": new_price
                        }

                        upd_res = requests.put(
                            f"{BASE_URL}/host/event/{e['id']}",
                            headers=headers(),
                            json=update_data
                        )

                        if upd_res.status_code == 200:
                            st.success("Event updated")
                            st.session_state[f"edit_mode_{e['id']}"] = False
                            st.rerun()
                        else:
                            st.error(upd_res.text)

                # =================================================
                # UPDATE DOCUMENT SECTION (SEPARATE)
                # =================================================
                if st.session_state.get(f"doc_mode_{e['id']}", False):

                    st.divider()
                    st.subheader("Upload New Document (PDF Only)")

                    new_doc = st.file_uploader(
                        "Select PDF",
                        type=["pdf"],
                        key=f"doc_upload_{e['id']}"
                    )

                    if new_doc:
                        if st.button("Upload Document", key=f"upload_btn_{e['id']}"):

                            files = {
                                "document": (
                                    new_doc.name,
                                    new_doc,
                                    "application/pdf"
                                )
                            }

                            doc_res = requests.put(
                                f"{BASE_URL}/host/event_document/{e['id']}",
                                headers=headers(),
                                files=files
                            )

                            if doc_res.status_code == 200:
                                st.success("Document updated successfully")
                                st.session_state[f"doc_mode_{e['id']}"] = False
                                st.rerun()
                            else:
                                st.error(doc_res.text)

# =================================================
# ADMIN DASHBOARD
# =================================================
def admin_dashboard():

    headers_auth = headers()

    tab = smart_tabs(
        ["Users", "Hosts", "Transactions", "Promotions", "Wallets"],
        key="admin_tab"
    )

    # ================= USERS =================
    if tab == "Users":

        users_res = requests.get(f"{BASE_URL}/admin/users", headers=headers_auth)
        bookings_res = requests.get(f"{BASE_URL}/admin/bookings", headers=headers_auth)
        events_res = requests.get(f"{BASE_URL}/admin/events", headers=headers_auth)

        if users_res.status_code != 200:
            st.error("Failed to fetch users")
            return

        users = users_res.json()
        bookings = bookings_res.json() if bookings_res.status_code == 200 else []
        events = events_res.json() if events_res.status_code == 200 else []

        if not users:
            st.info("No users found")
            return

        for u in users:

            with st.expander(f"{u['username']} — {u['email']}"):

                user_bookings = [
                    b for b in bookings if b["user_username"] == u["username"]
                ]

                if not user_bookings:
                    st.info("No bookings")
                else:
                    for b in user_bookings:

                        st.write(f"Event: {b['event_title']}")
                        st.write(f"Tickets: {b['ticket_count']}")
                        st.write(f"Payment: ₹{b['payment_amount']} ({b['payment_status']})")

                        col1, col2 = st.columns(2)

                        with col1:
                            if st.button("Delete Booking", key=f"admin_del_booking_{b['booking_id']}"):
                                requests.delete(
                                    f"{BASE_URL}/admin/booking/{b['booking_id']}",
                                    headers=headers_auth
                                )
                                st.success("Booking deleted")
                                st.rerun()

                        with col2:
                            event = next(
                                (e for e in events if e["event_id"] == b["event_id"]),
                                None
                            )
                            if event and event.get("more_details"):
                                st.link_button(
                                    "More Details",
                                    f"{BASE_URL}{event['more_details']}"
                                )

                        st.divider()

    # ================= HOSTS =================
    elif tab == "Hosts":

        hosts_res = requests.get(f"{BASE_URL}/admin/hosts", headers=headers_auth)
        events_res = requests.get(f"{BASE_URL}/admin/events", headers=headers_auth)
        bookings_res = requests.get(f"{BASE_URL}/admin/bookings", headers=headers_auth)

        if hosts_res.status_code != 200:
            st.error("Failed to fetch hosts")
            return

        hosts = hosts_res.json()
        events = events_res.json() if events_res.status_code == 200 else []
        bookings = bookings_res.json() if bookings_res.status_code == 200 else []

        if not hosts:
            st.info("No hosts found")
            return

        for h in hosts:

            with st.expander(f"{h['company_name']} — {h['email']}"):

                # Match via email (safer than company name)
                host_events = [
                    e for e in events if e["host_email"] == h["email"]
                ]

                if not host_events:
                    st.info("No events hosted")
                else:
                    for e in host_events:

                        st.subheader(f"{e['title']} — {e['venue']}")
                        st.write(f"Date: {e['date']}")
                        st.write(f"Seats: {e['available_seats']} / {e['total_seats']}")
                        st.write(f"Ticket Price: ₹{e['ticket_price']}")

                        col1, col2 = st.columns(2)

                        with col1:
                            if st.button("Delete Event", key=f"admin_del_event_{e['event_id']}"):
                                requests.delete(
                                    f"{BASE_URL}/admin/event/{e['event_id']}",
                                    headers=headers_auth
                                )
                                st.success("Event deleted")
                                st.rerun()

                        with col2:
                            if e.get("more_details"):
                                st.link_button(
                                    "More Details",
                                    f"{BASE_URL}{e['more_details']}"
                                )

                        event_bookings = [
                            b for b in bookings if b["event_id"] == e["event_id"]
                        ]

                        if event_bookings:
                            st.markdown("**Bookings:**")

                            for b in event_bookings:
                                with st.container(border=True):

                                    col1, col2, col3 = st.columns([3,2,1])

                                    with col1:
                                        st.write(f"👤 {b['user_username']}")
                                        st.write(f"🎟 {b['ticket_count']} tickets")

                                    with col2:
                                        st.write(f"💰 ₹{b['payment_amount']} ({b['payment_status']})")

                                    with col3:
                                        if st.button("Delete", key=f"admin_del_booking_{b['booking_id']}"):
                                            requests.delete(
                                                f"{BASE_URL}/admin/booking/{b['booking_id']}",
                                                headers=headers()
                                            )
                                            st.success("Booking deleted & refunded")
                                            st.rerun()

                        st.divider()

    # ================= TRANSACTIONS =================
    elif tab == "Transactions":

        subtab = smart_tabs(
            ["User Transactions", "Host Transactions"],
            key="admin_tx_tab"
        )

        if subtab == "User Transactions":

            res = requests.get(
                f"{BASE_URL}/admin/booking_transactions",
                headers=headers_auth
            )

            if res.status_code != 200:
                st.error("Failed to fetch transactions")
                return

            transactions = res.json()

            if not transactions:
                st.info("No user transactions")
            else:
                for t in transactions:
                    with st.container(border=True):
                        st.subheader(f"Username :  {t['username']}")
                        st.write(f"Booking ID : {t['booking_id']}")
                        st.write(f"Amount : ₹{t['amount']}")
                        st.write(f"Status : {t['status']}")

        else:

            res = requests.get(
                f"{BASE_URL}/admin/host_transactions",
                headers=headers_auth
            )

            if res.status_code != 200:
                st.error("Failed to fetch host transactions")
                return

            transactions = res.json()

            if not transactions:
                st.info("No host transactions")
            else:
                for t in transactions:
                    with st.container(border=True):
                        st.subheader(f"Company Name : {t['company_name']}")
                        st.write(f"Host ID : {t['host_id']}")
                        st.write(f"Amount : ₹{t['amount']}")
                        st.write(f"Status : {t['status']}")

    # ================= PROMOTIONS =================
    elif tab == "Promotions":

        res = requests.get(
            f"{BASE_URL}/admin/promotions",
            headers=headers_auth
        )

        if res.status_code != 200:
            st.error("Failed to fetch promotions")
            return

        promotions = res.json()

        if not promotions:
            st.info("No promotions found")
        else:
            for p in promotions:
                with st.container(border=True):
                    st.subheader(p["company_name"] or "N/A")
                    st.write(f"Email: {p['email']}")
                    st.write(f"Amount: ₹{p['amount']}")
                    st.write(f"Status: {p['status']}")

    # ================= WALLETS =================
    elif tab == "Wallets":

        res = requests.get(
            f"{BASE_URL}/admin/wallets",
            headers=headers_auth
        )

        if res.status_code != 200:
            st.error("Failed to fetch wallets")
            return

        wallets = res.json()

        if not wallets:
            st.info("No wallets found")
        else:
            for w in wallets:
                with st.container(border=True):
                    st.subheader(f"{w['owner_type'].upper()} — ID {w['owner_id']}")
                    st.write(f"Balance: ₹{w['balance']}")

                    
# =================================================
# ROUTER
# =================================================
if role == "user":
    user_dashboard()

elif role == "host":
    host_dashboard()

elif role == "admin":
    admin_dashboard()

