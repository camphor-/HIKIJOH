import requests

CURTAIN_URL = "http://m5atom.local"

def open_curtain():
    requests.get(CURTAIN_URL)

def close_curtain():
    requests.get(CURTAIN_URL)
