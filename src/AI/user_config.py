from model import UserSettings
from sqlalchemy.orm import Session

DEFAULT_SENSITIVE_TOOLS = [
    "delete_file",
    "delete_pdf",
    "change_directory",
    "top_up_wallet"
]

def get_user_sensitive_tools(db : Session, user_id : int, user_role : str):
    settings = db.query(UserSettings).filter(UserSettings.user_id == user_id, UserSettings.user_role == user_role).first()

    if not settings:
        # create default settings
        settings = UserSettings(
            user_id = user_id,
            user_role = user_role,
            sensitive_tools = DEFAULT_SENSITIVE_TOOLS
        )
        db.add(settings)
        db.commit()
        db.refresh(settings)

    return settings.sensitive_tools


def update_user_sensitive_tools(db: Session, user_id : int, user_role : str, tools : list):
    settings = db.query(UserSettings).filter(UserSettings.user_id == user_id, UserSettings.user_role == user_role).first()
    if not settings:
        # create default settings
        settings = UserSettings(
            user_id = user_id,
            user_role = user_role,
            sensitive_tools = tools
        )
        db.add(settings)
        db.commit()
        db.refresh(settings)
    settings.sensitive_tools = tools
    db.add(settings)
    db.commit()
    db.refresh(settings)

    return settings