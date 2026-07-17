"""Order lifecycle state machine.

PLACED -> CONFIRMED -> PACKED -> OUT_FOR_DELIVERY | READY_FOR_PICKUP -> DELIVERED
       -> COMPLETED, with REJECTED / CANCELLED / DISPUTED side paths.
Every transition is validated here; routes append an order_events audit entry per move.
"""

STATES = [
    "PLACED",
    "CONFIRMED",
    "PACKED",
    "OUT_FOR_DELIVERY",
    "READY_FOR_PICKUP",
    "DELIVERED",
    "COMPLETED",
    "CANCELLED",
    "REJECTED",
    "DISPUTED",
]

# (from_state, action) -> (to_state, allowed_roles)
# "consumer"/"farmer" mean the consumer/farmer ON THIS ORDER; admin may always act.
TRANSITIONS = {
    ("PLACED", "accept"): ("CONFIRMED", {"farmer"}),
    ("PLACED", "reject"): ("REJECTED", {"farmer"}),
    ("PLACED", "cancel"): ("CANCELLED", {"consumer"}),
    ("CONFIRMED", "pack"): ("PACKED", {"farmer"}),
    ("CONFIRMED", "cancel"): ("CANCELLED", {"consumer"}),  # only before PACKED
    ("PACKED", "out_for_delivery"): ("OUT_FOR_DELIVERY", {"farmer"}),
    ("PACKED", "ready_for_pickup"): ("READY_FOR_PICKUP", {"farmer"}),
    ("OUT_FOR_DELIVERY", "delivered"): ("DELIVERED", {"farmer"}),
    ("READY_FOR_PICKUP", "delivered"): ("DELIVERED", {"farmer"}),
    ("DELIVERED", "complete"): ("COMPLETED", {"consumer"}),
    ("DELIVERED", "dispute"): ("DISPUTED", {"consumer"}),
    ("DISPUTED", "resolve_complete"): ("COMPLETED", {"admin"}),
    ("DISPUTED", "resolve_cancel"): ("CANCELLED", {"admin"}),
}

# States whose entry must restore reserved stock.
RESTOCK_STATES = {"CANCELLED", "REJECTED"}
# Terminal states: no further transitions.
TERMINAL_STATES = {"COMPLETED", "CANCELLED", "REJECTED"}


def resolve(from_state, action, actor_role, is_order_consumer, is_order_farmer):
    """Return (to_state, error). Validates both the edge and who is allowed to walk it."""
    key = (from_state, action)
    if key not in TRANSITIONS:
        return None, f"Illegal transition: {action} from {from_state}"
    to_state, allowed = TRANSITIONS[key]
    if actor_role == "admin":
        return to_state, None
    if "consumer" in allowed and is_order_consumer:
        return to_state, None
    if "farmer" in allowed and is_order_farmer:
        return to_state, None
    return None, f"Role not allowed to {action} this order"
