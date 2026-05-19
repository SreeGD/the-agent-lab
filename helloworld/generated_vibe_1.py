import hashlib

text = 'hello world'
hash_value = hashlib.sha256(text.encode()).hexdigest()
print(hash_value)