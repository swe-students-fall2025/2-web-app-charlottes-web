from flask import render_template, redirect, url_for, request, flash
from flask_login import login_user, logout_user, current_user, login_required
from app import app, mongo
from app.models import User, Group, Bill, Payment, PaymentSession
from bson.objectid import ObjectId

@app.route('/')
@app.route('/index')
def index():
    '''
    Landing page
    '''
    return render_template('index.html', title='Home')

@app.route('/login', methods=['GET', 'POST'])
def login():
    '''
    Login page
    '''
    if current_user.is_authenticated:
        return redirect(url_for('customer_dashboard'))
    
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')

        # Validate input
        if not email or not password:
            flash('Please provide both email and password', 'error')
            return redirect(url_for('login'))

        # Find user by email
        user_data = mongo.db.users.find_one({'email': email})

        if not user_data:
            flash('Invalid email or password', 'error')
            return redirect(url_for('login'))

        user = User(user_data)

        # Check password
        if not user.check_password(password):
            flash('Invalid email or password', 'error')
            return redirect(url_for('login'))

        # Login user
        login_user(user)
        flash(f'Welcome back, {user.username}!', 'success')

        # Redirect based on user type
        if user.user_type == 'vendor':
            return redirect(url_for('index'))  # vendor_dashboard later
        else:
            return redirect(url_for('customer_dashboard'))

    return render_template('login.html', title='Login')

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    '''
    Signup page
    '''
    if current_user.is_authenticated:
        return redirect(url_for('customer_dashboard'))

    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        user_type = request.form.get('user_type', 'customer')
        # phone = request.form.get('phone', '')

        # Validate input
        if not all([username, email, password, confirm_password]):
            flash('All fields are required', 'error')
            return redirect(url_for('signup'))

        if password != confirm_password:
            flash('Passwords do not match', 'error')
            return redirect(url_for('signup'))

        # Check if user already exists
        if mongo.db.users.find_one({'email': email}):
            flash('Email already registered', 'error')
            return redirect(url_for('signup'))

        if mongo.db.users.find_one({'username': username}):
            flash('Username already taken', 'error')
            return redirect(url_for('signup'))

        # Create user
        vendor_name = request.form.get('vendor_name', '') if user_type == 'vendor' else ''
        user_dict = User.create_user_dict(
            username=username,
            email=email,
            password=password,
            user_type=user_type,
            # phone=phone,
            vendor_name=vendor_name
        )

        # Insert into database
        result = mongo.db.users.insert_one(user_dict)

        # Login the new user
        user_data = mongo.db.users.find_one({'_id': result.inserted_id})
        user = User(user_data)
        login_user(user)

        flash(f'Welcome, {username}! Your account has been created.', 'success')

        if user_type == 'vendor':
            return redirect(url_for('index'))
        else:
            return redirect(url_for('customer_dashboard'))

    return render_template('signup.html', title='Sign Up')

@app.route('/logout')
@login_required
def logout():
    '''
    Logout user
    '''
    logout_user()
    flash('You have been logged out.', 'success')
    return redirect(url_for('index'))

@app.route('/customer/dashboard')
def customer_dashboard():
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

@app.route('/customer/group/create', methods=['GET', 'POST'])
@login_required
def create_group():
    '''
    Create a new group
    '''
    if request.method == 'POST':
        # Get form data
        group_name = request.form.get('group_name')
        
        # Validate
        if not group_name or len(group_name.strip()) == 0:
            flash('Group name is required', 'error')
            return redirect(url_for('create_group'))
        
        # Create group document
        new_group = {
            'name': group_name.strip(),
            'creator_id': current_user.id,
            'members': [current_user.id],
            'active_bill_id': None,
            'active': True,
            'created_at': None
        }
        
        # Insert into MongoDB
        result = mongo.db.groups.insert_one(new_group)
        
        flash(f'Group "{group_name}" created successfully!', 'success')
        return redirect(url_for('customer_dashboard'))
    
    # GET request - show form
    return render_template('customer/create_group.html', title='Create Group')

@app.route('/customer/group/join', methods=['GET', 'POST'])
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
            return redirect(url_for('join_group'))
        
        try:
            # Find the group
            group = mongo.db.groups.find_one({'_id': ObjectId(group_id.strip())})
            
            if not group:
                flash('Group not found. Please check the Group ID and try again.', 'error')
                return redirect(url_for('join_group'))
            
            # Check if user is already a member
            if current_user.id in group.get('members', []):
                flash('You are already a member of this group!', 'error')
                return redirect(url_for('customer_dashboard'))
            
            # Add user to group members
            mongo.db.groups.update_one(
                {'_id': ObjectId(group_id.strip())},
                {'$push': {'members': current_user.id}}
            )
            
            flash(f'Successfully joined group "{group["name"]}"!', 'success')
            return redirect(url_for('customer_dashboard'))
            
        except Exception as e:
            flash('Invalid Group ID format. Please try again.', 'error')
            return redirect(url_for('join_group'))
    
    # GET request - show form
    return render_template('customer/join_group.html', title='Join Group')

@app.route('/customer/group/<group_id>')
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
            return redirect(url_for('customer_dashboard'))
        
        # Check if current user is a member
        if current_user.id not in group.get('members', []):
            flash('You are not a member of this group.', 'error')
            return redirect(url_for('customer_dashboard'))
        
        # Get member details
        member_ids = [ObjectId(m) for m in group.get('members', [])]
        members = list(mongo.db.users.find({'_id': {'$in': member_ids}}))
        
        # Get active bill if exists
        active_bill = None
        if group.get('active_bill_id'):
            active_bill = mongo.db.bills.find_one({'_id': ObjectId(group['active_bill_id'])})
        
        return render_template('customer/group_detail.html',
                               title=group['name'],
                               group=group,
                               members=members,
                               active_bill=active_bill,
                               is_creator=(current_user.id == group['creator_id']))
        
    except Exception as e:
        flash('Invalid group ID.', 'error')
        return redirect(url_for('customer_dashboard'))

@app.route('/customer/group/<group_id>/leave', methods=['POST'])
@login_required
def leave_group(group_id):
    '''
    Leave a group
    '''
    try:
        group = mongo.db.groups.find_one({'_id': ObjectId(group_id)})
        
        if not group:
            flash('Group not found.', 'error')
            return redirect(url_for('customer_dashboard'))
        
        # Check if user is a member
        if current_user.id not in group.get('members', []):
            flash('You are not a member of this group.', 'error')
            return redirect(url_for('customer_dashboard'))
        
        # Prevent creator from leaving if there are other members
        if current_user.id == group['creator_id'] and len(group.get('members', [])) > 1:
            flash('As the creator, you cannot leave while other members are in the group. Transfer ownership or remove all members first.', 'error')
            return redirect(url_for('group_detail', group_id=group_id))
        
        # Remove user from group
        mongo.db.groups.update_one(
            {'_id': ObjectId(group_id)},
            {'$pull': {'members': current_user.id}}
        )
        
        # If this was the last member, deactivate the group
        updated_group = mongo.db.groups.find_one({'_id': ObjectId(group_id)})
        if len(updated_group.get('members', [])) == 0:
            mongo.db.groups.update_one(
                {'_id': ObjectId(group_id)},
                {'$set': {'active': False}}
            )
        
        flash(f'You have left the group "{group["name"]}".', 'success')
        return redirect(url_for('customer_dashboard'))
        
    except Exception as e:
        flash('An error occurred while leaving the group.', 'error')
        return redirect(url_for('customer_dashboard'))
