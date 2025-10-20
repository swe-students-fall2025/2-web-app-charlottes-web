import uuid
from dataclasses import dataclass
from datetime import datetime

from cryptography.fernet import Fernet

from app import mongo

# This would never be stored IRL like this, and would go in a .env file
# It is only left here because nobody wants to type 32 characters for a demo
KEY = "_ePjcR6o75sFBXgOBFkoBKpSzi-06xKN6Vyw3UaYzjA="
fernet = Fernet(KEY.encode())


@dataclass
class Card:
    token: str
    card_number: str
    expiry_date: str
    cardholder_name: str

    def to_dict(self):
        return {
            "token": self.token,
            "card_number": self.card_number,
            "expiry_date": self.expiry_date,
            "cardholder_name": self.cardholder_name
        }


class PaymentError(Exception):
    pass


class PaymentProvider:
    def __init__(self, card_network):
        self.card_network = card_network

    def register(self, card):
        '''
        Simulate payment provider returning a token
        representing a payment method
        '''
        if len(card["card_number"]) != 16:
            raise ValueError("Invalid card number")
        if len(card["cvc"]) != 3:
            raise ValueError("Invalid CVC")

        new_token = str(uuid.uuid4())
        new_card = Card(
            token=new_token,
            card_number=fernet.encrypt(card["card_number"].encode()),
            expiry_date=card["expiry_date"],
            cardholder_name=card["cardholder_name"]
        )

        try:
            self.card_network.register_token(new_card, card["cvc"])
            return new_token
        except PaymentError:
            raise

    def delete_card(self, token):
        '''
        Simulate deleting a saved card from card network
        '''
        self.card_network.delete_token(token)

    def make_payment(self, card, cvc):
        '''
        Make a payment with a card
        '''
        if isinstance(card, dict):
            if len(card["card_number"]) != 16:
                raise ValueError("Invalid card number")
        if len(cvc) != 3:
            raise ValueError("Invalid CVC")

        try:
            self.card_network.validate_card(card, cvc)
            self.card_network.make_payment(card, cvc)
        except PaymentError:
            raise


class CardNetwork:
    def check_cvc(*args):
        '''
        Simulated check to see if cvc is valid for card.
        Usually done by the bank but done here for simplicity
        '''
        return

    def check_expiry(self, expiry_date):
        '''
        Check if card is expired. Throw error if so.
        '''
        today = datetime.today()
        expiry_date = datetime.strptime(expiry_date, "%Y-%m")
        if (expiry_date.year, expiry_date.month) < (today.year, today.month):
            raise PaymentError("Card is expired")

    def register_token(self, card, cvc):
        '''
        Register a token representing a card
        '''
        mongo.db.cards.create_index([("token", 1)], unique=True)
        try:
            self.check_cvc(card, cvc)
            self.check_expiry(card.expiry_date)
        except PaymentError:
            raise
        mongo.db.cards.insert_one(card.to_dict())

    def delete_token(self, token):
        '''
        Simulate deleting a saved card
        '''
        mongo.db.cards.delete_one({"token": token})

    def validate_card(self, card, cvc):
        '''
        Validate the card being used is valid
        '''
        # Token
        if isinstance(card, str):
            card = mongo.db.cards.find_one({"token": card})
            if not card:
                raise PaymentError("Card not found")
            if len(fernet.decrypt(card["card_number"]).decode()) != 16:
                raise PaymentError("Invalid card number")

            try:
                self.check_cvc(card, cvc)
                self.check_expiry(card["expiry_date"])
            except PaymentError:
                raise

    def make_payment(self, card, cvc):
        '''
        Simulated function call to make a payment
        This would be done at the bank level but is simulated here
        '''
        # Token
        if isinstance(card, str):
            card = mongo.db.cards.find_one({"token": card})
            if not card:
                raise PaymentError("Card not found")
            card["card_number"] = fernet.decode(card["card_number"]).decode()
            if len(card["card_number"]) != 16:
                raise PaymentError("Invalid card number")

        try:
            self.check_cvc(card, cvc)
            self.check_expiry(card["expiry_date"])
        except PaymentError:
            raise


demo_card_network = CardNetwork()
demo_payment_provider = PaymentProvider(demo_card_network)
