from langchain_community.tools import DuckDuckGoSearchRun
from langchain_community.tools import tool

@tool
def search(query: str) -> str:
    "Search the web using DuckDuckGo and return the results as a string."
    search_tool = DuckDuckGoSearchRun()
    result = search_tool.invoke(query)
    return result



