import requests

page_id = "1315569881639633"
page_access_token = "EAANSYy8k52YBSUEMnaCnRYfyFPbksRrtk0WL1PN7rmuBVY3rHZAW3ZCUnfPZBhedZAPM66RxEZCyZAQjMsb7cUnLaILeDmVhIeWvSdEgRZCjUgRCZCOsJbgZAwuiiWy6uD6m4z6fYZBmy8yQeIylNXRR37TQc5qhVDgt3Dd4s12Gdnz5ZBvjbZAn5tLJBQc4svvmEmYVDB4jwZA6ZBX8AAGjAH4lNLbVxAlUELBRwexfZCDKbbF"

url = f"https://graph.facebook.com/v26.0/{page_id}/feed"

data={
    "message": "Hello, this is a test post from the Facebook Graph API!",
    "access_token": page_access_token
}

response = requests.post(url, data=data)

print(response.status_code)
print(response.json())
