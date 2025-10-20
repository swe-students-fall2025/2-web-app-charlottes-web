"""
Custom Flask decorators for authentication and authorization
"""
from functools import wraps
from flask import flash, redirect, url_for
from flask_login import current_user


def vendor_access_required(f):
    '''
    decorator to check if current user is a customer
    redirects to vendor dashboard if not authorized
    '''
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if current_user.user_type != 'vendor':
            flash("Access denied.", "error")
            return redirect(url_for("index"))
        return f(*args, **kwargs)
    return decorated_function


def customer_access_required(f):
    '''
    decorator to check if current user is a customer
    redirects to vendor dashboard if not authorized
    '''
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if current_user.user_type != 'customer':
            flash("Access denied.", "error")
            return redirect(url_for("index"))
        return f(*args, **kwargs)
    return decorated_function
