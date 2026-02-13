import hashlib

with open("core.py", "rb") as f:
    print(hashlib.sha256(f.read()).hexdigest())
    
with open("index.html", "rb") as f:
    print(hashlib.sha256(f.read()).hexdigest())