import uuid
from dataclasses import dataclass, field
from datetime import datetime

import pytz
from bson import ObjectId
from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError

from app import TAX_RATE, mongo
from app.utils.code_generator import generate_code
from app.utils.decorators import vendor_access_required

vendor_bill_bp = Blueprint(
    'vendor_bills', f"vendor_{__name__}", url_prefix='/vendor/bill'
)
customer_bill_bp = Blueprint(
    'customer_bills', f"customer_{__name__}", url_prefix='/customer/bill'
)


@dataclass
class OrderItem:
    item_id: str
    name: str
    price: float
    quantity: int
    bill_id: str
    assigned_to: list = field(default_factory=list)
    split_type: str = "equal"
    _id: uuid = field(default_factory=lambda: str(uuid.uuid4()))

    def to_dict(self):
        return {
            "_id": self._id,
            "item_id": self.item_id,
            "name": self.name,
            "price": self.price,
            "quantity": self.quantity,
            "bill_id": self.bill_id,
            "assigned_to": self.assigned_to or [],
            "split_type": self.split_type
        }


@vendor_bill_bp.route('/create', methods=['POST'])
@login_required
@vendor_access_required
def create_bill():
    '''
    Create a bill
    '''
    mongo.db.bills.create_index([("session_code", 1)], unique=True)
    while True:
        try:
            new_bill = {
                "vendor_id": current_user.id,
                "table_number": request.form.get("table_number"),
                "contents": [],
                "subtotal": 0,
                "status": "pending",
                "session_code": generate_code(),
                "created_at": datetime.now(pytz.timezone("US/Eastern"))
            }
            new_bill = mongo.db.bills.insert_one(new_bill)
            break
        except DuplicateKeyError:
            pass

    return redirect(
        url_for("vendor_bills.display_bill", bill_id=new_bill.inserted_id)
    )


@vendor_bill_bp.route('/detail/<bill_id>', methods=['GET'])
@login_required
def display_bill(bill_id):
    '''
    Display information for a bill
    '''
    bill = mongo.db.bills.find_one({"_id": ObjectId(bill_id)})
    if not bill or bill["vendor_id"] != current_user.id:
        flash("Bill not found.", "error")
        return redirect(url_for("vendor.dashboard"))

    return render_template(
        'bills/vendor_bill_info.html',
        bill=bill,
        tax=TAX_RATE
    )


@vendor_bill_bp.route('/add_menu/<bill_id>', methods=['GET'])
@login_required
@vendor_access_required
def view_menu_for_bill(bill_id):
    '''
    Render menu to add items to a bill
    '''
    bill = mongo.db.bills.find_one({"_id": ObjectId(bill_id)})
    if not bill or bill["vendor_id"] != current_user.id:
        flash("Bill not found.", "error")
        return redirect(url_for("vendor.dashboard"))

    menu_items = list(mongo.db.menu_items.find({'vendor_id': current_user.id}))

    return render_template('bills/add_to_bill.html',
                           title='Menu Items',
                           menu_items=menu_items,
                           bill_id=bill_id)


@vendor_bill_bp.route('/add/<bill_id>/<item_id>', methods=['POST'])
@login_required
@vendor_access_required
def add_to_bill(bill_id, item_id):
    '''
    Add a menu item to a bill
    '''
    bill = mongo.db.bills.find_one({"_id": ObjectId(bill_id)})
    if not bill or bill["vendor_id"] != current_user.id:
        flash("Bill not found.", "error")
        return redirect(url_for("vendor.dashboard"))

    menu_item = mongo.db.menu_items.find_one({
        "_id": ObjectId(item_id)
    })
    quantity = float(request.form.get("qty", 1))
    new_order_item = OrderItem(
        item_id=str(menu_item["_id"]),
        name=menu_item["name"],
        price=menu_item["price"],
        quantity=quantity,
        bill_id=bill_id
    )
    bill = mongo.db.bills.find_one_and_update(
        {"_id": ObjectId(bill_id)},
        {
            "$inc": {"subtotal": menu_item["price"] * quantity},
            "$push": {"contents": new_order_item.to_dict()}
        },
        return_document=ReturnDocument.AFTER
    )

    return redirect(url_for("vendor_bills.display_bill", bill_id=bill["_id"]))


@vendor_bill_bp.route('/delete_from_bill/<bill_id>/<item_id>')
@login_required
@vendor_access_required
def delete_from_bill(bill_id, item_id):
    '''
    Delete a specified item from a bill
    '''
    bill = mongo.db.bills.find_one({"_id": ObjectId(bill_id)})
    if not bill or bill["vendor_id"] != current_user.id:
        flash("Bill not found.", "error")
        return redirect(url_for("vendor.dashboard"))

    bill_contents = (
        mongo.db.bills.find_one({"_id": ObjectId(bill_id)})["contents"]
    )

    item = next(
        (item for item in bill_contents if item["_id"] == item_id), None
    )

    bill = mongo.db.bills.find_one_and_update(
        {"_id": ObjectId(bill_id)},
        {
            "$pull": {"contents": {"_id": item["_id"]}},
            "$inc": {"subtotal": -item["price"]}
        }
    )
    return redirect(url_for("vendor_bills.display_bill", bill_id=bill["_id"]))


@vendor_bill_bp.route('/delete/<bill_id>')
@login_required
@vendor_access_required
def delete(bill_id):
    '''
    Delete a bill and remove it from any groups' active_bill_id
    '''
    bill = mongo.db.bills.find_one({"_id": ObjectId(bill_id)})
    if not bill or bill["vendor_id"] != current_user.id:
        flash("Bill not found.", "error")
        return redirect(url_for("vendor.dashboard"))

    # Remove this bill from any groups that have it as active_bill_id
    mongo.db.groups.update_many(
        {"active_bill_id": ObjectId(bill_id)},
        {"$set": {"active_bill_id": None}}
    )

    mongo.db.bills.delete_one({"_id": ObjectId(bill_id)})
    return redirect(url_for("vendor.dashboard"))


@customer_bill_bp.route('/join-by-code', methods=['POST'])
@login_required
def join_by_code():
    '''
    Customer joins a bill using payment code and attaches their group to it.
    '''
    try:
        session_code = request.form.get('session_code', '').strip().upper()
        group_id = request.form.get('group_id', '').strip()

        if not session_code or not group_id:
            flash("Missing payment code or group ID.", "error")
            return redirect(url_for("customer.dashboard"))

        # Find bill by session_code
        bill = mongo.db.bills.find_one({"session_code": session_code})
        if not bill:
            flash(f"Payment code '{session_code}' not found. Please check and try again.", "error")
            return redirect(url_for("customer.group_detail", group_id=group_id))

        # Verify group exists and user is a member
        group = mongo.db.groups.find_one({"_id": ObjectId(group_id)})
        if not group:
            flash("Group not found.", "error")
            return redirect(url_for("customer.dashboard"))

        if current_user.id not in group.get('members', []):
            flash("You are not a member of this group.", "error")
            return redirect(url_for("customer.dashboard"))

        # Attach group to bill
        mongo.db.groups.update_one(
            {"_id": ObjectId(group_id)},
            {"$set": {"active_bill_id": ObjectId(bill['_id'])}}
        )

        flash(f'Group "{group["name"]}" joined Bill (Code: {session_code}) successfully!', "success")
        return redirect(url_for('customer.display_bill', group_id=group_id))

    except Exception as e:
        flash(f"An error occurred: {str(e)}", "error")
        return redirect(url_for("customer.dashboard"))
