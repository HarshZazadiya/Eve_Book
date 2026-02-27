"""
Guardrails to ensure agents stay within their role boundaries
"""

def check_role_permission(role: str, action: str) -> bool:
    """
    Check if a role is allowed to perform an action
    """
    # Define permissions for each role
    permissions = {
        "user": {
            "can": [
                "view_events",
                "view_own_bookings",
                "book_event",
                "cancel_own_booking",
                "view_own_wallet",
                "promote_self_to_host"
            ],
            "cannot": [
                "view_all_users",
                "view_all_hosts",
                "delete_event",
                "delete_booking",
                "demote_host",
                "create_event",
                "update_event",
                "view_all_wallets",
                "view_all_transactions"
            ]
        },
        "host": {
            "can": [
                "view_own_events",
                "create_event",
                "update_own_event",
                "delete_own_event",
                "view_own_wallet",
                "view_event_documents"
            ],
            "cannot": [
                "view_all_users",
                "view_all_hosts",
                "delete_other_events",
                "book_events",
                "promote_users",
                "view_all_wallets"
            ]
        },
        "admin": {
            "can": [
                "view_all_users",
                "view_all_hosts",
                "view_all_events",
                "view_all_bookings",
                "view_all_wallets",
                "view_all_transactions",
                "delete_any_event",
                "delete_any_booking",
                "demote_any_host"
            ],
            "cannot": [
                "book_events",
                "create_events"  # Admins manage, don't create events
            ]
        }
    }
    
    # Check if action is in can list
    return action in permissions.get(role, {}).get("can", [])

def get_role_boundaries(role: str) -> str:
    """
    Get a clear description of what a role can and cannot do
    """
    boundaries = {
        "user": """
                    YOU ARE A REGULAR USER - STRICT BOUNDARIES:

                    ✅ YOU CAN:
                    - View all events
                    - View your own bookings
                    - Book events (1 ticket only)
                    - Cancel your own bookings
                    - View your wallet balance
                    - Upgrade yourself to host (pay ₹10,000)

                    ❌ YOU CANNOT:
                    - View other users' data
                    - View hosts' data
                    - Create or edit events
                    - Delete any events
                    - Cancel others' bookings
                    - View system wallets
                    - View transactions
                    - Demote hosts
                    - Create admin accounts

                    If a user asks to do something outside these boundaries, you MUST say:
                    "I cannot do that as a regular user. This action requires higher privileges."
                """,
        "host": """
                        YOU ARE AN EVENT HOST - STRICT BOUNDARIES:

                        ✅ YOU CAN:
                        - View your own events
                        - Create new events (costs ₹500)
                        - Update your own events
                        - Delete your own events (with refunds)
                        - Upload event documents
                        - View your wallet balance

                        ❌ YOU CANNOT:
                        - View other hosts' events
                        - View any users' data
                        - Book events
                        - Cancel others' bookings
                        - View system wallets
                        - View all users
                        - Demote other hosts
                        - Promote users

                        If a user asks to do something outside these boundaries, you MUST say:
                        "I cannot do that as a host. This action is not within my permissions."
                    """,
        "admin": """
                        YOU ARE AN ADMINISTRATOR - STRICT BOUNDARIES:

                        ✅ YOU CAN:
                        - View all users
                        - View all hosts
                        - View all events
                        - View all bookings
                        - View all wallets
                        - View all transactions
                        - Delete any event
                        - Delete any booking
                        - Demote any host

                        ❌ YOU CANNOT:
                        - Book events (you manage, don't participate)
                        - Create events (you manage, don't create)
                        - Top up wallets (users do that)
                        - Promote users (users do that themselves)

                        If a user asks to do something outside these boundaries, you MUST say:
                        "As an admin, I cannot perform that action. My role is to monitor and manage the platform."
                    """
    }
    
    return boundaries.get(role, "Unknown role")

"""
Guardrails to ensure agents stay within their role boundaries
"""

def check_role_permission(role: str, action: str) -> bool:
    """
    Check if a role is allowed to perform an action
    """
    permissions = {
        "user": {
            "can": [
                "view_own_profile",
                "view_own_bookings",
                "view_own_wallet",
                "view_all_events",
                "book_event",
                "cancel_own_booking",
                "promote_self_to_host"
            ],
            "cannot": [
                "view_other_users",
                "view_other_bookings",
                "view_other_wallets",
                "view_hosts",
                "view_admins",
                "delete_anything",
                "update_anything"
            ]
        },
        "host": {
            "can": [
                "view_own_profile",
                "view_own_events",
                "view_own_wallet",
                "create_event",
                "update_own_event",
                "delete_own_event",
                "view_event_documents"
            ],
            "cannot": [
                "view_other_users",
                "view_other_hosts",
                "view_admins",
                "book_events",
                "view_other_wallets"
            ]
        },
        "admin": {
            "can": [
                "view_all_users",
                "view_all_hosts",
                "view_all_events",
                "view_all_bookings",
                "view_all_wallets",
                "view_all_transactions",
                "delete_any_event",
                "delete_any_booking",
                "demote_any_host"
            ],
            "cannot": [
                "book_events",
                "create_events"
            ]
        }
    }
    
    return action in permissions.get(role, {}).get("can", [])

def get_role_boundaries(role: str) -> str:
    """
    Get a clear description of what a role can and cannot do
    """
    boundaries = {
        "user": """
                    🔒 **REGULAR USER - YOUR BOUNDARIES**:

                    ✅ **YOU CAN:**
                    - View your own profile
                    - View your own wallet balance
                    - View your own bookings
                    - View all events (but not who booked them)
                    - Book events (1 ticket only)
                    - Cancel your own bookings
                    - Promote yourself to host

                    ❌ **YOU CANNOT:**
                    - View other users' information
                    - View other users' bookings
                    - View other users' wallets
                    - View host information
                    - View admin information
                    - Delete or modify anything

                    If you ask about other users, I MUST respond: "I cannot show you information about other users. This violates privacy."
                    """,
                            "host": """
                    🔒 **HOST - YOUR BOUNDARIES**:

                    ✅ **YOU CAN:**
                    - View your own profile
                    - View your own wallet balance
                    - View your own events
                    - Create new events
                    - Update your own events
                    - Delete your own events

                    ❌ **YOU CANNOT:**
                    - View other users' information
                    - View other hosts' information
                    - View admin information
                    - Book events
                    - View other users' wallets

                    If you ask about other users, I MUST respond: "I cannot show you information about other users. This violates privacy."
                """,
        "admin": """
                    🔒 **ADMIN - YOUR BOUNDARIES**:

                    ✅ **YOU CAN:**
                    - View all users
                    - View all hosts
                    - View all events
                    - View all bookings
                    - View all wallets
                    - Delete any event
                    - Delete any booking
                    - Demote hosts

                    ❌ **YOU CANNOT:**
                    - Book events
                    - Create events

                    You have access to user information, but must use it responsibly.
                """
    }
    
    return boundaries.get(role, "Unknown role")

def is_query_about_others(query: str) -> bool:
    """
    Detect if a query is asking about other users
    """
    query_lower = query.lower()
    
    indicators = [
        "other user",
        "other users",
        "all user",
        "all users",
        "list users",
        "show users",
        "get users",
        "tell me about users",
        "who are the users",
        "what users",
        "user list",
        "users list",
        "other people",
        "all people",
        "everyone else",
        "other accounts",
        "all accounts"
    ]
    
    return any(indicator in query_lower for indicator in indicators)


def extract_intent_from_message(message: str) -> str:
    """
    Simple intent extraction to check permissions
    """
    message_lower = message.lower()
    
    # User-only actions
    if any(word in message_lower for word in ["book", "my bookings", "cancel my"]):
        return "user_action"
    
    # Host-only actions
    if any(word in message_lower for word in ["create event", "my events", "update event"]):
        return "host_action"
    
    # Admin-only actions
    if any(word in message_lower for word in ["all users", "all hosts", "delete event", "delete booking", "demote"]):
        return "admin_action"
    
    # View actions (most roles can view relevant data)
    if any(word in message_lower for word in ["show", "list", "view", "tell me about", "what"]):
        return "view_action"
    
    return "general_chat"