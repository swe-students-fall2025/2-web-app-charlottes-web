from datetime import datetime

import pytz
from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash


class User(UserMixin):
    '''
    User model
    '''
    def __init__(self, user_data):
        self.id = str(user_data.get('_id', ''))
        self.username = user_data.get('username', '')
        self.email = user_data.get('email', '')
        self.password_hash = user_data.get('password_hash', '')
        self.user_type = user_data.get('user_type', 'customer')
        # self.phone = user_data.get('phone', '')
        self.payment_method = user_data.get('payment_method', {})
        self.vendor_name = user_data.get('vendor_name', '')
        # self.created_at = user_data.get('created_at', datetime.utcnow())

    def set_password(self, password):
        return generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def get_id(self):
        return self.id

    @staticmethod
    def create_user_dict(
        username, email, password, user_type='customer', **kwargs
    ):
        '''
        Create user dict to save in MongoDB
        '''
        user_dict = {
            'username': username,
            'email': email,
            'password_hash': generate_password_hash(password),
            'user_type': user_type,
            # 'phone': kwargs.get('phone', ''),
            # 'created_at': datetime.utcnow()
        }

        if user_type == 'customer':
            user_dict['payment_method'] = kwargs.get('payment_method', {})
        elif user_type == 'vendor':
            user_dict['vendor_name'] = kwargs.get('vendor_name', '')

        return user_dict


class Group:
    '''
    Group model
    '''
    def __init__(self, group_data):
        self.id = str(group_data.get('_id', ''))
        self.name = group_data.get('name', '')
        self.creator_id = str(group_data.get('creator_id', ''))
        self.members = [str(m) for m in group_data.get('members', [])]
        self.active_bill_id = (
            str(group_data.get('active_bill_id', ''))
            if group_data.get('active_bill_id') else None
        )
        self.active = group_data.get('active', True)
        # self.created_at = group_data.get('created_at', datetime.utcnow())


class Bill:
    '''
    Bill model
    '''
    def __init__(self, bill_data):
        self.id = str(bill_data.get('_id', ''))
        self.vendor_id = str(bill_data.get('vendor_id', ''))
        # self.group_id = str(bill_data.get('group_id', ''))
        self.table_number = str(bill_data.get('table_number', ''))
        self.contents = bill_data.get('contents', [])
        self.subtotal = bill_data.get('subtotal', 0.0)
        self.status = bill_data.get('status', 'pending')
        self.session_code = bill_data.get('session_code', '')
        # self.estimated_total = bill_data.get('estimated_total', 0.0)
        # self.final_total = bill_data.get('final_total', 0.0)
        self.created_at = bill_data.get(
            'created_at', datetime.now(pytz.timezone('US/Eastern'))
        )
        # self.updated_at = bill_data.get('updated_at', datetime.utcnow())


class Payment:
    '''
    Payment model
    '''
    def __init__(self, payment_data):
        self.id = str(payment_data.get('_id', ''))
        self.bill_id = str(payment_data.get('bill_id', ''))
        self.user_id = str(payment_data.get('user_id', ''))
        self.amount = payment_data.get('amount', 0.0)
        self.status = payment_data.get('status', 'pending')
        self.payment_method = payment_data.get('payment_method', {})
        self.items_paid = payment_data.get('items_paid', [])
        # self.created_at = payment_data.get('created_at', datetime.utcnow())
        self.completed_at = payment_data.get('completed_at', None)

        # self.authorization_hold = payment_data.get(
        #     'authorization_hold', None
        # )
        # self.planned_amount = payment_data.get('planned_amount', 0.0)
        # self.captured_amount = payment_data.get('captured_amount', 0.0)
        # self.hold_status = payment_data.get('hold_status', None)


class OrderItem:
    '''
    individually ordered items
    '''
    def __init__(self, item_data):
        self.id = str(item_data.get('_id', ''))
        self.bill_id = str(item_data.get('bill_id', ''))
        self.name = item_data.get('name', '')
        self.price = item_data.get('price', 0.0)
        self.quantity = item_data.get('quantity', 1)
        self.assigned_to = item_data.get('assigned_to', [])  # user_ids
        self.split_type = item_data.get('split_type', 'equal')
