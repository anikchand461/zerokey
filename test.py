import requests

msgs = [
    "What is machine learning?",
    "Explain Docker in simple terms",
    "What is the difference between REST and GraphQL?",
    "How does Kubernetes work?",
    "What is an API gateway?",
    "Explain CI/CD pipeline",
    "What is vector database?",
    "Difference between TCP and UDP",
    "What is prompt engineering?",
    "How does LLM inference work?"
]*2

for m in msgs:
    print(requests.post(
        "http://localhost:8000/proxy/u/groq/cbhgroq",
        headers={"Authorization":"Bearer apikey-groq-cbhgroq","Content-Type":"application/json"},
        json={"model":"groq/compound-mini","messages":[{"role":"user","content":m}]}
    ).json())


