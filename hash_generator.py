import hashlib

with open("core.py", "rb") as f:
    print(hashlib.sha256(f.read()).hexdigest())
    
with open("index.html", "rb") as f:
    print(hashlib.sha256(f.read()).hexdigest())
    
import requests
import hashlib

url = "https://raw.githubusercontent.com/Uni44/PFLauncher/main/core.py"

r = requests.get(url)
print(hashlib.sha256(r.content).hexdigest())

import requests
import hashlib

url = "https://raw.githubusercontent.com/Uni44/PFLauncher/main/index.html"

r = requests.get(url)
print(hashlib.sha256(r.content).hexdigest())
