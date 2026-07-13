import requests

url = "https://api-inference.huggingface.co/models/mistralai/Mistral-7B-Instruct-v0.3"

try:
    r = requests.get(url, timeout=10)
    print(r.status_code)
    print(r.text)
except Exception as e:
    print(e)