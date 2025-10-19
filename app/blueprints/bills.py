import random
import string
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

import pytz
from bson import ObjectId
from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError

from app import CODE_LENGTH, TAX_RATE, mongo

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
    assigned_to: Optional[str] = None
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
            "assigned_to": self.assigned_to,
            "split_type": self.split_type
        }


@vendor_bill_bp.route('/create', methods=['POST'])
@login_required
def create_bill():
    '''
    Create a bill
    '''
    if current_user.user_type != 'vendor':
        flash("Access denied.", "error")
        return redirect(url_for("customer.dashboard"))
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


def generate_code():
    return "".join(
        random.choices(string.ascii_uppercase + string.digits, k=CODE_LENGTH)
    )


@vendor_bill_bp.route('/detail/<bill_id>', methods=['GET'])
@login_required
def display_bill(bill_id):
    '''
    Display information for a bill
    '''
    if current_user.user_type != 'vendor':
        flash("Access denied.", "error")
        return redirect(url_for("customer.dashboard"))

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
def view_menu_for_bill(bill_id):
    '''
    Render menu to add items to a bill
    '''
    if current_user.user_type != 'vendor':
        flash('Access denied. Vendor account required.', 'error')
        return redirect(url_for('customer.dashboard'))
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
def add_to_bill(bill_id, item_id):
    '''
    Add a menu item to a bill
    '''
    if current_user.user_type != 'vendor':
        flash('Access denied. Vendor account required.', 'error')
        return redirect(url_for('customer.dashboard'))
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
def delete_from_bill(bill_id, item_id):
    '''
    Delete a specified item from a bill
    '''
    if current_user.user_type != 'vendor':
        flash('Access denied. Vendor account required.', 'error')
        return redirect(url_for('customer.dashboard'))
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
def delete(bill_id):
    '''
    Delete a bill
    '''
    if current_user.user_type != 'vendor':
        flash('Access denied. Vendor account required.', 'error')
        return redirect(url_for('customer.dashboard'))
    bill = mongo.db.bills.find_one({"_id": ObjectId(bill_id)})
    if not bill or bill["vendor_id"] != current_user.id:
        flash("Bill not found.", "error")
        return redirect(url_for("vendor.dashboard"))

    mongo.db.bills.delete_one({"_id": ObjectId(bill_id)})
    return redirect(url_for("vendor.dashboard"))
    
@vendor_bill_bp.route('/addgroup/<bill_id>/<group_id>')
@login_required
def addgroup(bill_id, group_id):
    '''
    Add a group associated with bill
    '''
    if current_user.user_type != 'vendor':
        flash('Access denied. Vendor account required.', 'error')
        return redirect(url_for('customer.dashboard'))
    
    bill = mongo.db.bills.find_one({"_id": ObjectId(bill_id)})
    if not bill or bill["vendor_id"] != current_user.id:
        flash("Bill not found.", "error")
        return redirect(url_for("vendor.dashboard"))
    
    # TODO: call attach_group_to_bill() somehow?