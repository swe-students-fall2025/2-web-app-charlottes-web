from dataclasses import dataclass
from datetime import datetime

from bson.objectid import ObjectId
from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from pymongo.errors import DuplicateKeyError

from app import TAX_RATE, mongo
from app.payment import PaymentError, demo_payment_provider
from app.utils.code_generator import generate_code
from app.utils.decorators import customer_access_required

customer_bp = Blueprint('customer', __name__, url_prefix='/customer')


@dataclass
class PaymentMethod:
    nickname: str
    token: str
    last_four: str
    expiry_date: datetime
    cardholder_name: str

    def to_dict(self):
        return {
            "nickname": self.nickname,
            "token": self.token,
            "last_four": self.last_four,
            "expiry_date": self.expiry_date,
            "cardholder_name": self.cardholder_name
        }


@customer_bp.route('/dashboard')
@login_required
@customer_access_required
def dashboard():
    '''
    shows user's groups
    '''
    # Find all groups where user is a member
    groups = mongo.db.groups.find({'members': current_user.id})
    groups_list = list(groups)

    payment_methods = (
        mongo.db.users.find_one({"_id": ObjectId(current_user.id)})
        ["payment_methods"]
    )

    return render_template('customer/dashboard.html',
                           title='My Groups',
                           groups=groups_list,
                           user_id=current_user.id,
                           payment_methods=payment_methods)


@customer_bp.route('/group/create', methods=['GET', 'POST'])
@login_required
@customer_access_required
def create_group():
    '''
    Create a new group
    '''
    if request.method == 'POST':
        mongo.db.groups.create_index([("code", 1)], unique=True)
        # Get form data
        group_name = request.form.get('group_name')

        # Validate
        if not group_name or len(group_name.strip()) == 0:
            flash('Group name is required', 'error')
            return redirect(url_for('customer.create_group'))

        while True:
            try:
                # Create group document
                new_group = {
                    'name': group_name.strip(),
                    'creator_id': current_user.id,
                    'members': [current_user.id],
                    'active_bill_id': None,
                    'active': True,
                    'created_at': None,
                    'code': generate_code()
                }
                # Insert into MongoDB
                mongo.db.groups.insert_one(new_group)
                break
            except DuplicateKeyError:
                pass

        flash(f'Group "{group_name}" created successfully!', 'success')
        return redirect(url_for('customer.dashboard'))

    # GET request - show form
    return render_template('customer/create_group.html', title='Create Group')


@customer_bp.route('/group/join', methods=['GET', 'POST'])
@login_required
@customer_access_required
def join_group():
    '''
    Join an existing group by group ID
    '''
    if request.method == 'POST':
        group_id = request.form.get('group_id')

        # Validate input
        if not group_id or len(group_id.strip()) == 0:
            flash('Group ID is required', 'error')
            return redirect(url_for('customer.join_group'))

        try:
            # Find the group
            group = mongo.db.groups.find_one(
                {'code': group_id.strip().upper()}
            )

            if not group:
                flash(
                    'Group not found. '
                    'Please check the Group ID and try again.',
                    'error'
                )
                return redirect(url_for('customer.join_group'))

            # Check if user is already a member
            if current_user.id in group.get('members', []):
                flash('You are already a member of this group!', 'error')
                return redirect(url_for('customer.dashboard'))

            # Add user to group members
            mongo.db.groups.update_one(
                {'_id': group["_id"]},
                {'$push': {'members': current_user.id}}
            )

            flash(f'Successfully joined group "{group["name"]}"!', 'success')
            return redirect(url_for('customer.dashboard'))

        except Exception:
            flash('Invalid Group ID format. Please try again.', 'error')
            return redirect(url_for('customer.join_group'))

    # GET request - show form
    return render_template('customer/join_group.html', title='Join Group')


@customer_bp.route('/group/<group_id>')
@login_required
@customer_access_required
def group_detail(group_id):
    '''
    Show group details including members and active bill
    '''
    try:
        # Find the group
        group = mongo.db.groups.find_one({'_id': ObjectId(group_id)})

        if not group:
            flash('Group not found.', 'error')
            return redirect(url_for('customer.dashboard'))

        # Check if current user is a member
        if current_user.id not in group.get('members', []):
            flash('You are not a member of this group.', 'error')
            return redirect(url_for('customer.dashboard'))

        # Get member details
        member_ids = [ObjectId(m) for m in group.get('members', [])]
        members = list(mongo.db.users.find({'_id': {'$in': member_ids}}))

        # Get active bill if exists
        active_bill = None
        if group.get('active_bill_id'):
            active_bill = mongo.db.bills.find_one(
                {'_id': ObjectId(group['active_bill_id'])}
            )

        return render_template('customer/group_detail.html',
                               title=group['name'],
                               group=group,
                               members=members,
                               active_bill=active_bill,
                               is_creator=(
                                   current_user.id == group['creator_id']
                               ),
                               tax=TAX_RATE)

    except Exception:
        flash('Invalid group ID.', 'error')
        return redirect(url_for('customer.dashboard'))


@customer_bp.route('/group/<group_id>/leave', methods=['POST'])
@login_required
@customer_access_required
def leave_group(group_id):
    '''
    Leave a group
    '''
    try:
        group = mongo.db.groups.find_one({'_id': ObjectId(group_id)})

        if not group:
            flash('Group not found.', 'error')
            return redirect(url_for('customer.dashboard'))

        # Check if user is a member
        if current_user.id not in group.get('members', []):
            flash('You are not a member of this group.', 'error')
            return redirect(url_for('customer.dashboard'))

        # Prevent creator from leaving if there are other members
        if (
            current_user.id == group['creator_id']
            and len(group.get('members', [])) > 1
        ):
            flash(
                'As the creator, you cannot leave while '
                'other members are in the group.',
                'error'
            )
            return redirect(
                url_for('customer.group_detail', group_id=group_id)
            )

        # Remove user from group
        mongo.db.groups.update_one(
            {'_id': ObjectId(group_id)},
            {'$pull': {'members': current_user.id}})

        # If this was the last member, delete the group
        updated_group = mongo.db.groups.find_one({'_id': ObjectId(group_id)})
        if len(updated_group.get('members', [])) == 0:
            mongo.db.groups.delete_one({'_id': ObjectId(group_id)})

        flash(f'You have left the group "{group["name"]}".', 'success')
        return redirect(url_for('customer.dashboard'))

    except Exception:
        flash('An error occurred while leaving the group.', 'error')
        return redirect(url_for('customer.dashboard'))


# @customer_bp.route('/bill/display/<group_id>')
# @login_required
# def display_bill(group_id):
#     """
#     Display the current active bill for a given group.

#     """
#     if current_user.user_type != 'customer':
#         flash('Access denied. Customer account required.', 'error')
#         return redirect(url_for('vendor.dashboard'))

#     group = mongo.db.groups.find_one({"_id": ObjectId(group_id)})
#     if not group:
#         flash("Group not found.", "error")
#         return redirect(url_for("customer.dashboard"))

#     bill_id = group.get("active_bill_id")
#     if not bill_id:
#         flash("No active bill for this group.", "error")
#         return redirect(url_for("customer.dashboard"))

#     bill = mongo.db.bills.find_one({"_id": ObjectId(bill_id)})
#     if not bill:
#         flash("Bill not found.", "error")
#         return redirect(url_for("customer.dashboard"))

#     items = bill.get("contents", [])
#     group_members = group.get("members", [])

#     for item in items:
#         assigned = item.get("assigned_to", []) or []
#         item["assigned_user_objects"] = [
#             mongo.db.users.find_one({"_id": ObjectId(uid)}) for uid in assigned if uid
#         ]

#     return render_template(
#         "customer/customer_bill.html",
#         bill=bill,
#         group=group,
#         items=items,
#         group_members=group_members
#     )

@customer_bp.route('/bill/display/<group_id>')
@login_required
@customer_access_required
def display_bill(group_id):
    if current_user.user_type != 'customer':
        flash('Access denied. Customer account required.', 'error')
        return redirect(url_for('vendor.dashboard'))
    
    group = mongo.db.groups.find_one({"_id" : ObjectId(group_id)})
    if not group:
        flash("Group not found.", "error")
        return redirect(url_for("customer.dashboard"))
    
    if current_user.id not in group.get("members", []):
        flash("You are not a member of this group.", "error")
        return redirect(url_for("customer.dashboard"))

    # if user_id not in group.get("members", []):
    #     flash("Target user is not a member of this group.", "error")
    #     return redirect(url_for("customer.dashboard"))
    
    bill = mongo.db.bills.find_one({"_id": ObjectId(group.get("active_bill_id"))})
    if not bill:
        flash("Bill not found.", "error")
        return redirect(url_for("customer.dashboard"))
    return render_template("customer/display_bill.html", bill=bill, tax=TAX_RATE, group=group)

@customer_bp.route('/bill/split_interface/<group_id>/<bill_id>/<item_id>', methods=['GET'])
@login_required
def show_split_interface(group_id, bill_id, item_id):
    group = mongo.db.groups.find_one({"_id": ObjectId(group_id)})
    bill = mongo.db.bills.find_one({"_id": ObjectId(bill_id)})

    if not group or not bill:
        flash("Invalid group or bill.", "error")
        return redirect(url_for("customer.dashboard"))

    # Find the target item
    target_item = next((it for it in bill.get("contents", []) if str(it["_id"]) == str(item_id)), None)
    if not target_item:
        flash("Item not found.", "error")
        return redirect(url_for("customer.display_bill", group_id=group_id))

    assigned_users = []
    for id in target_item.get("assigned_to", []):
        assigned_users.append(mongo.db.users.find_one({"_id": ObjectId(id)}))
    
    # Load group members for display
    members = list(mongo.db.users.find({"_id": {"$in": [ObjectId(uid) for uid in group["members"]]}}))

    return render_template(
        "customer/split_bill.html",
        group=group,
        bill=bill,
        item=target_item,
        members=members,
        assigned_users=assigned_users
    )

@customer_bp.route('/bill/split/<group_id>/<bill_id>/<item_id>', methods=['POST'])
@login_required
def split_bill(group_id, bill_id, item_id):
    user_ids = request.form.getlist("user_ids")

    group = mongo.db.groups.find_one({"_id": ObjectId(group_id)})
    if not group:
        flash("Group not found.", "error")
        return redirect(url_for("customer.dashboard"))

    bill = mongo.db.bills.find_one({"_id": ObjectId(bill_id)})
    if not bill:
        flash("Bill not found.", "error")
        return redirect(url_for("customer.dashboard"))

    # Verify all selected users belong to this group
    for uid in user_ids:
        if uid not in group["members"]:
            flash("One or more selected users are not in this group.", "error")
            return redirect(url_for("customer.display_bill", group_id=group_id))

    # Update the bill’s item to assign all selected members
    mongo.db.bills.update_one(
        {"_id": ObjectId(bill_id), "contents._id": item_id},
        {"$set": {"contents.$.assigned_to": user_ids}}
    )

    flash("Bill successfully split among selected members!", "success")
    return redirect(url_for("customer.display_bill", group_id=group_id))


@customer_bp.route('/add_payment_method', methods=['POST'])
@login_required
@customer_access_required
def add_payment_method():
    '''
    Add a saved payment method for the consumer
    '''
    try:
        card_token = demo_payment_provider.register(request.form)
    except (ValueError, PaymentError) as e:
        flash(str(e), "error")
        return redirect(url_for("customer.dashboard"))

    new_card = PaymentMethod(
        nickname=request.form.get("nickname", "Untitled card"),
        token=card_token,
        last_four=request.form["card_number"][-4:],
        expiry_date=request.form["expiry_date"],
        cardholder_name=request.form["cardholder_name"]
    )

    mongo.db.users.find_one_and_update(
        {"_id": ObjectId(current_user.id)},
        {"$push": {"payment_methods": new_card.to_dict()}}
    )

    return redirect(url_for("customer.dashboard"))


@customer_bp.route('/add_payment_form', methods=['GET'])
@login_required
@customer_access_required
def add_payment_method_form():
    return render_template("customer/add_payment_method.html")


@customer_bp.route('/delete_payment_method/<token>', methods=['POST'])
@login_required
@customer_access_required
def delete_payment_method(token):
    '''
    Delete a payment method
    '''

    mongo.db.users.find_one_and_update(
        {"_id": ObjectId(current_user.id)},
        {"$pull": {"payment_methods": {"token": token}}}
    )

    demo_payment_provider.delete_card(token)

    return redirect(url_for("customer.dashboard"))
