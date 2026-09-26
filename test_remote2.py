import requests

url = "https://mutual-funds-api-5vvi.onrender.com/analyze"
payload = {
    "assets": ["119597", "120503"],
    "inv_mode": 1,
    "base_sip": 10000,
    "target_years": 5,
    "future_years": 10
}
response = requests.post(url, json=payload, timeout=30)
data = response.json()
if "results" in data and len(data["results"]) > 0:
    print(list(data["results"][0].keys()))
