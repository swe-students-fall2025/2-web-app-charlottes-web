from bson.objectid import ObjectId
from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from pymongo.errors import DuplicateKeyError

from app import mongo
from app.utils.code_generator import generate_code

customer_bp = Blueprint('customer', __name__, url_prefix='/customer')


@customer_bp.route('/dashboard')
def dashboard():
    '''
    shows user's groups
    '''
    # Find all groups where user is a member
    groups = mongo.db.groups.find({'members': current_user.id})
    groups_list = list(groups)

    return render_template('customer/dashboard.html',
                           title='My Groups',
                           groups=groups_list,
                           user_id=current_user.id)


@customer_bp.route('/group/create', methods=['GET', 'POST'])
@login_required
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
                               ))

    except Exception:
        flash('Invalid group ID.', 'error')
        return redirect(url_for('customer.dashboard'))


@customer_bp.route('/group/<group_id>/leave', methods=['POST'])
@login_required
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


@customer_bp.route('/bill/display/<group_id>')
@login_required
def display_bill(group_id):
    """
    Display the current active bill for a given group.

    """
    if current_user.user_type != 'customer':
        flash('Access denied. Customer account required.', 'error')
        return redirect(url_for('vendor.dashboard'))

    group = mongo.db.groups.find_one({"_id": ObjectId(group_id)})
    if not group:
        flash("Group not found.", "error")
        return redirect(url_for("customer.dashboard"))

    bill_id = group.get("active_bill_id")
    if not bill_id:
        flash("No active bill for this group.", "error")
        return redirect(url_for("customer.dashboard"))

    bill = mongo.db.bills.find_one({"_id": ObjectId(bill_id)})
    if not bill:
        flash("Bill not found.", "error")
        return redirect(url_for("customer.dashboard"))

    items = bill.get("contents", [])
    group_members = group.get("members", [])

    for item in items:
        assigned = item.get("assigned_to", []) or []
        item["assigned_user_objects"] = [
            mongo.db.users.find_one({"_id": ObjectId(uid)}) for uid in assigned if uid
        ]

    return render_template(
        "customer/customer_bill.html",
        bill=bill,
        group=group,
        items=items,
        group_members=group_members
    )

@customer_bp.route('/bill/split/<group_id>/<item_id>/<user_id>', methods=['POST'])
@login_required
def split_bill(group_id, item_id, user_id):
    '''
    Adds an additional member into the "assigned_to" list of the item inside the bill
    '''
    if current_user.user_type != 'customer':
        flash('Access denied. Customer account required.', 'error')
        return redirect(url_for('vendor.dashboard'))
    
    if current_user.id not in group.get("members", []):
        flash("You are not a member of this group.", "error")
        return redirect(url_for("customer.dashboard"))

    if user_id not in group.get("members", []):
        flash("Target user is not a member of this group.", "error")
        return redirect(url_for("customer.dashboard"))
    
    group = mongo.db.groups.find_one({"_id" : ObjectId(group_id)})
    if not group:
        flash("Group not found.", "error")
        return redirect(url_for("customer.dashboard"))
    
    bill = mongo.db.bills.find_one({"_id": ObjectId(group.get("active_bill_id"))})
    if not bill:
        flash("Bill not found.", "error")
        return redirect(url_for("customer.dashboard"))
    
    target_item = None
    for content in bill.get("contents"):
        if content.get("_id") == item_id:
            target_item = content
    if not target_item:
        flash("Target item not found.", "error")
        return redirect(url_for("customer.dashboard"))

    if user_id not in target_item["assigned_to"]:
        mongo.db.bills.update_one({
            {"_id": ObjectId(group.get("active_bill_id")), "contents._id": target_item.get('_id', "") },
            {
                "$push": {"assigned_to" : user_id }
            }
        })
    
    return redirect(url_for("customer.display_bill", group_id=group_id))

