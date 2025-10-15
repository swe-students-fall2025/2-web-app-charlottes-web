import random
import string
from datetime import datetime

import pytz
from bson import ObjectId
from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from pymongo.errors import DuplicateKeyError

from app import CODE_LENGTH, TAX_RATE, mongo

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
    if not bill:
        flash("Bill not found.", "error")
        return redirect(url_for("vendor.dashboard"))
    return render_template(
        'vendor/bill_info.html',
        bill=bill,
        tax=TAX_RATE
    )
