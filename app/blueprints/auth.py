from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required, login_user, logout_user

from app import mongo
from app.models import User

auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    '''
    Login page
    '''
    if current_user.is_authenticated:
        return redirect(url_for('customer.dashboard'))

    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')

        # Validate input
        if not email or not password:
            flash('Please provide both email and password', 'error')
            return redirect(url_for('auth.login'))

        # Find user by email
        user_data = mongo.db.users.find_one({'email': email})

        if not user_data:
            flash('Invalid email or password', 'error')
            return redirect(url_for('auth.login'))

        user = User(user_data)

        # Check password
        if not user.check_password(password):
            flash('Invalid email or password', 'error')
            return redirect(url_for('auth.login'))

        # Login user
        login_user(user)
        flash(f'Welcome back, {user.username}!', 'success')

        return redirect(url_for('index'))

    return render_template('login.html', title='Login')


@auth_bp.route('/signup', methods=['GET', 'POST'])
def signup():
    '''
    Signup page
    '''
    if current_user.is_authenticated:
        return redirect(url_for('index'))

    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        user_type = request.form.get('user_type', 'customer')

        # Validate input
        if not all([username, email, password, confirm_password]):
            flash('All fields are required', 'error')
            return redirect(url_for('auth.signup'))

        if password != confirm_password:
            flash('Passwords do not match', 'error')
            return redirect(url_for('auth.signup'))

        # Check if user already exists
        if mongo.db.users.find_one({'email': email}):
            flash('Email already registered', 'error')
            return redirect(url_for('auth.signup'))

        if mongo.db.users.find_one({'username': username}):
            flash('Username already taken', 'error')
            return redirect(url_for('auth.signup'))

        # Create user
        vendor_name = (
            request.form.get('vendor_name', '')
            if user_type == 'vendor' else ''
        )
        user_dict = User.create_user_dict(
            username=username,
            email=email,
            password=password,
            user_type=user_type,
            vendor_name=vendor_name
        )

        # Insert into database
        result = mongo.db.users.insert_one(user_dict)

        # Login the new user
        user_data = mongo.db.users.find_one({'_id': result.inserted_id})
        user = User(user_data)
        login_user(user)

        flash(
            f'Welcome, {username}! Your account has been created.', 'success'
        )

        return redirect(url_for('index'))

    return render_template('signup.html', title='Sign Up')


@auth_bp.route('/logout')
@login_required
def logout():
    '''
    Logout user
    '''
    logout_user()
    flash('You have been logged out.', 'success')
    return redirect(url_for('index'))
