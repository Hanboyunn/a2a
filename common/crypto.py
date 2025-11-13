import json, hashlib, base64
from Crypto.PublicKey import RSA
from Crypto.Signature import pkcs1_15
from Crypto.Hash import SHA256

KEY_PATH = "tools/private.pem"
PUB_PATH = "tools/public.pem"

def load_secret():
    with open(KEY_PATH, "rb") as f:
        return RSA.import_key(f.read())

def load_public():
    with open(PUB_PATH, "rb") as f:
        return RSA.import_key(f.read())

def params_hash(params: dict) -> str:
    raw = json.dumps(params, sort_keys=True)
    return hashlib.sha256(raw.encode()).hexdigest()

def sign_msg(msg: dict, fields: list) -> str:
    secret = load_secret()
    raw = "".join(str(eval_field(msg, f)) for f in fields)
    h = SHA256.new(raw.encode())
    return base64.b64encode(pkcs1_15.new(secret).sign(h)).decode()

def verify_msg(msg: dict) -> bool:
    try:
        fields = msg["signature_fields"]
        raw = "".join(str(eval_field(msg, f)) for f in fields)
        h = SHA256.new(raw.encode())
        pk = load_public()
        pkcs1_15.new(pk).verify(h, base64.b64decode(msg["signature"]))
        return True
    except Exception:
        return False

def eval_field(obj, path):
    cur = obj
    for p in path.split("."):
        cur = cur.get(p) if isinstance(cur, dict) else None
    return cur

def load_private_key(key_path: str):
    """Load private key from file (alias for load_secret for compatibility)"""
    with open(key_path, "rb") as f:
        return RSA.import_key(f.read())

def sign_message(private_key, message_str: str) -> str:
    """Sign a message string directly (for compatibility with old code)"""
    h = SHA256.new(message_str.encode())
    return base64.b64encode(pkcs1_15.new(private_key).sign(h)).decode()