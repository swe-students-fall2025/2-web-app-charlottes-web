'''
generates random codes for bills, groups, etc.
'''
import random
import string
from app import app

CODE_LENGTH = app.config.get('CODE_LENGTH', 6)


def generate_code():
    return "".join(
        random.choices(string.ascii_uppercase + string.digits, k=CODE_LENGTH)
    )
