import logging

from ddgs.exceptions import DDGSException
from langchain_community.tools import DuckDuckGoSearchRun
from langchain_community.tools import tool

logger = logging.getLogger(__name__)


@tool
def search(query: str) -> str:
    "Search the web using DuckDuckGo and return the results as a string."
    search_tool = DuckDuckGoSearchRun()
    try:
        return search_tool.invoke(query)
    except DDGSException as error:
        logger.warning("DuckDuckGo search failed for query %r: %s", query, error)
        return (
            "Web search is currently unavailable. Generate a general, topic-relevant "
            "post without claiming current or specific facts that cannot be verified."
        )
