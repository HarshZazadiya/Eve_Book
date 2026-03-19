import os
import redis
from database import SessionLocal
from langchain_core.tools import tool
from model import Users, Hosts, Wallets


REDIS_URL = os.getenv("REDIS_URL")
redis_client = redis.Redis.from_url(REDIS_URL, decode_responses=True) if REDIS_URL else None

@tool
def get_wallet_balance(authenticated_user_id: int, authenticated_user_type: str = None) -> dict:
    """
    Get your current wallet balance.
    Works for users, hosts, and admins.
    REMEMBER THE CURRENCY IS IN INR (₹).
    
    Args:
        authenticated_user_id: Your authenticated ID
        authenticated_user_type: Your role ('user', 'host', or 'admin')
    
    Returns:
        Dictionary with current balance
    """
    db = SessionLocal()
    try:
        # Validate input
        if not authenticated_user_type:
            return {"error": "User type not provided"}
        
        # Handle different user types
        if authenticated_user_type == "host":
            # Host - use host ID directly
            host = db.query(Hosts).filter(Hosts.id == authenticated_user_id).first()
            if not host:
                return {"error": "Host not found"}
            
            wallet = db.query(Wallets).filter(Wallets.owner_type == "host",  Wallets.owner_id == authenticated_user_id).first()
            
            balance = wallet.balance if wallet else 0
            result = {"balance" : balance}
            
            if balance < 500:
                result["warning"] = "Low balance - need ₹500 to create events"
            
        elif authenticated_user_type == "user":
            # Regular user
            user = db.query(Users).filter(Users.id == authenticated_user_id).first()
            if not user:
                return {"error" : "User not found"}
            
            # FIX: Added owner_type filter
            wallet = db.query(Wallets).filter(Wallets.owner_type == "user", Wallets.owner_id == authenticated_user_id).first()
            
            balance = wallet.balance if wallet else 0
            result = {"balance" : balance}
            
        elif authenticated_user_type == "admin":
            # Admin - check if admin has a wallet
            admin = db.query(Users).filter(Users.id == authenticated_user_id, Users.role == "admin").first()
            if not admin:
                return {"error": "Admin not found"}
            
            # FIX: Check for admin wallet
            wallet = db.query(Wallets).filter(Wallets.owner_type == "admin", Wallets.owner_id == authenticated_user_id).first()
            
            balance = wallet.balance if wallet else 0
            result = {"balance": balance}
            
        else:
            return {"error": f"Invalid user type: {authenticated_user_type}"}
        
        return result
        
    except Exception as e:
        print(f"❌ Error in get_wallet_balance: {e}")
        return {"error": f"Failed to get wallet balance: {str(e)}"}
    finally:
        db.close()


@tool
def top_up_wallet(amount: int, authenticated_user_id: int, authenticated_user_type: str = None) -> dict:
    """
    Add money to your wallet.
    REMEMBER THE CURRENCY IS IN INR (₹).

    Args:
        amount: Amount to add (positive number)
        authenticated_user_id: Your authenticated ID
        authenticated_user_type: Your role ('user', 'host', or 'admin')
    
    Returns:
        Dictionary with updated balance
    """
    # Validate amount
    if amount <= 0:
        return {"error": "Amount must be positive"}
    
    if not authenticated_user_type:
        return {"error": "User type not provided"}
    
    db = SessionLocal()
    try:
        # Map user type to wallet owner type
        owner_type_map = {
            "user" : "user",
            "host" : "host", 
            "admin" : "admin"
        }
        
        if authenticated_user_type not in owner_type_map:
            return {"error": f"Invalid user type: {authenticated_user_type}"}
        
        owner_type = owner_type_map[authenticated_user_type]
        owner_id = authenticated_user_id
        
        # Verify the user exists based on type
        if authenticated_user_type == "host":
            entity = db.query(Hosts).filter(Hosts.id == owner_id).first()
            if not entity:
                return {"error": "Host not found"}
        elif authenticated_user_type == "user":
            entity = db.query(Users).filter(Users.id == owner_id).first()
            if not entity:
                return {"error": "User not found"}
        elif authenticated_user_type == "admin":
            entity = db.query(Users).filter(
                Users.id == owner_id, 
                Users.role == "admin"
            ).first()
            if not entity:
                return {"error": "Admin not found"}
        
        # Get or create wallet
        wallet = db.query(Wallets).filter(Wallets.owner_type == owner_type, Wallets.owner_id == owner_id).first()

        if wallet:
            wallet.balance += amount
        else:
            wallet = Wallets(
                owner_type = owner_type,
                owner_id = owner_id,
                balance = amount
            )
            db.add(wallet)

        db.commit()
        db.refresh(wallet)

        return {
            "balance" : wallet.balance,
            "message" : f"Wallet topped up with ₹{amount}",
            "new_balance" : wallet.balance
        }
        
    except Exception as e:
        db.rollback()
        print(f"❌ Error in top_up_wallet: {e}")
        return {"error" : f"Failed to top up wallet: {str(e)}"}
    finally:
        db.close()


default_tools = [get_wallet_balance, top_up_wallet]