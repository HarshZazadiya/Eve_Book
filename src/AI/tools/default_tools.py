from langchain_core.tools import tool
from database import SessionLocal
from model import Users, Hosts, Wallets
import os
import redis

REDIS_URL = os.getenv("REDIS_URL")
redis_client = redis.Redis.from_url(REDIS_URL, decode_responses=True) if REDIS_URL else None

@tool
def get_wallet_balance(authenticated_user_id: int, authenticated_user_type: str = None) -> dict:
    """
    Get your current wallet balance.
    Works for both users and hosts.
    REMEBER THE CURRENCY IS IN INR (₹).
    Args:
        authenticated_user_id: Your authenticated ID
        authenticated_user_type: Your role ('user', 'host', or 'admin')
    
    Returns:
        Dictionary with current balance
    """
    db = SessionLocal()
    try:
        # Handle different user types
        if authenticated_user_type == "host":
            # Host - use host ID directly
            host = db.query(Hosts).filter(Hosts.id == authenticated_user_id).first()
            if not host:
                return {"error": "Host not found"}
            
            wallet = db.query(Wallets).filter(Wallets.owner_type == "host", Wallets.owner_id == authenticated_user_id).first()
            
            balance = wallet.balance if wallet else 0
            result = {"balance": balance}
            
            if balance < 500:
                result["warning"] = "Low balance - need ₹500 to create events"
            
        else:
            # User or admin - use user ID
            user = db.query(Users).filter(Users.id == authenticated_user_id).first()
            if not user:
                return {"error": "User not found"}
            
            wallet = db.query(Wallets).filter(Wallets.owner_type == "user", Wallets.owner_id == authenticated_user_id).first()
            
            balance = wallet.balance if wallet else 0
            result = {"balance": balance}
        
        return result
    except Exception as e:
        return {"error": str(e)}
    finally:
        db.close()


@tool
def top_up_wallet(amount: int, authenticated_user_id: int, authenticated_user_type: str = None) -> dict:
    """
    Add money to your wallet.
    REMEBER THE CURRENCY IS IN INR (₹).

    Args:
        amount: Amount to add (positive number)
        authenticated_user_id: Your authenticated ID
        authenticated_user_type: Your role
    
    Returns:
        Dictionary with updated balance
    """
    if amount <= 0:
        return {"error": "Amount must be positive"}
    
    db = SessionLocal()
    try:
        # Determine wallet type based on user type
        if authenticated_user_type == "host":
            owner_type = "host"
            owner_id = authenticated_user_id
        else:
            owner_type = "user"
            owner_id = authenticated_user_id
        
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
            "message" : f"Wallet topped up with ₹{amount}"
        }
    except Exception as e:
        db.rollback()
        return {"error": str(e)}
    finally:
        db.close()


default_tools = [get_wallet_balance, top_up_wallet]