import unittest
from unittest.mock import MagicMock, patch
import json

from state import TriageState
import github_client
from agent import TriageAgent

class TestBugTriageOffline(unittest.TestCase):
    def setUp(self):
        # Sample mock data
        self.mock_issue = {
            "title": "TypeError: Cannot read properties of undefined (reading 'token')",
            "body": "The app crashes in the auth middleware when the Authorization header is missing.",
            "comments": [
                "I am getting the same error on my dev machine.",
                "Looks like the check on line 12 is failing because token is undefined."
            ]
        }
        self.mock_repo_tree = [
            "package.json",
            "README.md",
            "src/middleware/auth.py",
            "src/routes/user.py",
            "src/controllers/auth_controller.py",
            "static/styles.css",
            "node_modules/express/index.js",
            "venv/lib/python3.8/site-packages/requests/api.py"
        ]

    def test_triage_state_serialization(self):
        """Verifies state serialization to/from json operates correctly."""
        state = TriageState(
            url="https://github.com/mock-owner/mock-repo/issues/101",
            issue=self.mock_issue,
            repo_tree=self.mock_repo_tree
        )
        
        # Verify default initialized values
        self.assertEqual(state.current_step, "initialized")
        self.assertIsNone(state.classification)
        self.assertIsNone(state.error)

        # Serialize to JSON and parse it back
        serialized = state.to_json()
        data = json.loads(serialized)
        
        self.assertEqual(data["url"], "https://github.com/mock-owner/mock-repo/issues/101")
        self.assertEqual(data["issue"]["title"], "TypeError: Cannot read properties of undefined (reading 'token')")
        self.assertEqual(data["current_step"], "initialized")

    def test_github_client_url_parsing(self):
        """Validates that issue and repo URL parsers extract correct fields."""
        # Test issue URL parsing
        url = "https://github.com/google/google-genai/issues/123"
        owner, repo, number = github_client.parse_issue_url(url)
        self.assertEqual(owner, "google")
        self.assertEqual(repo, "google-genai")
        self.assertEqual(number, "123")

        # Invalid issue URL should raise ValueError
        with self.assertRaises(ValueError):
            github_client.parse_issue_url("https://github.com/invalid-url")

        # Test repo URL parsing
        repo_url = "https://github.com/Mourya20/FinTrack--Personal-Finance-Tracker"
        owner_repo, repo_name = github_client.parse_repo_url(repo_url)
        self.assertEqual(owner_repo, "Mourya20")
        self.assertEqual(repo_name, "FinTrack--Personal-Finance-Tracker")

        # Test trailing slashes and subpaths
        owner_repo_2, repo_name_2 = github_client.parse_repo_url("https://github.com/Mourya20/FinTrack--Personal-Finance-Tracker/pulls")
        self.assertEqual(owner_repo_2, "Mourya20")
        self.assertEqual(repo_name_2, "FinTrack--Personal-Finance-Tracker")

        with self.assertRaises(ValueError):
            github_client.parse_repo_url("https://github.com/invalid")

    @patch("requests.get")
    def test_github_client_get_open_issues(self, mock_get):
        """Validates get_open_issues fetches open issues while filtering out pull requests."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = [
            {"number": 1, "title": "A real bug", "html_url": "https://github.com/mock/repo/issues/1"},
            {"number": 2, "title": "A pull request", "html_url": "https://github.com/mock/repo/pull/2", "pull_request": {}},
            {"number": 3, "title": "Another bug", "html_url": "https://github.com/mock/repo/issues/3"}
        ]
        mock_get.return_value = mock_response

        issues = github_client.get_open_issues("mock-owner", "mock-repo", token="dummy")
        self.assertEqual(len(issues), 2)
        self.assertEqual(issues[0]["number"], 1)
        self.assertEqual(issues[0]["title"], "A real bug")
        self.assertEqual(issues[1]["number"], 3)

    def test_github_client_prioritization(self):
        """Checks file tree filtering and prioritization logic."""
        files = [
            "node_modules/express/lib/router/index.js",
            "venv/bin/activate",
            "src/middleware/auth.py",
            "src/routes/user.py",
            "static/images/logo.png",
            "README.md",
            "package.json"
        ]
        prioritized = github_client.prioritize_and_filter_files(files, limit=5)
        
        # Verify node_modules, venv, and images are ignored
        self.assertNotIn("node_modules/express/lib/router/index.js", prioritized)
        self.assertNotIn("venv/bin/activate", prioritized)
        self.assertNotIn("static/images/logo.png", prioritized)
        
        # Verify root files and priority prefixes are included
        self.assertIn("src/middleware/auth.py", prioritized)
        self.assertIn("src/routes/user.py", prioritized)
        self.assertIn("README.md", prioritized)
        self.assertIn("package.json", prioritized)

    @patch("requests.get")
    def test_github_client_fallback_on_403(self, mock_get):
        """Validates fallback to top-level contents endpoint when recursive tree returns 403."""
        # Setup mock responses: first response (recursive tree) is 403, second response (contents) is 200
        mock_tree_response = MagicMock()
        mock_tree_response.status_code = 403
        
        mock_contents_response = MagicMock()
        mock_contents_response.status_code = 200
        mock_contents_response.json.return_value = [
            {"name": "package.json", "path": "package.json", "type": "file"},
            {"name": "src", "path": "src", "type": "dir"},
            {"name": "README.md", "path": "README.md", "type": "file"}
        ]
        
        mock_get.side_effect = [
            MagicMock(status_code=200, json=lambda: {"default_branch": "main"}), # repo details call
            mock_tree_response, # recursive tree call
            mock_contents_response # contents fallback call
        ]

        result = github_client.get_repo_tree("mock-owner", "mock-repo", token="dummy")
        
        # Verify it falls back and returns file paths
        self.assertIn("package.json", result)
        self.assertIn("README.md", result)
        self.assertIn("src/", result) # directory representation
        self.assertEqual(len(result), 3)

    def test_agent_reasoning_loop_mocked(self):
        """Simulates the 4-step reasoning agent loop using mocked Gemini client outputs."""
        # Create agent with mock key
        agent = TriageAgent(api_key="mock-gemini-key")
        
        # Setup mock response structures
        mock_classify_text = json.dumps({
            "severity": "High",
            "category": "Security",
            "affected_layer": "Auth Middleware",
            "confidence": 0.95,
            "reasoning": "Missing validation on auth token header leads to uncaught type error."
        })
        mock_locate_text = json.dumps({
            "relevant_files": ["src/middleware/auth.py"],
            "reasoning": "The stack trace points directly to auth middleware."
        })
        mock_suggest_text = json.dumps({
            "debug_steps": [
                {
                    "step_number": 1,
                    "title": "Inspect Authorization extraction",
                    "description": "Locate line where request.headers.get('Authorization') is defined.",
                    "target_files": ["src/middleware/auth.py"]
                },
                {
                    "step_number": 2,
                    "title": "Add None guard",
                    "description": "Add safe check if authorization header is not present.",
                    "target_files": ["src/middleware/auth.py"]
                },
                {
                    "step_number": 3,
                    "title": "Run test case",
                    "description": "Execute backend tests without auth header and verify it fails with 401 instead of crashing.",
                    "target_files": ["src/middleware/auth.py"]
                }
            ]
        })
        mock_respond_text = "### Bug Report Triage Summary\n\nThanks for reporting! We suspect `src/middleware/auth.py` is the cause."

        # Setup mock client & models response calls
        mock_client = MagicMock()
        
        classify_resp = MagicMock()
        classify_resp.text = mock_classify_text
        
        locate_resp = MagicMock()
        locate_resp.text = mock_locate_text
        
        suggest_resp = MagicMock()
        suggest_resp.text = mock_suggest_text
        
        respond_resp = MagicMock()
        respond_resp.text = mock_respond_text
        
        mock_client.models.generate_content.side_effect = [
            classify_resp,
            locate_resp,
            suggest_resp,
            respond_resp
        ]
        
        # Inject the mock client
        agent.client = mock_client

        # Create initial state
        state = TriageState(
            url="https://github.com/mock-owner/mock-repo/issues/101",
            issue=self.mock_issue,
            repo_tree=self.mock_repo_tree
        )
        
        # Run agent triage loop
        final_state = agent.run_all(state)
        
        # Assert state transitions and properties
        self.assertEqual(final_state.current_step, "completed")
        self.assertIsNone(final_state.error)
        
        # Validate classification
        self.assertEqual(final_state.classification["severity"], "High")
        self.assertEqual(final_state.classification["category"], "Security")
        self.assertEqual(final_state.classification["confidence"], 0.95)
        
        # Validate located files
        self.assertEqual(final_state.located_files["relevant_files"], ["src/middleware/auth.py"])
        
        # Validate debug steps
        self.assertEqual(len(final_state.debug_plan["debug_steps"]), 3)
        self.assertEqual(final_state.debug_plan["debug_steps"][0]["title"], "Inspect Authorization extraction")
        
        # Validate draft response
        self.assertIn("Thanks for reporting!", final_state.draft_response)

if __name__ == "__main__":
    unittest.main()
