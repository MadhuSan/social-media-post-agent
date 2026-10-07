from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph
from tools.webSearch import search
from tools.postToFacebookPage import save_content_draft
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
    draft_result: dict[str, str]


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


def save_draft_node(state: FacebookPostState) -> FacebookPostState:
    social_account_id = state.get("social_account_id")
    if not social_account_id:
        raise RuntimeError("social_account_id is required to save a draft")

    draft_result = save_content_draft.invoke(
        {
            "social_account_id": social_account_id,
            "content": state["generated_content"],
        }
    )
    return {"draft_result": draft_result}


workflow = StateGraph(FacebookPostState)
workflow.add_node("search", search_node)
workflow.add_node("generate_content", generate_content_node)
workflow.add_node("save_draft", save_draft_node)

workflow.add_edge(START, "search")
workflow.add_edge("search", "generate_content")
workflow.add_edge("generate_content", "save_draft")
workflow.add_edge("save_draft", END)

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
            #"social_account_id": "987637f9-8cb5-4e4f-b18d-d1b2d02bc6dd",
        }
    )
    
    print(result)
