import uuid
from dataclasses import dataclass

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


class CardNetwork:
    def check_cvc(*args):
        '''
        Simulated check to see if cvc is valid for card.
        Usually done by the bank but done here for simplicity
        '''
        return True

    def register_token(self, card, cvc):
        '''
        Register a token representing a card
        '''
        mongo.db.cards.create_index([("token", 1)], unique=True)
        if self.check_cvc(card, cvc):
            mongo.db.cards.insert_one(card.to_dict())
        else:
            raise PaymentError("Invalid cvc")

    def delete_token(self, token):
        '''
        Simulate deleting a saved card
        '''
        mongo.db.cards.delete_one({"token": token})


demo_card_network = CardNetwork()
demo_payment_provider = PaymentProvider(demo_card_network)
