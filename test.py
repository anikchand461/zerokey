import requests
print(requests.post(
    "http://localhost:8000/proxy/u/groq/groq",
    headers={"Authorization":"Bearer apikey-groq-groq","Content-Type":"application/json"},
    json={"model":"llama-3.3-70b-versatile","messages":[{"role":"user","content":input("Message: ")}]}
).json())
