
import os
import deepgram

path = os.path.join(os.path.dirname(deepgram.__file__), 'listen')
print(f"Listing {path}")
for root, dirs, files in os.walk(path):
    for file in files:
        print(os.path.join(root, file))
