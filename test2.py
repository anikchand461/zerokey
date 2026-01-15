import requests

prompts = [
    "Hi", "Hello", "Explain AI", "What is ML?", "Define API",
    "What is REST?", "Docker?", "Kubernetes?", "CI/CD?", "Cloud computing?",
    "What is Linux?", "What is Git?", "Explain HTTP", "TCP vs UDP",
    "What is JSON?", "Explain OAuth", "What is JWT?", "What is caching?",
    "SQL vs NoSQL", "What is Redis?",
    "Explain DNS", "What is CDN?", "What is load balancing?"
]

for p in prompts:
    print(requests.post(
        "http://localhost:8000/proxy/u/openrouter/cbhor",
        headers={
            "Authorization": "Bearer apikey-openrouter-cbhor",
            "Content-Type": "application/json"
        },
        json={
            "model": "openrouter/auto",
            "messages": [{"role": "user", "content": p}]
        }
    ).json())
