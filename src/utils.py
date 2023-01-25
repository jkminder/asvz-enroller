from cryptography.fernet import Fernet


def load_token(file):
    with open(file, 'r') as f:
        return f.read().strip()

def encrypt(text, token):
    fernet = Fernet(token.encode())
    encMessage = fernet.encrypt(text.encode())
    return encMessage

def decrypt(text, token):
    fernet = Fernet(token.encode())
    decMessage = fernet.decrypt(text).decode()
    return decMessage
