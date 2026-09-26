import requests

url = "https://mutual-funds-api-5vvi.onrender.com/analyze"
payload = {
    "assets": ["119597"],
    "inv_mode": 1,
    "base_sip": 10000,
    "target_years": 5,
    "future_years": 10
}
try:
    response = requests.post(url, json=payload, timeout=30)
    print("Status:", response.status_code)
    print("Response:", response.text[:500])
except Exception as e:
    print("Error:", e)
