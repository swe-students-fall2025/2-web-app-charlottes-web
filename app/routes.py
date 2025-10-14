from flask import render_template, redirect, url_for, request, flash
from app import app, mongo
from app.models import User, Group, Bill, Payment, PaymentSession
from bson.objectid import ObjectId

@app.route('/')
@app.route('/index')
def index():
    '''
    Landing page
    '''
    user = {'username': 'Charlotte'}
    return render_template('index.html', title='Home', user=user)

@app.route('/customer/dashboard')
def customer_dashboard():
    '''
    shows user's groups
    '''
    test_user_id = 'test_user_123'
    
    # Find all groups where user is a member
    groups = mongo.db.groups.find({'members': test_user_id})
    groups_list = list(groups)
    
    return render_template('customer/dashboard.html', 
                           title='My Groups', 
                           groups=groups_list,
                           user_id=test_user_id)

@app.route('/customer/group/create', methods=['GET', 'POST'])
def create_group():
    '''
    Create a new group
    '''
    if request.method == 'POST':
        # Get form data
        group_name = request.form.get('group_name')
        test_user_id = "test_user_123"  # Replace with current_user.id later
        
        # Validate
        if not group_name or len(group_name.strip()) == 0:
            flash('Group name is required', 'error')
            return redirect(url_for('create_group'))
        
        # Create group document
        new_group = {
            'name': group_name.strip(),
            'creator_id': test_user_id,
            'members': [test_user_id],
            'active_bill_id': None,
            'active': True,
            'created_at': None  # MongoDB will auto-generate if needed
        }
        
        # Insert into MongoDB
        result = mongo.db.groups.insert_one(new_group)
        
        flash(f'Group "{group_name}" created successfully!', 'success')
        return redirect(url_for('customer_dashboard'))
    
    # GET request - show form
    return render_template('customer/create_group.html', title='Create Group')

@app.route('/customer/group/join', methods=['GET', 'POST'])
def join_group():
    '''
    Join an existing group by group ID
    '''
    if request.method == 'POST':
        group_id = request.form.get('group_id')
        test_user_id = "test_user_123"  # Replace with current_user.id later
        
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
            if test_user_id in group.get('members', []):
                flash('You are already a member of this group!', 'error')
                return redirect(url_for('customer_dashboard'))
            
            # Add user to group members
            mongo.db.groups.update_one(
                {'_id': ObjectId(group_id.strip())},
                {'$push': {'members': test_user_id}}
            )
            
            flash(f'Successfully joined group "{group["name"]}"!', 'success')
            return redirect(url_for('customer_dashboard'))
            
        except Exception as e:
            flash('Invalid Group ID format. Please try again.', 'error')
            return redirect(url_for('join_group'))
    
    # GET request - show form
    return render_template('customer/join_group.html', title='Join Group')
