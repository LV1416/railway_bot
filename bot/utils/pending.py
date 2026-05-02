import time
from dataclasses import dataclass, field
from typing import Dict, Any, List

import config

@dataclass
class PendingAction:
    type: str
    data: Dict[str, Any]
    original_text: str
    created_at: float = field(default_factory=time.time)
    edits: List[str] = field(default_factory=list)

# Global store for pending actions
_pending_store: Dict[str, PendingAction] = {}

def set_pending(user_id: str, action_type: str, data: dict, text: str):
    _pending_store[str(user_id)] = PendingAction(
        type=action_type,
        data=data,
        original_text=text
    )

def get_pending(user_id: str) -> PendingAction | None:
    """Get pending action if it exists and hasn't expired."""
    uid = str(user_id)
    action = _pending_store.get(uid)
    if action:
        if time.time() - action.created_at <= config.PENDING_TTL:
            return action
        else:
            # Expired
            del _pending_store[uid]
    return None

def clear_pending(user_id: str):
    uid = str(user_id)
    if uid in _pending_store:
        del _pending_store[uid]
