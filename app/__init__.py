import os
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask
from flask_login import LoginManager
from flask_pymongo import PyMongo

TAX_RATE = 8
CODE_LENGTH = 6

# Load .env from parent directory (override existing env vars)
basedir = Path(__file__).parent.parent
load_dotenv(basedir / '.env', override=True)

# Set template and static folders to parent directory
app = Flask(__name__,
            template_folder='../templates',
            static_folder='../static')
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY')
app.config['MONGO_URI'] = os.getenv('MONGO_URI')

mongo = PyMongo(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'auth.login'

from app.models import User


@login_manager.user_loader
def load_user(user_id):
    from bson.objectid import ObjectId
    user_data = mongo.db.users.find_one({'_id': ObjectId(user_id)})
    if user_data:
        return User(user_data)
    return None

from app.blueprints.auth import auth_bp
from app.blueprints.bills import customer_bill_bp, vendor_bill_bp
from app.blueprints.customer import customer_bp
from app.blueprints.vendor import vendor_bp

app.register_blueprint(auth_bp)
app.register_blueprint(customer_bill_bp)
app.register_blueprint(vendor_bill_bp)
app.register_blueprint(customer_bp)
app.register_blueprint(vendor_bp)

from app import routes
