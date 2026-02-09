# import streamlit as st
# import requests
# import os

# BASE_URL = "http://localhost:8000"

# st.set_page_config(page_title="Event Booking Platform", layout="wide")

# # ---------------- SESSION ----------------
# if "token" not in st.session_state:
#     st.session_state.token = None

# if "role" not in st.session_state:
#     st.session_state.role = None


# # ---------------- HELPERS ----------------
# def headers():
#     return {"Authorization": f"Bearer {st.session_state.token}"}


# def login(username, password):
#     return requests.post(
#         f"{BASE_URL}/auth/token",
#         data={"username": username, "password": password}
#     )


# def detect_role():
#     r = requests.get(f"{BASE_URL}/auth/me", headers=headers())
#     data = r.json()

#     if data.get("role") == "admin":
#         return "admin"

#     return data.get("type")


# # ---------------- WALLET ----------------
# def wallet_ui():

#     st.header("💰 Wallet")

#     r = requests.get(f"{BASE_URL}/myWallet", headers=headers())

#     if r.status_code == 200:
#         data = r.json()
#         balance = data.get("balance") or data.get("wallet_balance") or 0
#         st.metric("Current Balance", f"₹ {balance}")

#     amount = st.number_input("Top Up Amount", min_value=1, key="wallet_amount")

#     if st.button("Add Money"):
#         requests.post(
#             f"{BASE_URL}/topUp",
#             headers=headers(),
#             json={"amount": amount}
#         )
#         st.success("Wallet Updated")
#         st.rerun()


# # =================================================
# # AUTH UI
# # =================================================
# if not st.session_state.token:

#     st.title("🎟 Event Booking Platform")

#     tab1, tab2 = st.tabs(["Login", "Register"])

#     # ---------- LOGIN ----------
#     with tab1:

#         st.info(
#             "👉 Use USERNAME to login as User\n\n"
#             "👉 Use EMAIL to login as Host"
#         )

#         username = st.text_input("Username / Email", key="login_user")
#         password = st.text_input("Password", type="password", key="login_pass")

#         if st.button("Login"):

#             res = login(username, password)

#             if res.status_code == 200:
#                 st.session_state.token = res.json()["access_token"]
#                 st.session_state.role = detect_role()
#                 st.rerun()
#             else:
#                 st.error("Invalid credentials")

#     # ---------- REGISTER ----------
#     with tab2:

#         role = st.radio("Register As", ["User", "Host"], key="register_role")

#         if role == "User":

#             st.subheader("User Registration")

#             username = st.text_input("Username", key="reg_user_username")
#             email = st.text_input("Email", key="reg_user_email")
#             password = st.text_input("Password", type="password", key="reg_user_password")

#             if st.button("Register User"):

#                 r = requests.post(
#                     f"{BASE_URL}/auth/user",
#                     json={
#                         "username": username,
#                         "email": email,
#                         "password": password
#                     }
#                 )

#                 if r.status_code == 201:
#                     st.success("User Registered Successfully")
#                 else:
#                     st.error(r.text)

#         else:

#             st.subheader("Host Registration")

#             company = st.text_input("Company Name", key="reg_host_company")
#             email = st.text_input("Email", key="reg_host_email")
#             password = st.text_input("Password", type="password", key="reg_host_password")

#             if st.button("Register Host"):

#                 r = requests.post(
#                     f"{BASE_URL}/auth/host",
#                     json={
#                         "company_name": company,
#                         "email": email,
#                         "password": password
#                     }
#                 )

#                 if r.status_code == 201:
#                     st.success("Host Registered Successfully")
#                 else:
#                     st.error(r.text)

#     st.stop()


# role = st.session_state.role


# # ---------------- SIDEBAR ----------------
# st.sidebar.title(f"Role : {role.upper()}")

# if st.sidebar.button("Logout"):
#     st.session_state.token = None
#     st.session_state.role = None
#     st.rerun()


# # =================================================
# # USER DASHBOARD
# # =================================================
# def user_dashboard():

#     menu = st.sidebar.radio(
#         "User Menu",
#         ["Wallet", "Browse Events", "My Bookings", "Promote To Host"]
#     )

#     if menu == "Wallet":
#         wallet_ui()

#     if menu == "Browse Events":

#         st.header("🎉 Available Events")

#         res = requests.get(f"{BASE_URL}/user/events", headers=headers())

#         if res.status_code == 200:

#             events = sorted(res.json(), key=lambda x: x["id"], reverse=True)

#             for e in events:

#                 with st.container(border=True):

#                     st.subheader(f"Event #{e['id']} - {e['title']}")

#                     c1, c2, c3, c4 = st.columns(4)

#                     c1.write(f"📅 {e['date']}")
#                     c2.write(f"🎟 Seats: {e['available_seats']}")
#                     c3.write(f"💰 Price: ₹{e['ticket_price']}")
#                     c4.write(f"🏢 Host ID: {e['host_id']}")

#                     if st.button("Book Ticket", key=f"book_{e['id']}"):
#                         requests.post(
#                             f"{BASE_URL}/user/event/{e['id']}",
#                             headers=headers()
#                         )
#                         st.success("Booking Successful")
#                         st.rerun()

#     if menu == "My Bookings":
#         st.header("📘 My Bookings")

#         res = requests.get(f"{BASE_URL}/user/myEvents", headers=headers())

#         if res.status_code != 200:
#             st.error("Failed to fetch bookings")
#             return

#         bookings = sorted(res.json(), key=lambda x: x["booking_id"], reverse=True)

#         if not bookings:
#             st.info("No bookings found")
#             return

#         for b in bookings:

#             with st.container(border=True):

#                 st.subheader(f"Booking #{b['booking_id']}")
#                 st.write(f"Event ID: {b['event_id']}")
#                 st.write(f"Tickets: {b['ticket_count']}")

#                 # ✅ FIX → cancel using booking_id not event_id
#                 if st.button("Cancel Booking", key=f"cancel_{b['booking_id']}"):

#                     res = requests.delete(
#                         f"{BASE_URL}/user/booking/{b['booking_id']}",
#                         headers=headers()
#                     )

#                     if res.status_code == 200:
#                         st.success("Booking Cancelled")
#                         st.rerun()
#                     else:
#                         st.error(res.text)


#     if menu == "Promote To Host":

#         st.header("🚀 Become Host")

#         if st.button("Pay 10000 & Promote"):
#             requests.post(f"{BASE_URL}/user/promote-to-host", headers=headers())
#             st.success("You are now a Host")
#             st.rerun()


# # =================================================
# # HOST DASHBOARD
# # =================================================
# def host_dashboard():

#     menu = st.sidebar.radio(
#         "Host Menu",
#         ["Wallet", "Create Event", "My Events"]
#     )

#     if menu == "Wallet":
#         wallet_ui()

#     if menu == "Create Event":

#         st.header("➕ Create Event")

#         title = st.text_input("Title", key="host_title")
#         venue = st.text_input("Venue", key="host_venue")
#         date = st.date_input("Date", key="host_date")
#         seats = st.number_input("Seats", min_value=1, key="host_seats")
#         price = st.number_input("Ticket Price", min_value=1, key="host_price")

#         if st.button("Create Event"):

#             requests.post(
#                 f"{BASE_URL}/host/event",
#                 headers=headers(),
#                 json={
#                     "title": title,
#                     "venue": venue,
#                     "date": str(date),
#                     "seats": seats,
#                     "ticket_price": price
#                 }
#             )

#             st.success("Event Created")
#             st.rerun()

#     if menu == "My Events":

#         st.header("📅 Hosted Events")

#         events = requests.get(f"{BASE_URL}/host/events", headers=headers()).json()
#         events = sorted(events, key=lambda x: x["id"], reverse=True)

#         for e in events:

#             with st.container(border=True):

#                 st.subheader(f"Event #{e['id']} - {e['title']}")
#                 st.write(f"📍 {e['venue']}")
#                 st.write(f"📅 {e['date']}")
#                 st.write(f"Seats Left: {e['available_seats']}")

#                 if st.button("Delete", key=f"del_{e['id']}"):
#                     requests.delete(
#                         f"{BASE_URL}/host/event/{e['id']}",
#                         headers=headers()
#                     )
#                     st.success("Event Deleted")
#                     st.rerun()

# # =================================================
# # ADMIN DASHBOARD
# # =================================================
# def admin_dashboard():

#     menu = st.sidebar.radio(
#         "Admin Menu",
#         ["Users", "Hosts", "All Events", "All Bookings"]
#     )

#     # =================================================
#     # USERS
#     # =================================================
#     if menu == "Users":

#         st.header("👥 Users")

#         res = requests.get(f"{BASE_URL}/admin/users", headers=headers())

#         if res.status_code != 200:
#             st.error(res.text)
#             return

#         users = sorted(res.json(), key=lambda x: x["username"].lower())

#         for u in users:

#             with st.container(border=True):

#                 col1, col2 = st.columns([3, 1])

#                 with col1:
#                     st.subheader(f"👤 {u['username']}")
#                     st.write(f"📧 {u['email']}")
#                     st.write(f"🏷 Role: {u['role']}")

#                 with col2:
#                     st.metric("User ID", u["id"])

#     # =================================================
#     # HOSTS
#     # =================================================
#     if menu == "Hosts":

#         st.header("🏢 Hosts")

#         res = requests.get(f"{BASE_URL}/admin/hosts", headers=headers())

#         if res.status_code != 200:
#             st.error(res.text)
#             return

#         hosts = sorted(res.json(), key=lambda x: x["company_name"].lower())

#         for h in hosts:

#             with st.container(border=True):

#                 st.subheader(f"🏢 {h['company_name']}")
#                 st.write(f"📧 {h['email']}")
#                 st.caption(f"Host ID: {h['id']}")

#                 if st.button("⬇ Demote Host", key=f"demote_{h['id']}"):

#                     res = requests.post(
#                         f"{BASE_URL}/admin/demote-host/{h['id']}",
#                         headers=headers()
#                     )

#                     if res.status_code == 200:
#                         st.success("Host Demoted")
#                         st.rerun()
#                     else:
#                         st.error(res.text)

#     # =================================================
#     # EVENTS
#     # =================================================
#     if menu == "All Events":

#         st.header("🎉 All Events")

#         events_res = requests.get(f"{BASE_URL}/admin/events", headers=headers())
#         bookings_res = requests.get(f"{BASE_URL}/admin/bookings", headers=headers())

#         if events_res.status_code != 200:
#             st.error(events_res.text)
#             return

#         events = sorted(events_res.json(), key=lambda x: x["event_id"], reverse=True)
#         bookings = bookings_res.json() if bookings_res.status_code == 200 else []

#         for e in events:

#             with st.container(border=True):

#                 st.subheader(f"Event #{e['event_id']} — {e['title']}")

#                 c1, c2, c3, c4 = st.columns(4)

#                 c1.write(f"📍 {e['venue']}")
#                 c2.write(f"📅 {e['date']}")
#                 c3.write(f"🎟 {e['available_seats']} / {e['total_seats']}")
#                 c4.write(f"💰 ₹{e['ticket_price']}")

#                 st.caption(f"Host: {e['host_company']} ({e['host_email']})")

#                 # ---------- DELETE EVENT ----------
#                 if st.button("🗑 Delete Entire Event", key=f"delete_event_{e['event_id']}"):

#                     res = requests.delete(
#                         f"{BASE_URL}/admin/event/{e['event_id']}",
#                         headers=headers()
#                     )

#                     if res.status_code == 200:
#                         st.success("Event Deleted")
#                         st.rerun()
#                     else:
#                         st.error(res.text)

#                 # ---------- BOOKINGS INSIDE EVENT ----------
#                 st.divider()
#                 st.markdown("### 📘 Bookings For This Event")

#                 event_bookings = [b for b in bookings if b["event_id"] == e["event_id"]]

#                 if not event_bookings:
#                     st.info("No bookings yet")
#                 else:

#                     for b in event_bookings:

#                         with st.container(border=True):

#                             st.write(f"Booking #{b['booking_id']}")
#                             st.write(f"👤 {b['user_username']} ({b['user_email']})")
#                             st.write(f"🎟 Tickets: {b['ticket_count']}")
#                             st.write(f"💰 ₹{b['payment_amount']}")

#                             if st.button(
#                                 "❌ Delete Booking",
#                                 key=f"event_booking_delete_{b['booking_id']}"
#                             ):

#                                 res = requests.delete(
#                                     f"{BASE_URL}/admin/booking/{b['booking_id']}",
#                                     headers=headers()
#                                 )

#                                 if res.status_code == 200:
#                                     st.success("Booking Deleted")
#                                     st.rerun()
#                                 else:
#                                     st.error(res.text)

#     # =================================================
#     # ALL BOOKINGS
#     # =================================================
#     if menu == "All Bookings":

#         st.header("📘 All Bookings")

#         res = requests.get(f"{BASE_URL}/admin/bookings", headers=headers())

#         if res.status_code != 200:
#             st.error(res.text)
#             return

#         bookings = sorted(res.json(), key=lambda x: x["booking_id"], reverse=True)

#         for b in bookings:

#             with st.container(border=True):

#                 st.subheader(f"Booking #{b['booking_id']}")

#                 col1, col2 = st.columns([3, 1])

#                 with col1:
#                     st.write(f"👤 {b['user_username']} ({b['user_email']})")
#                     st.write(f"🎉 Event #{b['event_id']} — {b['event_title']}")
#                     st.write(f"🎟 Tickets: {b['ticket_count']}")
#                     st.write(f"💰 ₹{b['payment_amount']} ({b['payment_status']})")

#                 with col2:
#                     if st.button("🗑 Delete", key=f"delete_booking_{b['booking_id']}"):

#                         res = requests.delete(
#                             f"{BASE_URL}/admin/booking/{b['booking_id']}",
#                             headers=headers()
#                         )

#                         if res.status_code == 200:
#                             st.success("Booking Deleted")
#                             st.rerun()
#                         else:
#                             st.error(res.text)

# # =================================================
# # ROUTER
# # =================================================
# if role == "user":
#     user_dashboard()

# elif role == "host":
#     host_dashboard()

# elif role == "admin":
#     admin_dashboard()






















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
def host_dashboard():

    menu = smart_tabs(
        ["Wallet", "Create Event", "My Events"],
        key="host_tab"
    )

    if menu == "Wallet":
        wallet_ui()

    if menu == "Create Event":

        title = st.text_input("Title")
        venue = st.text_input("Venue")
        date = st.date_input("Date")
        seats = st.number_input("Seats", min_value=1)
        price = st.number_input("Ticket Price", min_value=1)

        if st.button("Create Event"):
            requests.post(
                f"{BASE_URL}/host/event",
                headers=headers(),
                json={
                    "title": title,
                    "venue": venue,
                    "date": str(date),
                    "seats": seats,
                    "ticket_price": price
                }
            )
            st.success("Created")
            st.rerun()

    if menu == "My Events":

        events = requests.get(f"{BASE_URL}/host/events", headers=headers()).json()

        for e in events:

            with st.container(border=True):

                st.subheader(e["title"])
                st.write(e["venue"])
                st.write(e["date"])

                if st.button("Delete", key=f"del_{e['id']}"):
                    requests.delete(
                        f"{BASE_URL}/host/event/{e['id']}",
                        headers=headers()
                    )
                    st.success("Deleted")
                    st.rerun()


# =================================================
# ADMIN DASHBOARD
# =================================================
def admin_dashboard():

    menu = smart_tabs(
        ["Users", "Hosts", "Events", "Bookings", "Wallets"],
        key="admin_tab"
    )

    # USERS
    if menu == "Users":

        users = requests.get(f"{BASE_URL}/admin/users", headers=headers()).json()

        for u in users:
            with st.container(border=True):
                st.subheader(u["username"])
                st.write(u["email"])
                st.caption(u["role"])

    # HOSTS
    if menu == "Hosts":

        hosts = requests.get(f"{BASE_URL}/admin/hosts", headers=headers()).json()

        for h in hosts:
            with st.container(border=True):

                st.subheader(h["company_name"])
                st.write(h["email"])

                if st.button("Demote", key=f"demote_{h['id']}"):
                    requests.post(
                        f"{BASE_URL}/admin/demote-host/{h['id']}",
                        headers=headers()
                    )
                    st.success("Demoted")
                    st.rerun()

    # EVENTS
    if menu == "Events":

        events = requests.get(f"{BASE_URL}/admin/events", headers=headers()).json()
        bookings = requests.get(f"{BASE_URL}/admin/bookings", headers=headers()).json()

        for e in events:

            with st.expander(f"{e['title']} — {e['venue']}"):

                st.write(f"📅 {e['date']}")
                st.write(f"Seats : {e['available_seats']} / {e['total_seats']}")

                if st.button("Delete Event", key=f"admin_del_{e['event_id']}"):
                    requests.delete(
                        f"{BASE_URL}/admin/event/{e['event_id']}",
                        headers=headers()
                    )
                    st.rerun()

                st.markdown("### Bookings")

                event_bookings = [b for b in bookings if b["event_id"] == e["event_id"]]

                if not event_bookings:
                    st.info("No bookings")

                for b in event_bookings:

                    col1, col2 = st.columns([3, 1])

                    with col1:
                        st.write(f"{b['user_username']} — {b['ticket_count']} tickets")

                    with col2:
                        if st.button("Delete", key=f"bk_del_{b['booking_id']}"):
                            requests.delete(
                                f"{BASE_URL}/admin/booking/{b['booking_id']}",
                                headers=headers()
                            )
                            st.rerun()

    # BOOKINGS
    if menu == "Bookings":

        bookings = requests.get(f"{BASE_URL}/admin/bookings", headers=headers()).json()

        for b in bookings:

            with st.container(border=True):

                st.subheader(f"Booking #{b['booking_id']}")
                st.write(f"{b['user_username']} → {b['event_title']}")
                st.write(f"₹ {b['payment_amount']}")

                if st.button("Delete", key=f"booking_del_{b['booking_id']}"):
                    requests.delete(
                        f"{BASE_URL}/admin/booking/{b['booking_id']}",
                        headers=headers()
                    )
                    st.rerun()

    # WALLETS
    if menu == "Wallets":

        wallets = requests.get(f"{BASE_URL}/admin/wallets", headers=headers()).json()

        for w in wallets:

            with st.container(border=True):

                col1, col2 = st.columns([4, 1])

                with col1:
                    if w["owner_type"] == "user":
                        st.subheader(w["username"])
                    else:
                        st.subheader(w["company_name"])

                    st.write(w["email"])
                    st.caption(f"{w['owner_type']} ID : {w['owner_id']}")

                with col2:
                    st.metric("Balance", f"₹ {w['balance']}")


# =================================================
# ROUTER
# =================================================
if role == "user":
    user_dashboard()

elif role == "host":
    host_dashboard()

elif role == "admin":
    admin_dashboard()
