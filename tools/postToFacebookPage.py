import requests
import dotenv
import json
import os
from langchain_community.tools import tool

@tool
def get_facebook_page_info():
    "Get the Facebook page information using the Graph API."

    try:
        dotenv.load_dotenv()
        user_access_token = os.getenv("USER_ACCESS_TOKEN")
        if not user_access_token:
            raise ValueError("USER_ACCESS_TOKEN is not configured")

        with open("config.json", encoding="utf-8") as config_file:
            config = json.load(config_file)

        url = config.get("facebook_url")
        if not url:
            raise ValueError("facebook_url is not configured")

        response = requests.get(
            url,
            params={"access_token": user_access_token},
            timeout=30,
        )
        try:
            response_data = response.json()
        except json.JSONDecodeError:
            response_data = {"raw_response": response.text}

        if not response.ok:
            facebook_error = response_data.get("error", {})
            error_message = facebook_error.get("message", response.text)
            error_code = facebook_error.get("code", response.status_code)
            raise RuntimeError(
                f"Facebook API error {error_code}: {error_message}"
            )

        print(response_data)
        return response_data
    except (FileNotFoundError, json.JSONDecodeError, ValueError) as error:
        print(f"Configuration error: {error}")
    except requests.exceptions.RequestException as error:
        print(f"Facebook API request failed: {error}")
    except RuntimeError as error:
        print(error)
    except TypeError as error:
        print(f"Invalid Facebook API response: {error}")

@tool
def extract_page_info(response_data):
    "Extract relevant page information from the Facebook API response."
    # Extract the target elements safely
    if isinstance(response_data, dict) and isinstance(response_data.get("data"), list) and response_data["data"]:
        page_data = response_data["data"][0]  # Get the first page in the list
        
        page_id = page_data.get("id")
        access_token = page_data.get("access_token")

        print(f"Extracted Page ID: {page_id}")
        print(f"Extracted Access Token: {access_token}")

        return page_id, access_token
    else:
        print("No page data found in the response.")

@tool
def post_content(page_id,access_token,content):
    "Post content to the Facebook page using the Graph API. Content will be provided by the LLM by previous tool call"

    if content is None:
        content = "Content is provided by LLM."
    url = f"https://graph.facebook.com/v26.0/{page_id}/feed"

    data={
    "message": content,
    "access_token": access_token
    }

    requests.post(url, data=data)
    


if __name__ == "__main__":
    response_data = get_facebook_page_info()
    if response_data:
        page_id, access_token = extract_page_info(response_data)
        post_content(page_id, access_token, "Content is provided by LLM.")

