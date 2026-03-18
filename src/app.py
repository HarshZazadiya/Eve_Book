import logging
logging.getLogger("streamlit").setLevel(logging.ERROR)
from datetime import datetime
import streamlit as st
import requests

BASE_URL = "http://localhost:8000"

st.set_page_config(
    page_title="EveBook · AI Event Platform", 
    page_icon="🎟️", 
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for modern, clean design
st.markdown("""
<style>
    /* ── Kill the purple gradient, use clean neutral dark ── */
    .stApp {
        background: #0f1117 !important;
    }
    .main .block-container {
        background: #0f1117 !important;
        border-radius: 0 !important;
        box-shadow: none !important;
        padding: 1.5rem 2rem !important;
        margin: 0 !important;
        max-width: 100% !important;
    }

    /* ── Text colours ── */
    html, body, [class*="css"], p, span, label, div {
        color: #e2e8f0 !important;
    }
    h1, h2, h3, h4 { color: #f1f5f9 !important; }

    /* ── Sidebar ── */
    section[data-testid="stSidebar"] {
        background: #1a1d2e !important;
        border-right: 1px solid #2d3148 !important;
    }
    section[data-testid="stSidebar"] * { color: #cbd5e1 !important; }

    /* ── Cards / containers ── */
    [data-testid="stExpander"],
    div[data-testid="stVerticalBlock"] > div > [data-testid="stVerticalBlock"] {
        background: #161b2e !important;
        border: 1px solid #2d3148 !important;
        border-radius: 12px !important;
    }

    /* ── Buttons ── */
    .stButton > button {
        border-radius: 10px !important;
        font-weight: 500 !important;
        transition: all 0.15s !important;
    }
    .stButton > button[kind="primary"] {
        background: #3b5bdb !important;
        color: #fff !important;
        border: none !important;
    }
    .stButton > button[kind="primary"]:hover {
        background: #4c6ef5 !important;
        transform: translateY(-1px) !important;
    }
    .stButton > button[kind="secondary"] {
        background: #1e2235 !important;
        color: #94a3b8 !important;
        border: 1px solid #2d3148 !important;
    }
    .stButton > button[kind="secondary"]:hover {
        background: #252a40 !important;
        color: #e2e8f0 !important;
    }

    /* ── Chat messages ── */
    .stChatMessage {
        background: #161b2e !important;
        border: 1px solid #2d3148 !important;
        border-radius: 14px !important;
        margin: 0.4rem 0 !important;
    }
    .stChatMessage p, .stChatMessage span, .stChatMessage li { color: #e2e8f0 !important; }

    /* ── Status widget ── */
    [data-testid="stStatusWidget"],
    div[data-testid="stStatus"] {
        background: #1a2035 !important;
        border: 1px solid #2d3c5e !important;
        border-radius: 10px !important;
    }
    [data-testid="stStatusWidget"] p,
    [data-testid="stStatusWidget"] span { color: #94a3b8 !important; }

    /* ── Chat input ── */
    [data-testid="stChatInputContainer"] {
        background: #161b2e !important;
        border: 1px solid #2d3148 !important;
        border-radius: 14px !important;
    }
    [data-testid="stChatInputContainer"]:focus-within {
        border-color: #3b5bdb !important;
        box-shadow: 0 0 0 3px rgba(59,91,219,.15) !important;
    }
    [data-testid="stChatInput"] textarea {
        background: transparent !important;
        color: #e2e8f0 !important;
        border: none !important;
    }
    [data-testid="stChatInput"] textarea::placeholder { color: #4a5568 !important; }

    /* ── Inputs ── */
    .stTextInput > div > div > input {
        background: #1a1d2e !important;
        border: 1px solid #2d3148 !important;
        border-radius: 10px !important;
    }

    /* ── Metrics ── */
    [data-testid="stMetricValue"] { color: #f1f5f9 !important; }
    [data-testid="stMetricLabel"] { color: #94a3b8 !important; }

    /* ── Dividers ── */
    hr { border-color: #2d3148 !important; }

    /* ── Alerts ── */
    .stAlert { border-radius: 10px !important; }

    /* ── Popover ── */
    [data-testid="stPopover"] { background: #1a1d2e !important; }

    /* ── Select / radio ── */
    .stRadio label { color: #cbd5e1 !important; }

    /* ── Expander header ── */
    [data-testid="stExpander"] summary { color: #94a3b8 !important; }

    /* ── Hide default chrome ── */
    #MainMenu, footer { visibility: hidden; }
</style>
""", unsafe_allow_html=True)

# =================================================
# CHAT INTERFACE — clean Streamlit-native UI
# =================================================

def chat_interface():
    """Chat interface with HITL approval + live tool-call status"""

    # ── session state ─────────────────────────────────────────
    defaults = {
        "current_thread_id":   None,
        "messages":            [],
        "hitl_pending":        False,
        "hitl_last_message":   None,
        "hitl_tools":          [],
        "thread_names":        {},   # thread_id → custom title (local cache)
        "renaming_thread":     None, # thread_id currently being renamed
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

    auth_headers = {"Authorization": f"Bearer {st.session_state.token}"}

    # ── sidebar — thread list ─────────────────────────────────
    with st.sidebar:
        st.markdown("""
        <div style='text-align: center; margin-bottom: 2rem;'>
            <div style='font-size: 2.5rem; margin-bottom: 0.5rem;'>✨</div>
            <div style='font-weight: 600; font-size: 1.2rem; color: white;'>EveBook AI</div>
            <div style='color: #94a3b8; font-size: 0.8rem;'>Your intelligent assistant</div>
        </div>
        """, unsafe_allow_html=True)

        if st.button("＋ New conversation", use_container_width=True, type="primary"):
            st.session_state.current_thread_id = None
            st.session_state.messages          = []
            st.session_state.hitl_pending      = False
            st.session_state.hitl_last_message = None
            st.session_state.hitl_tools        = []
            st.rerun()

        st.markdown("<hr style='margin: 1rem 0; opacity: 0.2;'>", unsafe_allow_html=True)

        try:
            tr = requests.get(f"{BASE_URL}/chat/threads", headers=auth_headers, timeout=5)
            if tr.status_code == 200:
                threads = tr.json()
                
                if not threads:
                    st.markdown("""
                    <div style='text-align: center; color: #94a3b8; padding: 2rem 0;'>
                        <div style='font-size: 2rem; margin-bottom: 0.5rem;'>💭</div>
                        <div>No conversations yet</div>
                    </div>
                    """, unsafe_allow_html=True)
                
                for thread in threads:
                    active       = thread["id"] == st.session_state.current_thread_id
                    tid_key      = thread["id"]

                    # Title priority: local rename cache → server thread_name → message preview
                    if tid_key in st.session_state.thread_names:
                        display_name = st.session_state.thread_names[tid_key]
                    elif thread.get("thread_name") and thread["thread_name"] != "New Chat":
                        display_name = thread["thread_name"]
                        st.session_state.thread_names[tid_key] = thread["thread_name"]
                    else:
                        preview_text = thread.get("last_message") or "New Chat"
                        display_name = preview_text[:32] + "…" if len(preview_text) > 32 else preview_text

                    # ── rename mode: show text input inline ──
                    if st.session_state.renaming_thread == tid_key:
                        st.markdown(f"<div style='margin-bottom: 0.5rem; color: white; font-size: 0.9rem;'>Rename thread</div>", unsafe_allow_html=True)
                        new_name = st.text_input(
                            "",
                            value=display_name,
                            key=f"rename_input_{tid_key}",
                            label_visibility="collapsed",
                            placeholder="Enter new name…"
                        )
                        rc1, rc2 = st.columns([1, 1])
                        with rc1:
                            if st.button("✓ Save", key=f"save_{tid_key}", use_container_width=True, type="primary"):
                                if new_name.strip():
                                    st.session_state.thread_names[tid_key] = new_name.strip()
                                    try:
                                        requests.patch(
                                            f"{BASE_URL}/chat/threads/{tid_key}/rename",
                                            headers=auth_headers,
                                            json={"thread_name": new_name.strip()},
                                            timeout=5
                                        )
                                    except Exception:
                                        pass
                                st.session_state.renaming_thread = None
                                st.rerun()
                        with rc2:
                            if st.button("✕ Cancel", key=f"cancel_rename_{tid_key}", use_container_width=True):
                                st.session_state.renaming_thread = None
                                st.rerun()
                        continue

                    # ── normal row ──
                    with st.container():
                        col1, col2, col3 = st.columns([5, 1, 1])
                        with col1:
                            btn_type = "primary" if active else "secondary"
                            icon = "🟢" if active else "💬"
                            if st.button(
                                f"{icon}  {display_name}",
                                key=f"t_{tid_key}",
                                use_container_width=True,
                                type=btn_type,
                            ):
                                st.session_state.current_thread_id = tid_key
                                st.session_state.hitl_pending      = False
                                msgs_r = requests.get(
                                    f"{BASE_URL}/chat/threads/{tid_key}/messages",
                                    headers=auth_headers)
                                st.session_state.messages = msgs_r.json() if msgs_r.status_code == 200 else []
                                st.rerun()
                        with col2:
                            if st.button("✏️", key=f"ren_{tid_key}", help="Rename"):
                                st.session_state.renaming_thread = tid_key
                                st.rerun()
                        with col3:
                            if st.button("🗑", key=f"d_{tid_key}", help="Delete"):
                                requests.delete(
                                    f"{BASE_URL}/chat/threads/{tid_key}",
                                    headers=auth_headers)
                                if st.session_state.current_thread_id == tid_key:
                                    st.session_state.current_thread_id = None
                                    st.session_state.messages          = []
                                    st.session_state.hitl_pending      = False
                                st.session_state.thread_names.pop(tid_key, None)
                                st.rerun()
        except Exception as e:
            st.error(f"Could not load threads: {e}")

    # ── main area header ──────────────────────────────────────
    tid = st.session_state.current_thread_id
    if tid and tid in st.session_state.thread_names:
        sub = st.session_state.thread_names[tid]
    elif tid:
        sub = f"Thread #{tid}"
    else:
        sub = "Start a new conversation"
    
    st.markdown(f"""
    <div style='display: flex; align-items: center; gap: 0.5rem; margin-bottom: 1rem;'>
        <div style='background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
                    width: 40px; height: 40px; border-radius: 12px; 
                    display: flex; align-items: center; justify-content: center;
                    color: white; font-size: 1.2rem;'>
            💬
        </div>
        <div>
            <div style='font-size: 1.5rem; font-weight: 600; color: var(--dark);'>AI Assistant</div>
            <div style='color: var(--gray); font-size: 0.9rem;'>{sub}</div>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    st.markdown("<hr style='margin: 1rem 0;'>", unsafe_allow_html=True)

    # ── message history ───────────────────────────────────────
    msgs = st.session_state.messages
    if not msgs and not st.session_state.hitl_pending:
        st.markdown("""
        <div style='text-align: center; padding: 4rem 2rem;'>
            <div style='font-size: 4rem; margin-bottom: 1rem; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                        -webkit-background-clip: text; -webkit-text-fill-color: transparent;'>
                ✨
            </div>
            <div style='font-size: 1.5rem; font-weight: 500; color: var(--dark); margin-bottom: 0.5rem;'>
                How can I help you today?
            </div>
            <div style='color: var(--black);'>
                Ask me about events, bookings, wallets, files, and more
            </div>
            <div style='display: flex; gap: 0.5rem; justify-content: center; margin-top: 2rem;'>
                <span style='background: #f1f5f9; padding: 0.25rem 1rem; border-radius: 20px; color: var(--black);'>🎟️ Browse events</span>
                <span style='background: #f1f5f9; padding: 0.25rem 1rem; border-radius: 20px; color: var(--black);'>💰 Check wallet</span>
                <span style='background: #f1f5f9; padding: 0.25rem 1rem; border-radius: 20px; color: var(--black);'>📅 My bookings</span>
            </div>
        </div>
        """, unsafe_allow_html=True)
    else:
        for msg in msgs:
            role    = msg.get("role", "user")
            content = msg.get("content", "")
            with st.chat_message(role):
                st.markdown(content)

    # ── HITL approval ─────────────────────────────────────────
    if st.session_state.hitl_pending:
        tools_str = "  ".join(f"`{t}`" for t in st.session_state.hitl_tools)

        with st.chat_message("assistant"):
            with st.status("⏳ Waiting for your approval…", expanded=True) as status:
                # Show what tool wants to run + its args
                st.write(f"⚠️ The assistant wants to run: {tools_str}")

                col_yes, col_no, _ = st.columns([1, 1, 4])
                approved = None
                with col_yes:
                    if st.button("✅ Yes, proceed", use_container_width=True, type="primary",
                                 key="hitl_yes"):
                        approved = "yes"
                with col_no:
                    if st.button("❌ No, cancel", use_container_width=True,
                                 key="hitl_no"):
                        approved = "no"

                if approved is not None:
                    # Update status to show running
                    if approved == "yes":
                        status.update(label="⚙️ Executing…", state="running", expanded=True)
                    else:
                        status.update(label="🚫 Cancelled", state="complete", expanded=False)

                    if approved == "yes":
                        try:
                            resp = requests.post(
                                f"{BASE_URL}/chat/ask", headers=auth_headers,
                                json={
                                    "message":        st.session_state.hitl_last_message,
                                    "thread_id":      st.session_state.current_thread_id,
                                    "human_approval": approved,
                                },
                                timeout=60)
                            if resp.status_code == 200:
                                data       = resp.json()
                                tools_used = data.get("tools_used") or []
                                for tc in tools_used:
                                    st.write(f"🔧 `{tc.get('name','?')}` completed")
                                status.update(
                                    label=f"✅ Done — {', '.join(tc.get('name','?') for tc in tools_used) if tools_used else 'complete'}",
                                    state="complete", expanded=False)
                                st.session_state.current_thread_id = data["thread_id"]
                                st.session_state["_hitl_response"]  = data.get("response", "")
                            else:
                                status.update(label="Error", state="error", expanded=True)
                                st.error(f"HTTP {resp.status_code}: {resp.text}")
                        except Exception as e:
                            status.update(label="Error", state="error", expanded=True)
                            st.error(str(e))
                    else:
                        # Denied — ask backend to resume with "no"
                        try:
                            resp = requests.post(
                                f"{BASE_URL}/chat/ask", headers=auth_headers,
                                json={
                                    "message":        st.session_state.hitl_last_message,
                                    "thread_id":      st.session_state.current_thread_id,
                                    "human_approval": "no",
                                },
                                timeout=60)
                            if resp.status_code == 200:
                                data = resp.json()
                                st.session_state.current_thread_id = data["thread_id"]
                                st.session_state["_hitl_response"]  = data.get("response", "")
                        except Exception:
                            st.session_state["_hitl_response"] = "Action cancelled."

                    st.session_state.hitl_pending      = False
                    st.session_state.hitl_last_message = None
                    st.session_state.hitl_tools        = []

            # ── Answer printed BELOW the status widget ──
            hitl_reply = st.session_state.pop("_hitl_response", None)
            if hitl_reply:
                st.markdown(hitl_reply)
                st.session_state.messages.append({"role": "assistant", "content": hitl_reply})

        if not st.session_state.hitl_pending:
            st.rerun()
        return  # hide input while waiting

    # ── chat input ────────────────────────────────────────────
    if prompt := st.chat_input("Ask about events, files, wallets…"):
        with st.chat_message("user"):
            st.markdown(prompt)
        st.session_state.messages.append({"role": "user", "content": prompt})

        with st.chat_message("assistant"):
            # Status widget — shows tools while waiting, collapses after
            with st.status("Working…", expanded=True) as status:
                try:
                    resp = requests.post(
                        f"{BASE_URL}/chat/ask", headers=auth_headers,
                        json={
                            "message":   prompt,
                            "thread_id": st.session_state.current_thread_id,
                        },
                        timeout=60)

                    if resp.status_code == 200:
                        data       = resp.json()
                        tools_used = data.get("tools_used") or []
                        ai_text    = data.get("response", "")

                        # Show only tools called for THIS query
                        for tc in tools_used:
                            name = tc.get("name", "unknown")
                            args = tc.get("args", {})
                            hint = next(iter(args.values()), "") if args else ""
                            hint_str = f" · `{str(hint)[:45]}`" if hint else ""
                            st.write(f"🔧 `{name}`{hint_str}")

                        if data.get("hitl_required"):
                            status.update(label="⏳ Waiting for your approval…",
                                          state="running", expanded=False)
                            st.session_state.hitl_pending      = True
                            st.session_state.hitl_last_message = prompt
                            st.session_state.hitl_tools        = data.get("hitl_tools") or []
                            st.session_state.current_thread_id = data["thread_id"]
                            st.session_state.messages.append(
                                {"role": "assistant", "content": ai_text})
                            st.rerun()
                        else:
                            if tools_used:
                                names = ", ".join(tc.get("name","?") for tc in tools_used)
                                status.update(
                                    label=f"✅ Used {len(tools_used)} tool{'s' if len(tools_used)>1 else ''} — {names}",
                                    state="complete", expanded=False)
                            else:
                                status.update(label="✅ Done", state="complete", expanded=False)

                        st.session_state.current_thread_id = data["thread_id"]
                        # Store response to render OUTSIDE the status block
                        st.session_state["_pending_response"] = ai_text
                        st.session_state.messages.append(
                            {"role": "assistant", "content": ai_text})

                    else:
                        status.update(label="Error", state="error", expanded=True)
                        st.error(f"HTTP {resp.status_code}: {resp.text}")
                        st.session_state["_pending_response"] = None

                except requests.exceptions.Timeout:
                    status.update(label="Timed out", state="error", expanded=True)
                    st.error("⏱️ Request timed out")
                    st.session_state["_pending_response"] = None
                except Exception as e:
                    status.update(label="Error", state="error", expanded=True)
                    st.error(str(e))
                    st.session_state["_pending_response"] = None

            # ── Answer printed HERE — outside/below the status widget ──
            ai_text = st.session_state.pop("_pending_response", None)
            if ai_text:
                st.markdown(ai_text)


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
    return data.get("type") or data.get("role") or "user"

# ---------------- SMART TABS ----------------
def smart_tabs(tab_list, key="tab"):
    if key not in st.session_state:
        st.session_state[key] = tab_list[0]
    
    selected = st.radio(
        "Navigation",
        tab_list, 
        horizontal=True,
        label_visibility="collapsed"
    )
    
    if selected != st.session_state[key]:
        st.session_state[key] = selected
        st.rerun()
    
    return st.session_state[key]

# ---------------- PROFILE MENU ----------------
def profile_menu():
    with st.popover("👤"):
        st.markdown(f"""
        <div style='text-align: center; margin-bottom: 1rem;'>
            <div style='background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                        width: 60px; height: 60px; border-radius: 30px;
                        margin: 0 auto 0.5rem; display: flex; align-items: center;
                        justify-content: center; color: white; font-size: 1.5rem;'>
                {st.session_state.role[0].upper()}
            </div>
            <div style='font-weight: 600;'>{st.session_state.role.upper()}</div>
        </div>
        """, unsafe_allow_html=True)
        
        if st.session_state.role == "user":
            res = requests.get(f"{BASE_URL}/user/", headers=headers())
        elif st.session_state.role == "host":
            res = requests.get(f"{BASE_URL}/host/", headers=headers())
        else:
            res = requests.get(f"{BASE_URL}/auth/me", headers=headers())
        
        if res.status_code == 200:
            data = res.json()
            for k, v in data.items():
                st.markdown(f"""
                <div style='margin-bottom: 0.5rem;'>
                    <span style='color: var(--gray); font-size: 0.8rem;'>{k.capitalize()}</span><br>
                    <span style='font-weight: 500;'>{v}</span>
                </div>
                """, unsafe_allow_html=True)
        
        st.divider()
        
        if st.button("Logout", use_container_width=True, type="primary"):
            st.session_state.clear()
            st.rerun()

# ---------------- WALLET UI ----------------
def wallet_ui():
    st.markdown("""
    <div style='display: flex; align-items: center; gap: 0.5rem; margin-bottom: 2rem;'>
        <div style='background: linear-gradient(135deg, #10b981 0%, #059669 100%);
                    width: 40px; height: 40px; border-radius: 12px;
                    display: flex; align-items: center; justify-content: center;
                    color: black; font-size: 1.2rem;'>
            💰
        </div>
        <div>
            <div style='font-size: 1.5rem; font-weight: 600; color: var(--dark);'>Wallet</div>
            <div style='color: var(--gray); font-size: 0.9rem;'>Manage your funds</div>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    r = requests.get(f"{BASE_URL}/wallets/myWallet", headers=headers())
    
    if r.status_code == 200:
        data = r.json()
        balance = data.get("balance") or data.get("wallet_balance") or 0
        
        st.markdown(f"""
        <div style='background: linear-gradient(135deg, #1a2a1a 0%, #0d2b1a 100%);
                    border: 1px solid #2a5c3a;
                    padding: 2.5rem 2rem; border-radius: 24px; text-align: center; margin-bottom: 2rem;
                    box-shadow: 0 4px 24px rgba(16, 185, 129, 0.12);'>
            <div style='color: #6ee7b7; font-size: 0.85rem; letter-spacing: 0.08em; text-transform: uppercase; margin-bottom: 0.75rem;'>Current Balance</div>
            <div style='font-size: 3rem; font-weight: 700; color: #ecfdf5; letter-spacing: -0.02em;'>₹ {balance:,.2f}</div>
        </div>
        """, unsafe_allow_html=True)
        
        if "warning" in data:
            st.warning(data["warning"])
    
    st.markdown("""
    <div style='display: flex; align-items: center; gap: 0.5rem; margin: 2rem 0 1rem;'>
        <div style='background: #1e3a2f; border: 1px solid #2a5c3a; width: 30px; height: 30px; border-radius: 8px;
                    display: flex; align-items: center; justify-content: center; color: #6ee7b7;'>
            ➕
        </div>
        <div style='font-size: 1.2rem; font-weight: 500; color: #e2e8f0;'>Add Money</div>
    </div>
    """, unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        amount = st.number_input("", min_value=1, value=100, step=100, label_visibility="collapsed")
        
        if st.button("➕ Add Money", use_container_width=True, type="primary"):
            with st.spinner("Processing..."):
                response = requests.post(
                    f"{BASE_URL}/wallets/topUp",
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
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown("""
        <div style='text-align: center; margin-bottom: 3rem;'>
            <div style='font-size: 4rem; margin-bottom: 1rem;'>🎟️</div>
            <div style='font-size: 2rem; font-weight: 600; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                        -webkit-background-clip: text; -webkit-text-fill-color: transparent;'>
                EveBook
            </div>
            <div style='color: var(--gray); margin-top: 0.5rem;'>AI-Powered Event Booking Platform</div>
        </div>
        """, unsafe_allow_html=True)
        
        tab1, tab2 = st.tabs(["Login", "Register"])
        
        with tab1:
            with st.container(border=True):
                username = st.text_input("Username / Email", key="login_user")
                password = st.text_input("Password", type="password", key="login_pass")
                
                if st.button("Login", use_container_width=True, type="primary"):
                    res = login(username, password)
                    
                    if res.status_code == 200:
                        st.session_state.token = res.json()["access_token"]
                        st.session_state.role = detect_role()
                        st.rerun()
                    else:
                        st.error("Invalid credentials")
        
        with tab2:
            role = st.radio("Register As", ["User", "Host"], horizontal=True)
            
            with st.container(border=True):
                if role == "User":
                    username = st.text_input("Username")
                    email = st.text_input("Email")
                    password = st.text_input("Password", type="password")
                    
                    if st.button("Register User", use_container_width=True, type="primary"):
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
                    
                    if st.button("Register Host", use_container_width=True, type="primary"):
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
    st.markdown(f"""
    <div style='display: flex; align-items: center; gap: 1rem;'>
        <div style='background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    width: 50px; height: 50px; border-radius: 16px;
                    display: flex; align-items: center; justify-content: center;
                    color: white; font-size: 1.5rem;'>
            {role[0].upper()}
        </div>
        <div>
            <div style='font-size: 1.8rem; font-weight: 600; color: var(--dark);'>Dashboard</div>
            <div style='color: var(--gray);'>{role.upper()} · {datetime.now().strftime("%B %d, %Y")}</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

with col2:
    profile_menu()

st.markdown("<hr style='margin: 1.5rem 0;'>", unsafe_allow_html=True)

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
        
        # Grid layout for events
        cols = st.columns(3)
        for idx, e in enumerate(sorted(events, key=lambda x: x.get("id", 0), reverse=True)):
            with cols[idx % 3]:
                with st.container(border=True):
                    st.markdown(f"""
                    <div style='margin-bottom: 1rem;'>
                        <div style='font-size: 2rem; margin-bottom: 0.5rem;'>🎟️</div>
                        <div style='font-weight: 600; font-size: 1.2rem;'>{e.get('title', 'Untitled')}</div>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    st.markdown(f"📅 **{e.get('date', 'Unknown')}**")
                    st.markdown(f"🎟️ Seats: **{e.get('available_seats', 0)}**")
                    st.markdown(f"💰 ₹**{e.get('ticket_price', 0)}**")
                    st.markdown(f"🏢 Host: **{e.get('host_name', e.get('host_id', 'Unknown'))}**")
                    
                    if st.button("Book Now", key=f"book_{e.get('id', e.get('event_id', 0))}", use_container_width=True, type="primary"):
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
                        st.link_button("📄 View Details", f"{BASE_URL}{e['more_details']}", use_container_width=True)
    
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
                col1, col2, col3 = st.columns([2, 1, 1])
                
                with col1:
                    st.markdown(f"""
                    <div style='font-weight: 600;'>Booking #{b.get('booking_id', 'N/A')}</div>
                    <div style='color: var(--gray);'>{b.get('event_title', 'Unknown')}</div>
                    """, unsafe_allow_html=True)
                
                with col2:
                    st.markdown(f"""
                    <div style='text-align: center;'>
                        <div style='color: var(--gray);'>Tickets</div>
                        <div style='font-weight: 600;'>{b.get('ticket_count', 1)}</div>
                    </div>
                    """, unsafe_allow_html=True)
                
                with col3:
                    st.markdown(f"""
                    <div style='text-align: center;'>
                        <div style='color: var(--gray);'>Total</div>
                        <div style='font-weight: 600; color: var(--success);'>₹{b.get('ticket_count', 1) * b.get('ticket_price', 0)}</div>
                    </div>
                    """, unsafe_allow_html=True)
                
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
                        st.link_button("📄 View Details", f"{BASE_URL}{event['more_details']}", use_container_width=True)
                
                if st.button("Cancel Booking", key=f"cancel_{b.get('booking_id')}"):
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
        with st.container(border=True):
            col1, col2 = st.columns([1, 2])
            
            with col1:
                st.markdown("""
                <div style='background: linear-gradient(135deg, #f59e0b 0%, #d97706 100%);
                            width: 80px; height: 80px; border-radius: 40px;
                            display: flex; align-items: center; justify-content: center;
                            color: white; font-size: 2rem; margin: 0 auto;'>
                    ⭐
                </div>
                """, unsafe_allow_html=True)
            
            with col2:
                st.markdown("""
                <div style='font-size: 1.5rem; font-weight: 600;'>Become a Host</div>
                <div style='color: var(--gray);'>Create events and earn money</div>
                <div style='margin-top: 0.5rem;'>💳 One-time fee: <strong>₹10,000</strong></div>
                """, unsafe_allow_html=True)
            
            st.divider()
            
            if st.button("Pay ₹10,000 & Promote to Host", use_container_width=True, type="primary"):
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
        with st.container(border=True):
            st.markdown("""
            <div style='margin-bottom: 2rem;'>
                <div style='font-size: 1.5rem; font-weight: 600; margin-bottom: 0.5rem;'>Create New Event</div>
                <div style='color: var(--gray);'>Fill in the details below</div>
            </div>
            """, unsafe_allow_html=True)
            
            with st.form("create_event_form"):
                col1, col2 = st.columns(2)
                
                with col1:
                    title = st.text_input("Event Title")
                    venue = st.text_input("Venue")
                    date_val = st.date_input("Date")
                
                with col2:
                    seats = st.number_input("Total Seats", min_value=1, value=100)
                    price = st.number_input("Ticket Price (₹)", min_value=1, value=100)
                
                document = st.file_uploader("Upload Event PDF (optional)", type=["pdf"])
                
                submitted = st.form_submit_button("Create Event", use_container_width=True, type="primary")
                
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
            with st.expander(f"🎟️ {e.get('title', 'Untitled')} — {e.get('date', 'Unknown')}"):
                col1, col2 = st.columns(2)
                
                with col1:
                    st.markdown(f"📍 **Venue:** {e.get('venue', 'Unknown')}")
                    st.markdown(f"🎟️ **Seats:** {e.get('available_seats', 0)} / {e.get('seats', 0)}")
                
                with col2:
                    st.markdown(f"💰 **Ticket Price:** ₹{e.get('ticket_price', 0)}")
                
                st.divider()
                
                col1, col2, col3, col4 = st.columns(4)
                
                # DELETE
                with col1:
                    if st.button("🗑 Delete", key=f"del_{e.get('id')}"):
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
                        st.link_button("📄 View Document", f"{BASE_URL}{e['more_details']}", use_container_width=True)
                
                # EDIT TOGGLE
                with col3:
                    if st.button("✏️ Edit", key=f"edit_toggle_{e.get('id')}"):
                        st.session_state[f"edit_mode_{e.get('id')}"] = not st.session_state.get(
                            f"edit_mode_{e.get('id')}", False
                        )
                
                # DOCUMENT TOGGLE
                with col4:
                    if st.button("📎 Update Doc", key=f"doc_toggle_{e.get('id')}"):
                        st.session_state[f"doc_mode_{e.get('id')}"] = not st.session_state.get(
                            f"doc_mode_{e.get('id')}", False
                        )
                
                # EDIT EVENT SECTION
                if st.session_state.get(f"edit_mode_{e.get('id')}", False):
                    st.divider()
                    st.markdown("### ✏️ Edit Event Details")
                    
                    with st.form(f"edit_form_{e.get('id')}"):
                        col1, col2 = st.columns(2)
                        
                        with col1:
                            new_title = st.text_input("Title", value=e.get('title', ''))
                            new_venue = st.text_input("Venue", value=e.get('venue', ''))
                        
                        with col2:
                            new_date = st.date_input(
                                "Date",
                                value=datetime.strptime(e.get('date', '2025-01-01'), "%Y-%m-%d").date()
                            )
                            new_seats = st.number_input("Seats", value=e.get('seats', 1), min_value=1)
                            new_price = st.number_input("Ticket Price", value=e.get('ticket_price', 1), min_value=1)
                        
                        if st.form_submit_button("Save Changes", use_container_width=True, type="primary"):
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
                    st.markdown("### 📄 Update Document")
                    
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
        ["Users", "Hosts", "Transactions", "Promotions", "Wallets", "Stats", "AI ChatBot"],
        key="admin_tab"
    )
    
    if tab == "AI ChatBot":
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
            with st.expander(f"👤 {u.get('username', 'Unknown')} — {u.get('email', 'No email')}"):
                user_bookings = [
                    b for b in bookings 
                    if b.get("username") == u.get("username") or b.get("user_id") == u.get("id")
                ]
                
                if not user_bookings:
                    st.info("No bookings")
                else:
                    for b in user_bookings:
                        with st.container(border=True):
                            col1, col2 = st.columns([3, 1])
                            
                            with col1:
                                st.markdown(f"**Event:** {b.get('event_title', 'Unknown')}")
                                st.markdown(f"**Tickets:** {b.get('ticket_count', 0)}")
                            
                            with col2:
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
                            
                            event = next(
                                (e for e in events if e.get("event_id") == b.get("event_id")),
                                None
                            )
                            if event and event.get("more_details"):
                                st.link_button("📄 More Details", f"{BASE_URL}{event['more_details']}", use_container_width=True)
    
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
            with st.expander(f"🏢 {h.get('company_name', h.get('username', 'Unknown'))} — {h.get('email', 'No email')}"):
                col1, col2 = st.columns(2)
                with col1:
                    st.markdown(f"**Host ID:** {h.get('host_id', h.get('id', 'N/A'))}")
                    st.markdown(f"**Company:** {h.get('company_name', 'N/A')}")
                with col2:
                    st.markdown(f"**Email:** {h.get('email', 'N/A')}")
                    st.markdown(f"**Fee Paid:** {'✅' if h.get('is_fee_paid') else '❌'}")
                
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
                            st.markdown(f"**{e.get('title', 'Untitled')}**")
                            st.markdown(f"📍 {e.get('venue', 'No venue')} | 📅 {e.get('date', 'Unknown')}")
                            st.markdown(f"🎟 Seats: {e.get('available_seats', 0)} / {e.get('total_seats', 0)}")
                            st.markdown(f"💰 ₹{e.get('ticket_price', 0)}")
                            
                            col1, col2, col3 = st.columns(3)
                            
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
                                    st.link_button(
                                        "📄 View Document", 
                                        f"{BASE_URL}{e['more_details']}",
                                        use_container_width=True
                                    )
                                else:
                                    st.write("No document")
                            
                            event_bookings = [
                                b for b in bookings if b.get("event_id") == e.get("event_id")
                            ]
                            
                            if event_bookings:
                                st.markdown("**Bookings:**")
                                for b in event_bookings:
                                    with st.container(border=True):
                                        col1, col2 = st.columns([3, 1])
                                        with col1:
                                            st.markdown(f"👤 {b.get('username', 'Unknown')} - {b.get('ticket_count', 0)} tickets")
                                        with col2:
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
            res = requests.get(f"{BASE_URL}/admin/bookings", headers=headers_auth)
            
            if res.status_code != 200:
                st.error(f"Failed to fetch bookings: {res.text}")
                return
            
            data = res.json()
            
            # Handle response format
            if isinstance(data, dict):
                if "error" in data:
                    st.error(data["error"])
                    return
                bookings = data.get("bookings", [])
            elif isinstance(data, list):
                bookings = data
            else:
                bookings = []
            
            if not bookings:
                st.info("No booking transactions found")
            else:
                st.metric("Total Bookings", len(bookings))
                st.divider()
                
                for b in bookings:
                    amount = b.get('total_amount', b.get('payment_amount', 0))
                    st.markdown(f"""
                    <div style='background:#131c2e; border:1px solid #1e3a5f; border-radius:14px;
                                padding:1.1rem 1.4rem; margin-bottom:0.75rem;
                                display:grid; grid-template-columns:1fr 1fr 1fr; gap:0.5rem 1.5rem;'>
                        <div>
                            <div style='color:#64748b; font-size:0.72rem; text-transform:uppercase; letter-spacing:0.06em;'>Booking ID</div>
                            <div style='color:#e2e8f0; font-weight:600;'>#{b.get('booking_id','N/A')}</div>
                        </div>
                        <div>
                            <div style='color:#64748b; font-size:0.72rem; text-transform:uppercase; letter-spacing:0.06em;'>User</div>
                            <div style='color:#e2e8f0; font-weight:600;'>{b.get('username','Unknown')}</div>
                        </div>
                        <div>
                            <div style='color:#64748b; font-size:0.72rem; text-transform:uppercase; letter-spacing:0.06em;'>Amount</div>
                            <div style='color:#34d399; font-weight:700; font-size:1.05rem;'>₹{amount}</div>
                        </div>
                        <div>
                            <div style='color:#64748b; font-size:0.72rem; text-transform:uppercase; letter-spacing:0.06em;'>Email</div>
                            <div style='color:#94a3b8;'>{b.get('user_email','N/A')}</div>
                        </div>
                        <div>
                            <div style='color:#64748b; font-size:0.72rem; text-transform:uppercase; letter-spacing:0.06em;'>Event</div>
                            <div style='color:#94a3b8;'>{b.get('event_title','Unknown')}</div>
                        </div>
                        <div>
                            <div style='color:#64748b; font-size:0.72rem; text-transform:uppercase; letter-spacing:0.06em;'>Tickets</div>
                            <div style='color:#94a3b8;'>{b.get('ticket_count',0)}</div>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
        
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
                    status = t.get('status', 'Unknown')
                    status_color = "#34d399" if status == "success" else "#f87171" if status == "failed" else "#fbbf24"
                    st.markdown(f"""
                    <div style='background:#131c2e; border:1px solid #1e3a5f; border-radius:14px;
                                padding:1.1rem 1.4rem; margin-bottom:0.75rem;
                                display:grid; grid-template-columns:1fr 1fr 1fr; gap:0.5rem 1.5rem;'>
                        <div>
                            <div style='color:#64748b; font-size:0.72rem; text-transform:uppercase; letter-spacing:0.06em;'>Company</div>
                            <div style='color:#e2e8f0; font-weight:600;'>{t.get('company_name','Unknown')}</div>
                        </div>
                        <div>
                            <div style='color:#64748b; font-size:0.72rem; text-transform:uppercase; letter-spacing:0.06em;'>Amount</div>
                            <div style='color:#34d399; font-weight:700; font-size:1.05rem;'>₹{t.get('amount',0)}</div>
                        </div>
                        <div>
                            <div style='color:#64748b; font-size:0.72rem; text-transform:uppercase; letter-spacing:0.06em;'>Status</div>
                            <div style='color:{status_color}; font-weight:600;'>{status}</div>
                        </div>
                        <div>
                            <div style='color:#64748b; font-size:0.72rem; text-transform:uppercase; letter-spacing:0.06em;'>Host ID</div>
                            <div style='color:#94a3b8;'>#{t.get('host_id','N/A')}</div>
                        </div>
                        <div style='grid-column:span 2;'>
                            <div style='color:#64748b; font-size:0.72rem; text-transform:uppercase; letter-spacing:0.06em;'>Date</div>
                            <div style='color:#94a3b8;'>{t.get('created_at','Unknown')}</div>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
    
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
                    if p.get('company_name'):
                        st.markdown(f"**Company:** {p.get('company_name')}")
                    elif p.get('username'):
                        st.markdown(f"**User:** {p.get('username')}")
                    
                    if p.get('amount'):
                        st.markdown(f"**Amount:** ₹{p.get('amount')}")
                    if p.get('status'):
                        st.markdown(f"**Status:** {p.get('status')}")
                    if p.get('created_at'):
                        st.markdown(f"**Date:** {p.get('created_at')}")
    
    # ================= STATS =================
    elif tab == "Stats":
        res = requests.get(f"{BASE_URL}/admin/stats", headers=headers_auth)
        
        if res.status_code != 200:
            st.error("Failed to fetch stats")
            return
        
        stats = res.json()
        
        if "error" in stats:
            st.error(stats["error"])
            return
        
        st.markdown("""
        <div style='display:flex; align-items:center; gap:0.6rem; margin-bottom:1.5rem;'>
            <div style='background:linear-gradient(135deg,#3b5bdb,#4c6ef5); width:38px; height:38px;
                        border-radius:10px; display:flex; align-items:center; justify-content:center;
                        font-size:1.1rem;'>📊</div>
            <div>
                <div style='font-size:1.3rem; font-weight:600; color:#f1f5f9;'>System Stats</div>
                <div style='color:#94a3b8; font-size:0.85rem;'>Platform overview</div>
            </div>
        </div>
        """, unsafe_allow_html=True)
        
        # Render each key-value from the stats response as a clean card grid
        items = [(k.replace("_", " ").title(), v) for k, v in stats.items()]
        
        # Rows of 3
        for i in range(0, len(items), 3):
            row = items[i:i+3]
            cols = st.columns(3)
            for col, (label, value) in zip(cols, row):
                with col:
                    # Colour-code monetary values green, counts blue
                    is_money = isinstance(value, (int, float)) and ("amount" in label.lower() or "balance" in label.lower() or "revenue" in label.lower())
                    val_color = "#34d399" if is_money else "#93c5fd"
                    display_val = f"₹{value:,.2f}" if is_money and isinstance(value, float) else f"₹{value:,}" if is_money else (f"{value:,}" if isinstance(value, (int, float)) else str(value))
                    st.markdown(f"""
                    <div style='background:#131c2e; border:1px solid #1e3a5f; border-radius:14px;
                                padding:1.2rem 1.2rem; margin-bottom:0.75rem; text-align:center;'>
                        <div style='color:#64748b; font-size:0.72rem; text-transform:uppercase;
                                    letter-spacing:0.07em; margin-bottom:0.4rem;'>{label}</div>
                        <div style='color:{val_color}; font-size:1.6rem; font-weight:700;'>{display_val}</div>
                    </div>
                    """, unsafe_allow_html=True)
    
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
                        st.markdown(f"**{owner_type}:** {owner_name}")
                        if w.get('email'):
                            st.markdown(f"📧 {w.get('email')}")
                    
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