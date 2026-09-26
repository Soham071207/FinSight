import sys
import traceback
from mutual_2_api import app

with app.test_client() as client:
    try:
        response = client.post('/analyze', json={
            "assets": ["119597", "120503"],
            "inv_mode": 1,
            "base_sip": 10000,
            "target_years": 5,
            "future_years": 10
        })
        print(f"Status Code: {response.status_code}")
        if response.status_code != 200:
            print("Error data:", response.data.decode('utf-8'))
        else:
            json_data = response.get_json()
            if "error" in json_data:
                print("Error:", json_data["error"])
            else:
                print("Success! Results length:", len(json_data.get("results", [])))
    except Exception as e:
        traceback.print_exc()
