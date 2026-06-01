import re
import requests
from typing import List, Dict, Any, Tuple, Optional

def parse_issue_url(url: str) -> Tuple[str, str, str]:
    """
    Parses a GitHub issue URL to extract owner, repo, and issue number.
    Accepts format: https://github.com/owner/repo/issues/123
    """
    match = re.search(r"github\.com/([^/]+)/([^/]+)/issues/(\d+)", url)
    if not match:
        raise ValueError(
            "Invalid GitHub issue URL. Please use the format: "
            "https://github.com/owner/repo/issues/123"
        )
    return match.group(1), match.group(2), match.group(3)

def parse_repo_url(url: str) -> Tuple[str, str]:
    """
    Parses a GitHub repository URL to extract owner and repo name.
    Accepts format: https://github.com/owner/repo
    """
    match = re.search(r"github\.com/([^/]+)/([^/]+)", url)
    if not match:
        raise ValueError(
            "Invalid GitHub repository URL. Please use the format: "
            "https://github.com/owner/repo"
        )
    owner = match.group(1)
    repo = match.group(2)
    # Strip any trailing parts like subpaths or .git extension
    if repo.endswith(".git"):
        repo = repo[:-4]
    # In case the URL is an issue URL or subpath, extract only the repo name
    if "/" in repo:
        repo = repo.split("/")[0]
    return owner, repo

def get_open_issues(owner: str, repo: str, token: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Fetches the 15 most recent open issues for a given repository.
    """
    headers = get_headers(token)
    api_url = f"https://api.github.com/repos/{owner}/{repo}/issues?state=open&per_page=15"
    response = requests.get(api_url, headers=headers)
    if response.status_code == 403:
        raise Exception(
            "GitHub API Rate Limit Exceeded or Forbidden. "
            "Please provide a GITHUB_TOKEN to list issues."
        )
    response.raise_for_status()
    
    items = response.json()
    issues = []
    for item in items:
        if isinstance(item, dict) and "pull_request" not in item:
            issues.append({
                "number": item.get("number"),
                "title": item.get("title", "") or "",
                "html_url": item.get("html_url", "") or ""
            })
    return issues

def get_headers(token: Optional[str] = None) -> Dict[str, str]:
    """Generates standard headers for GitHub API requests."""
    headers = {
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": "BugTriageAgent/1.0"
    }
    if token:
        # Strip token of extra whitespace/newlines
        clean_token = token.strip()
        if clean_token:
            headers["Authorization"] = f"token {clean_token}"
    return headers

def get_rate_limit(token: Optional[str] = None) -> Dict[str, Any]:
    """Fetches the current GitHub API rate limit status."""
    headers = get_headers(token)
    api_url = "https://api.github.com/rate_limit"
    response = requests.get(api_url, headers=headers)
    if response.status_code == 403:
        raise Exception("GitHub API rate limit check blocked. Please verify your token.")
    response.raise_for_status()
    data = response.json()
    core = data.get("resources", {}).get("core", {})
    return {
        "limit": core.get("limit", 0),
        "remaining": core.get("remaining", 0),
        "reset": core.get("reset", 0),
        "used": core.get("used", 0),
    }

def get_issue(url: str, token: Optional[str] = None) -> Dict[str, Any]:
    """
    Fetches GitHub issue details (title, body) and the first 5 comments.
    """
    owner, repo, issue_num = parse_issue_url(url)
    headers = get_headers(token)
    
    # 1. Fetch issue details
    issue_api_url = f"https://api.github.com/repos/{owner}/{repo}/issues/{issue_num}"
    response = requests.get(issue_api_url, headers=headers)
    
    if response.status_code == 403:
        raise Exception(
            "GitHub API Rate Limit Exceeded or Forbidden. "
            "Please provide a GITHUB_TOKEN in your environment configuration to raise limits."
        )
    elif response.status_code == 404:
        raise Exception(f"GitHub issue not found at URL: {url}. Please verify the URL and permissions.")
    response.raise_for_status()
    
    issue_data = response.json()
    
    # 2. Fetch first 5 comments
    comments: List[str] = []
    comments_url = issue_data.get("comments_url")
    if comments_url:
        # Request comments (limit to first page, 5 per page)
        comments_response = requests.get(f"{comments_url}?per_page=5", headers=headers)
        if comments_response.status_code == 200:
            comments_data = comments_response.json()
            comments = [c.get("body", "") or "" for c in comments_data if isinstance(c, dict)]

    return {
        "title": issue_data.get("title", "") or "",
        "body": issue_data.get("body", "") or "",
        "comments": comments,
        "owner": owner,
        "repo": repo,
        "number": issue_num
    }

def prioritize_and_filter_files(file_paths: List[str], limit: int = 300) -> List[str]:
    """
    Filters out noise files and prioritizes specific code paths, capping at limit.
    """
    # Noise/ignore patterns
    ignore_prefixes = (
        ".git/", "node_modules/", "venv/", "env/", "dist/", "build/",
        "__pycache__/", ".next/", ".idea/", ".vscode/", ".github/",
        "tests/", "test/", "docs/", "static/", "public/"
    )
    ignore_extensions = (
        ".png", ".jpg", ".jpeg", ".gif", ".ico", ".svg", ".zip", ".tar.gz",
        ".pdf", ".woff", ".woff2", ".eot", ".ttf", ".css", ".scss", ".map",
        ".lock", "-lock.json"
    )

    filtered: List[str] = []
    for p in file_paths:
        p_lower = p.lower()
        if p.startswith(ignore_prefixes) or p_lower.endswith(ignore_extensions):
            continue
        filtered.append(p)

    # Priority directories
    priority_prefixes = (
        "src/", "app/", "routes/", "controllers/", "middleware/", "pages/",
        "lib/", "utils/", "components/", "api/", "services/"
    )

    priority_files: List[str] = []
    other_files: List[str] = []

    for p in filtered:
        # Check if root level file (no slashes) or starts with priority directory prefix
        if "/" not in p or p.startswith(priority_prefixes):
            priority_files.append(p)
        else:
            other_files.append(p)

    # Combine prioritizing the selected categories
    result = priority_files[:limit]
    if len(result) < limit:
        remaining_slots = limit - len(result)
        result.extend(other_files[:remaining_slots])

    return result

def get_repo_tree(owner: str, repo: str, token: Optional[str] = None) -> List[str]:
    """
    Fetches the repository file list. Tries recursive tree API first.
    If rate-limited (403) or error occurs, falls back to non-recursive top-level contents API.
    """
    headers = get_headers(token)
    
    # 1. Fetch repo details to get default branch
    repo_api_url = f"https://api.github.com/repos/{owner}/{repo}"
    try:
        repo_response = requests.get(repo_api_url, headers=headers)
        repo_response.raise_for_status()
        default_branch = repo_response.json().get("default_branch", "main")
    except Exception:
        # Fallback to HEAD if repo details can't be fetched
        default_branch = "HEAD"

    # 2. Try fetching recursive tree
    tree_api_url = f"https://api.github.com/repos/{owner}/{repo}/git/trees/{default_branch}?recursive=1"
    try:
        tree_response = requests.get(tree_api_url, headers=headers)
        if tree_response.status_code == 403:
            # Explicitly raise rate limit error to trigger fallback
            raise PermissionError("Rate limited or forbidden (403) on recursive tree API.")
        
        tree_response.raise_for_status()
        tree_data = tree_response.json()
        
        # Extract file paths from recursive blobs
        paths = [
            item.get("path", "")
            for item in tree_data.get("tree", [])
            if item.get("type") == "blob" and item.get("path")
        ]
        return prioritize_and_filter_files(paths)

    except Exception as e:
        # Fallback routine: call top-level contents endpoint
        contents_api_url = f"https://api.github.com/repos/{owner}/{repo}/contents"
        try:
            contents_response = requests.get(contents_api_url, headers=headers)
            contents_response.raise_for_status()
            contents_data = contents_response.json()
            
            # Non-recursive fallback: fetch paths of root level files/directories
            paths = []
            for item in contents_data:
                path_type = item.get("type")
                path_name = item.get("path", "")
                if path_name:
                    if path_type == "file":
                        paths.append(path_name)
                    elif path_type == "dir":
                        # Add dir as path indicator
                        paths.append(f"{path_name}/")
                        
            return prioritize_and_filter_files(paths)
        except Exception as fallback_err:
            # If fallback also fails, return empty list or raise
            raise Exception(f"Failed to fetch repository tree: {str(e)}. Fallback contents fetch failed: {str(fallback_err)}")
