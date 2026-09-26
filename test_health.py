from mutual_2_api import app

with app.test_client() as client:
    response = client.get('/health')
    print("Status:", response.status_code)
    print("Data:", response.data)
