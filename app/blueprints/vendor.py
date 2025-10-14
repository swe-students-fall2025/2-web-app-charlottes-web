import random
import string

from bson.objectid import ObjectId
from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from pymongo.errors import DuplicateKeyError

from app import mongo

vendor_bp = Blueprint('vendor', __name__, url_prefix='/vendor')
CODE_LENGTH = 6  # group join code length


@vendor_bp.route('/dashboard')
@login_required
def dashboard():
    '''
    Vendor dashboard - shows active bills and menu items
    '''
    # Check if user is a vendor
    if current_user.user_type != 'vendor':
        flash('Access denied. Vendor account required.', 'error')
        return redirect(url_for('customer.dashboard'))

    # Get vendor's active bills
    active_bills = list(mongo.db.bills.find({
        'vendor_id': current_user.id,
        'status': {'$in': ['pending', 'active']}
        })
    )

    # Get completed bills count
    completed_count = mongo.db.bills.count_documents({
        'vendor_id': current_user.id,
        'status': 'completed'
    })

    # Get menu items count
    menu_items_count = mongo.db.menu_items.count_documents(
        {'vendor_id': current_user.id}
    )

    return render_template('vendor/dashboard.html',
                           title='Vendor Dashboard',
                           active_bills=active_bills,
                           completed_count=completed_count,
                           menu_items_count=menu_items_count)


@vendor_bp.route('/menu')
@login_required
def menu():
    '''
    Vendor menu items management
    '''
    if current_user.user_type != 'vendor':
        flash('Access denied. Vendor account required.', 'error')
        return redirect(url_for('customer.dashboard'))

    # Get all menu items for this vendor
    menu_items = list(mongo.db.menu_items.find({'vendor_id': current_user.id}))

    return render_template('vendor/menu.html',
                           title='Menu Items',
                           menu_items=menu_items)


@vendor_bp.route('/menu/add', methods=['GET', 'POST'])
@login_required
def add_menu_item():
    '''
    Add a new menu item
    '''
    if current_user.user_type != 'vendor':
        flash('Access denied. Vendor account required.', 'error')
        return redirect(url_for('customer.dashboard'))

    if request.method == 'POST':
        name = request.form.get('name')
        price = request.form.get('price')
        description = request.form.get('description', '')
        category = request.form.get('category', 'Other')

        # Validate
        if not name or not price:
            flash('Name and price are required.', 'error')
            return redirect(url_for('vendor.add_menu_item'))

        try:
            price_float = float(price)
            if price_float <= 0:
                flash('Price must be greater than 0.', 'error')
                return redirect(url_for('vendor.add_menu_item'))
        except ValueError:
            flash('Invalid price format.', 'error')
            return redirect(url_for('vendor.add_menu_item'))

        # Create menu item
        menu_item = {
            'vendor_id': current_user.id,
            'name': name.strip(),
            'price': price_float,
            'description': description.strip(),
            'category': category,
            'available': True
        }

        mongo.db.menu_items.insert_one(menu_item)
        flash(f'Menu item "{name}" added successfully', 'success')
        return redirect(url_for('vendor.menu'))

    return render_template('vendor/add_menu_item.html', title='Add Menu Item')


@vendor_bp.route('/menu/<item_id>/delete', methods=['POST'])
@login_required
def delete_menu_item(item_id):
    '''
    Delete a menu item
    '''
    if current_user.user_type != 'vendor':
        flash('Access denied.', 'error')
        return redirect(url_for('customer.dashboard'))

    try:
        # Verify ownership
        item = mongo.db.menu_items.find_one({
            '_id': ObjectId(item_id),
            'vendor_id': current_user.id})

        if not item:
            flash('Menu item not found.', 'error')
            return redirect(url_for('vendor.menu'))

        mongo.db.menu_items.delete_one({'_id': ObjectId(item_id)})
        flash('Menu item deleted successfully!', 'success')

    except Exception:
        flash('Error deleting menu item.', 'error')

    return redirect(url_for('vendor.menu'))


@vendor_bp.route('/bill/create', methods=['POST'])
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
                "session_code": generate_code()
            }
            mongo.db.bills.insert_one(new_bill)
            break
        except DuplicateKeyError:
            pass

    # TODO: Go to bill page
    return redirect(url_for("vendor.dashboard"))


def generate_code():
    return "".join(
        random.choices(string.ascii_uppercase + string.digits, CODE_LENGTH)
    )
