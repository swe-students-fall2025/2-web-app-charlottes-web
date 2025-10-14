from flask import render_template, redirect, url_for
from flask_login import current_user
from app import app

@app.route('/')
@app.route('/index')
def index():
    '''
    Landing page
    '''
    if current_user.is_authenticated:
        if current_user.user_type == 'vendor':
            return redirect(url_for('vendor.dashboard'))
        else:
            return redirect(url_for('customer.dashboard'))

    return render_template('index.html', title='Home')
