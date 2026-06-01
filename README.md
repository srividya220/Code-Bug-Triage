# BugTriage AI

BugTriage AI is a lightweight Streamlit dashboard for triaging GitHub issues with AI assistance. It fetches issue details and repository metadata, then uses the Gemini model API to:

- classify issue severity and type,
- locate the likely source files,
- create a step-by-step debugging plan,
- draft a maintainer-friendly Markdown response.

This repo is ideal for developers who want a quick way to analyze GitHub bug reports and generate actionable recommendations.

## What This Project Does

The application takes a GitHub repository or issue URL and runs a multi-stage triage workflow:

1. Fetch GitHub issue details and comments.
2. Fetch the repository file tree.
3. Use a Gemini-powered agent to classify the issue.
4. Identify suspect files in the repository.
5. Generate a 3-step debugging plan.
6. Draft a well-structured response for the issue reporter.

## Why It Helps

This tool is useful when you need to:

- quickly understand new bug reports,
- identify likely file locations without manually scanning the repo,
- produce a reproducible debugging plan,
- draft an initial response to maintainers or contributors.

## Project Structure

- `app.py` - Streamlit application and UI wiring.
- `github_client.py` - GitHub API integration for fetching issues, comments, and repository trees.
- `agent.py` - Gemini agent implementation with a structured 4-step reasoning pipeline.
- `prompts.py` - Prompt templates and Pydantic schemas that describe expected AI output formats.
- `state.py` - `TriageState` dataclass used to hold issue, repo, classification, location, and response state.
- `test_triage.py` - Unit tests covering URL parsing, GitHub helper logic, fallback behavior, and offline agent flow.
- `requirements.txt` - Python dependencies needed to run the app.
- `.env` - Example environment file for secrets and configuration.

## Dependencies

- Python 3.14+
- `streamlit`
- `requests`
- `python-dotenv`
- `google-genai`
- `pydantic`

## Setup

1. Open a terminal in the project root.
2. Create and activate a virtual environment:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate
```

3. Install the required packages:

```powershell
pip install -r requirements.txt
```

4. Create or update the `.env` file with your credentials:

```ini
GEMINI_API_KEY=your_gemini_api_key_here
GEMINI_MODEL=gemini-2.5-flash
GITHUB_TOKEN=your_github_token_here
# Optional alternative variable:
GITHUB_PAT=your_github_token_here
```

### Environment variable notes

- `GEMINI_API_KEY` is required.
- `GEMINI_MODEL` defaults to `gemini-2.5-flash` if not set.
- `GITHUB_TOKEN` or `GITHUB_PAT` is optional, but strongly recommended to avoid GitHub API rate limiting.

## How to Run

From the project root, use one of these PowerShell workflows:

Option 1: enable the repository root in PATH and use the normal Streamlit command:

```powershell
.\enable_streamlit.ps1
streamlit run app.py
```

Option 2: run the local wrapper directly without modifying PATH:

```powershell
.\streamlit.cmd run app.py
```

Option 3: use the batch wrapper if you prefer:

```powershell
.\streamlit.bat run app.py
```

### Why this is necessary

PowerShell does not automatically search the current directory for commands. That means typing `streamlit run app.py` may fail unless the repo root is added to `PATH` or you invoke the wrapper using `.
`.

After the app starts, open the URL shown in the terminal, usually:

- `http://localhost:8501`

## Using the App

1. Open the app in your browser.
2. Enter your `Gemini API Key` in the sidebar.
3. Optionally enter a GitHub PAT for better API access.
4. Paste either:
   - a repository URL, e.g. `https://github.com/owner/repo`
   - or an issue URL, e.g. `https://github.com/owner/repo/issues/123`
5. Click `🚀 Run Triage Agent`.

### Example workflows

- Enter a repository URL to see open issue picks.
- Enter a specific issue URL to run a complete triage for that issue.

### Example issue URLs

Try these example issue URLs in the app:

- `https://github.com/streamlit/streamlit/issues/8049`
- `https://github.com/spring-projects/spring-boot/issues/39255`
- `https://github.com/nodejs/node/issues/51644`

## What Happens Inside

### `app.py`

- Renders the sidebar and main UI.
- Loads environment variables with `python-dotenv`.
- Calls GitHub helpers to fetch issue and repo data.
- Runs the `TriageAgent` to perform reasoning steps.
- Displays the triage output in the browser.

### `github_client.py`

- Parses GitHub issue and repo URLs.
- Fetches issue details and comments.
- Loads repo metadata and attempts a recursive file tree fetch.
- Falls back to top-level contents if the recursive API is blocked.

### `agent.py`

- Wraps the Gemini API client.
- Sends structured prompts to classify, locate, suggest, and respond.
- Parses JSON from the AI output and stores it in `TriageState`.

### `prompts.py`

- Defines schemas for AI responses using `pydantic`.
- Contains prompt templates for each reasoning stage.

## Running Tests

Run the unit tests with:

```powershell
python -m unittest test_triage.py
```

## Troubleshooting

### `streamlit` command not found

Run the app directly through Python:

```powershell
py -3 -m streamlit run app.py
```

### GitHub 401 / 403 errors

- Check that `GITHUB_TOKEN` or `GITHUB_PAT` is set correctly.
- Ensure the token still exists and has at least `public_repo` or `repo` access.
- If you only use unauthenticated GitHub requests, expect strict rate limits.

### Gemini API issues

- Confirm `GEMINI_API_KEY` is correct.
- Install dependencies from `requirements.txt`.
- Verify the selected Gemini model supports `generate_content`.

## Helpful Tips

- Use a GitHub PAT for reliable issue fetching and repository tree access.
- If you want to inspect the repository structure manually, copy `repo_tree` from the browser output.
- Keep the issue URL or repo URL exact and valid, or the app will prompt for a correction.

## License

This repository does not include a license file. Add one if you intend to share it publicly.
