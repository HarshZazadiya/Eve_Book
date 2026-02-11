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

