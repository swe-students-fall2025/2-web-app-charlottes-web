import random
import string

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from pymongo.errors import DuplicateKeyError

from app import mongo

CODE_LENGTH = 6  # group join code length

vendor_bill_bp = Blueprint(
    'vendor_bills', f"vendor_{__name__}", url_prefix='/vendor/bill'
)
customer_bill_bp = Blueprint(
    'customer_bills', f"customer_{__name__}", url_prefix='/customer/bill'
)


@vendor_bill_bp.route('/create', methods=['POST'])
@login_required
def create_bill():
    '''
    Create a bill
    '''
    mongo.db.bills.create_index([("session_code", 1)], unique=True)
    if current_user.user_type != 'vendor':
        flash("Access denied.", "error")
        return redirect(url_for("customer.dashboard"))
    while True:
        try:
            new_bill = {
                "vendor_id": current_user.id,
                "table_number": request.form.get("table_number"),
                "items": [],
                "total_amount": 0,
                "status": "pending",
                "session_code": generate_code(),
                "participants": {}
            }
            mongo.db.bills.insert_one(new_bill)
            break
        except DuplicateKeyError:
            pass

    # TODO: Go to bill page
    return redirect(url_for("vendor.dashboard"))


@vendor_bill_bp.route('/detail/<bill_id>', methods=['GET'])
@login_required
def display_bill(bill_id):
    '''
    Display information for a bill
    '''
    bill = mongo.db.bills.find_one({"_id": bill_id})
    return "HI"


def generate_code():
    return "".join(
        random.choices(string.ascii_uppercase + string.digits, k=CODE_LENGTH)
    )
