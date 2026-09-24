from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph
from tools.webSearch import search
from tools.postToFacebookPage import get_facebook_page_info, post_content
from models import model
import prompts.birdsPrompt
import json

with open("config.json", encoding="utf-8") as config_file:
    config = json.load(config_file)
url=config.get("website_url")
system_prompt = prompts.birdsPrompt.system_prompt
user_prompt = prompts.birdsPrompt.user_prompt

class FacebookPostState(TypedDict, total=False):
    system_prompt: str
    user_prompt: str
    search_query: str
    social_account_id: str
    search_result: str
    generated_content: str
    page_response: dict[str, Any]
    page_id: str
    access_token: str
    post_result: Any


def search_node(state: FacebookPostState) -> FacebookPostState:
    search_result = search.invoke({"query": state["search_query"]})
    return {"search_result": search_result}


def generate_content_node(state: FacebookPostState) -> FacebookPostState:
    response = model.invoke(
        [
            {"role": "system", "content": state["system_prompt"]},
            {
                "role": "user",
                "content": (
                    f"{state['user_prompt']}\n\n"
                    f"Use these search results as factual context:\n{state['search_result']}"
                ),
            },
        ]
    )
    return {"generated_content": response.content}


def get_page_info_node(state: FacebookPostState) -> FacebookPostState:
    social_account_id = state.get("social_account_id")
    if not social_account_id:
        raise RuntimeError("social_account_id is required to load a Facebook page")

    page_data = get_facebook_page_info.invoke(
        {"social_account_id": social_account_id}
    )
    if not page_data:
        raise RuntimeError("get_facebook_page_info returned no page data")

    page_id = page_data.get("id")
    access_token = page_data.get("access_token")
    if not page_id or not access_token:
        raise RuntimeError("Facebook page data is missing an ID or access token")

    return {
        "page_response": page_data,
        "page_id": page_id,
        "access_token": access_token,
    }


def post_content_node(state: FacebookPostState) -> FacebookPostState:
    post_result = post_content.invoke(
        {
            "page_id": state["page_id"],
            "access_token": state["access_token"],
            "content": state["generated_content"],
        }
    )
    return {"post_result": post_result}


workflow = StateGraph(FacebookPostState)
workflow.add_node("search", search_node)
workflow.add_node("generate_content", generate_content_node)
workflow.add_node("get_facebook_page_info", get_page_info_node)
workflow.add_node("post_content", post_content_node)

workflow.add_edge(START, "search")
workflow.add_edge("search", "generate_content")
workflow.add_edge("generate_content", "get_facebook_page_info")
workflow.add_edge("get_facebook_page_info", "post_content")
workflow.add_edge("post_content", END)

graph = workflow.compile()

if __name__ == "__main__":
    result = graph.invoke(
        {
            "system_prompt": system_prompt,
            "user_prompt": user_prompt,
            "search_query": (
                "BIRDS Bangalore Institute respiratory diseases sleep disorders "
                "clinic services pulmobirds.in"
            ),
            "social_account_id": "SOCIAL_ACCOUNT_UUID",
        }
    )
    
    print(result)
