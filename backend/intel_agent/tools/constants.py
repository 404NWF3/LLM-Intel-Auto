"""Shared in-process MCP naming constants without tool-construction imports."""

SERVER_NAME = "intel_sources"

SOURCE_TOOL_NAMES = {
    "search_nvd": "nvd_cve_api",
    "search_arxiv": "arxiv_api",
    "search_cisa_kev": "cisa_kev_json",
    "search_osv": "osv_dev_api",
    "search_hackernews": "hackernews",
    "search_hf_forum": "discourse",
    "search_github_issues": "github_issues",
    "search_reddit": "reddit",
}
