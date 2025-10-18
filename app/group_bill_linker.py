"""
Group ↔ Bill linker service

Core idea:
- We store the association on the Group side as: groups.active_bill_id = bill._id
- We enforce vendor isolation:
    bill.vendor_id == vendor_id == group.creator_id
- All functions here are DB-agnostic helpers you can call from CLI, a job, or future routes.

Typical usage:
    from app.services.group_bill_linker import attach_group_to_bill, detach_group_from_bill

Can also import list_vendor_groups/get_attached_group.
"""

from __future__ import annotations
from typing import Optional, Tuple, List, Dict, Any

try:
    # Prefer bson's ObjectId if your _id fields are ObjectIds.
    from bson import ObjectId
    _HAS_OID = True
except Exception:
    _HAS_OID = False
    ObjectId = str  # fallback typing

class LinkError(Exception):
    """Raised when linking rules or lookups fail."""

def _maybe_oid(val: Any):
    """Convert a hex string to ObjectId if bson is available; otherwise return as-is."""
    if not _HAS_OID:
        return val
    if isinstance(val, ObjectId):
        return val
    return ObjectId(str(val))

def ensure_indexes(db) -> None:
    """Optional: run once to make lookups snappy."""
    try:
        db.groups.create_index("creator_id")
        db.groups.create_index("active_bill_id")
        db.bills.create_index("vendor_id")
    except Exception:
        # Safe to ignore in most local setups
        pass

def _load_bill(db, bill_id: str) -> Dict[str, Any]:
    bill = db.bills.find_one({"_id": _maybe_oid(bill_id)})
    if not bill:
        raise LinkError("Bill not found.")
    return bill

def _load_group(db, group_id: str) -> Dict[str, Any]:
    group = db.groups.find_one({"_id": _maybe_oid(group_id)})
    if not group:
        raise LinkError("Group not found.")
    return group

def _assert_same_vendor(bill: Dict[str, Any], group: Optional[Dict[str, Any]], vendor_id: str) -> None:
    if str(bill.get("vendor_id")) != str(vendor_id):
        raise LinkError("Vendor mismatch on bill.")
    if group is not None and str(group.get("creator_id")) != str(vendor_id):
        raise LinkError("Vendor mismatch on group.")

def get_attached_group(db, *, bill_id: str) -> Optional[Dict[str, Any]]:
    """Return the group document attached to this bill, or None."""
    return db.groups.find_one({"active_bill_id": _maybe_oid(bill_id)})

def list_vendor_groups(db, *, vendor_id: str) -> List[Dict[str, Any]]:
    """List groups owned by a vendor (useful to feed a dropdown)."""
    return list(db.groups.find({"creator_id": vendor_id}).sort("name", 1))

def attach_group_to_bill(
    db,
    *,
    vendor_id: str,
    bill_id: str,
    group_id: str,
    allow_reattach: bool = True
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """
    Attach a group to a bill by setting groups.active_bill_id = bill._id.
    If the group is already attached to another bill:
      - allow_reattach=True  → it will be moved to the new bill
      - allow_reattach=False → raises LinkError
    Returns (bill_doc, group_doc) after update.
    """
    bill = _load_bill(db, bill_id)
    group = _load_group(db, group_id)
    _assert_same_vendor(bill, group, vendor_id)

    # If already attached somewhere else, decide behavior
    current_ptr = group.get("active_bill_id")
    if current_ptr and str(current_ptr) != str(bill["_id"]):
        if not allow_reattach:
            raise LinkError("Group is already attached to a different bill.")
        # else: proceed to move the pointer

    db.groups.update_one(
        {"_id": group["_id"]},
        {"$set": {"active_bill_id": bill["_id"]}}
    )
    # re-read
    bill = _load_bill(db, bill_id)
    group = _load_group(db, group_id)
    return bill, group

def detach_group_from_bill(db, *, vendor_id: str, bill_id: str) -> int:
    """
    Detach any groups currently pointing to this bill.
    Returns the number of modified groups.
    """
    bill = _load_bill(db, bill_id)
    _assert_same_vendor(bill, None, vendor_id)
    res = db.groups.update_many(
        {"active_bill_id": bill["_id"]},
        {"$set": {"active_bill_id": None}}
    )
    return getattr(res, "modified_count", 0)

def move_group_between_bills(
    db,
    *,
    vendor_id: str,
    from_bill_id: str,
    to_bill_id: str,
    group_id: str
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """
    Move a specific group from one bill to another.
    Validates both bills belong to vendor and group belongs to vendor.
    """
    from_bill = _load_bill(db, from_bill_id)
    to_bill = _load_bill(db, to_bill_id)
    group = _load_group(db, group_id)

    _assert_same_vendor(from_bill, group, vendor_id)
    _assert_same_vendor(to_bill, None, vendor_id)

    if str(group.get("active_bill_id")) != str(from_bill["_id"]):
        raise LinkError("This group is not attached to the 'from' bill.")

    db.groups.update_one(
        {"_id": group["_id"]},
        {"$set": {"active_bill_id": to_bill["_id"]}}
    )
    # return fresh docs
    return _load_bill(db, to_bill_id), _load_group(db, group_id)
