import os
import streamlit as st
from dotenv import load_dotenv

from state import TriageState
import github_client
from agent import TriageAgent

# Page configuration
st.set_page_config(
    page_title="BugTriage AI Dashboard",
    page_icon="🐞",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Load environment variables
load_dotenv()

# Inject custom premium CSS for styling
st.markdown("""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;700;800&display=swap');
        
        /* Font rules */
        html, body, [class*="css"], .stApp {
            font-family: 'Outfit', sans-serif;
        }
        
        /* Header styling */
        .title-container {
            padding: 1rem 0;
            margin-bottom: 1.5rem;
            border-bottom: 1px solid rgba(255, 255, 255, 0.08);
        }
        .title-text {
            background: linear-gradient(90deg, #ff4b4b, #ff8533);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            font-size: 2.8rem;
            font-weight: 800;
            margin: 0;
        }
        .subtitle-text {
            font-size: 1.1rem;
            color: #888899;
            margin-top: 5px;
        }

        /* Glassmorphism metrics card */
        .triage-card {
            background: rgba(255, 255, 255, 0.03);
            backdrop-filter: blur(12px);
            border-radius: 12px;
            padding: 20px;
            border: 1px solid rgba(255, 255, 255, 0.08);
            margin-bottom: 20px;
            box-shadow: 0 4px 30px rgba(0, 0, 0, 0.25);
        }
        
        /* Custom styled badges */
        .badge {
            display: inline-block;
            padding: 5px 10px;
            border-radius: 20px;
            font-size: 0.85rem;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            margin-right: 8px;
            border: 1px solid rgba(255, 255, 255, 0.1);
        }
        .badge-critical { background-color: rgba(255, 51, 51, 0.2); color: #ff6666; border: 1px solid rgba(255, 51, 51, 0.4); }
        .badge-high { background-color: rgba(255, 128, 0, 0.2); color: #ff9933; border: 1px solid rgba(255, 128, 0, 0.4); }
        .badge-medium { background-color: rgba(230, 184, 0, 0.2); color: #ffcc00; border: 1px solid rgba(230, 184, 0, 0.4); }
        .badge-low { background-color: rgba(45, 179, 0, 0.2); color: #66ff66; border: 1px solid rgba(45, 179, 0, 0.4); }
        
        .badge-category { background-color: rgba(0, 115, 230, 0.2); color: #3399ff; border: 1px solid rgba(0, 115, 230, 0.4); }
        .badge-layer { background-color: rgba(153, 51, 255, 0.2); color: #b366ff; border: 1px solid rgba(153, 51, 255, 0.4); }

        /* Meta display */
        .meta-label {
            font-size: 0.85rem;
            color: #888899;
            margin-bottom: 3px;
            font-weight: 500;
        }
        .meta-value {
            font-size: 1.15rem;
            font-weight: 600;
            color: #ffffff;
        }
        
        /* Debug step custom card styling */
        .debug-step-card {
            background: rgba(255, 255, 255, 0.01);
            border-left: 4px solid #ff4b4b;
            border-radius: 0 8px 8px 0;
            padding: 15px;
            margin-bottom: 12px;
            border-top: 1px solid rgba(255, 255, 255, 0.04);
            border-right: 1px solid rgba(255, 255, 255, 0.04);
            border-bottom: 1px solid rgba(255, 255, 255, 0.04);
        }
    </style>
""", unsafe_allow_html=True)

# Application Header
st.markdown("""
    <div class="title-container">
        <h1 class="title-text">🐞 BugTriage AI</h1>
        <p class="subtitle-text">A premium multi-step agentic system acting as a first responder for GitHub bug reports.</p>
    </div>
""", unsafe_allow_html=True)

# Sidebar setup for configuration and API credentials
with st.sidebar:
    st.header("⚙️ Configuration")
    
    # Retrieve default credentials from env (if loaded)
    env_gemini_key = os.getenv("GEMINI_API_KEY", "")
    env_github_token = os.getenv("GITHUB_TOKEN", "") or os.getenv("GITHUB_PAT", "")
    env_gemini_model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
    
    st.markdown("### API Credentials")
    api_key_input = st.text_input(
        "Gemini API Key",
        value=env_gemini_key,
        type="password",
        help="Required for running the triage agent reasoning steps."
    )
    
    github_token_input = st.text_input(
        "GitHub Personal Access Token (Optional)",
        value=env_github_token,
        type="password",
        help="Recommended to raise rate limits from 60 req/hr to 5,000 req/hr. Set either GITHUB_TOKEN or GITHUB_PAT."
    )

    st.markdown("---")
    st.markdown("### Model Selection")
    model_name_input = st.selectbox(
        "Gemini Model",
        options=["gemini-2.5-flash", "gemini-1.5-flash", "gemini-2.5-pro"],
        index=0 if env_gemini_model == "gemini-2.5-flash" else (1 if env_gemini_model == "gemini-1.5-flash" else 2)
    )
    
    st.markdown("---")
    st.markdown("💡 **Tip:** Providing a `GITHUB_TOKEN` ensures that recursive file tree requests resolve successfully even for larger repositories.")

# Main Interface Layout
issue_url = st.text_input(
    "🔗 Enter GitHub Repository or Issue URL",
    placeholder="https://github.com/owner/repo or https://github.com/owner/repo/issues/123",
    help="Enter a repository URL to list open issues, or enter an issue URL directly."
)

# Parsing URL input
selected_issue_url = None
is_issue_url = False

if issue_url:
    try:
        # Check if it's a specific issue
        owner, repo, issue_num = github_client.parse_issue_url(issue_url)
        selected_issue_url = issue_url
        is_issue_url = True
    except ValueError:
        # Try parsing as a repo URL
        try:
            owner, repo = github_client.parse_repo_url(issue_url)
            
            # Fetch open issues
            try:
                open_issues = github_client.get_open_issues(owner, repo, token=github_token_input)
                if open_issues:
                    st.info(f"📁 Repository: {owner}/{repo} — Found {len(open_issues)} open issue(s).")
                    issue_options = {f"#{issue['number']}: {issue['title']}": issue['html_url'] for issue in open_issues}
                    selected_label = st.selectbox(
                        "🎯 Select an open issue to triage:",
                        options=list(issue_options.keys()),
                        help="Choose which bug report you want the agent to triage."
                    )
                    selected_issue_url = issue_options[selected_label]
                else:
                    st.warning(f"⚠️ No open issues found in repository {owner}/{repo}.")
            except Exception as ex:
                st.error(f"❌ Failed to fetch issues: {str(ex)}")
        except ValueError:
            st.error("❌ Invalid GitHub URL. Please provide a repository URL (https://github.com/owner/repo) or issue URL (https://github.com/owner/repo/issues/123)")

run_triage = st.button("🚀 Run Triage Agent", use_container_width=True)

# Initialize Session State variables
if "triage_state" not in st.session_state:
    st.session_state.triage_state = None

if run_triage:
    if not selected_issue_url:
        st.warning("Please provide a valid GitHub issue URL or select an open issue from the repository.")
    elif not api_key_input:
        st.error("Gemini API Key is required to run the reasoning agent.")
    else:
        # 1. Initialize State
        state = TriageState(url=selected_issue_url, issue={}, repo_tree=[])
        st.session_state.triage_state = None
        
        # Start st.status loader to orchestrate tasks live
        with st.status("🤖 Initiating Triage Pipeline...", expanded=True) as status:
            try:
                # Step 1: Parse and Fetch Issue Details
                status.update(label="🔍 Fetching GitHub issue details & comments...", state="running")
                issue_details = github_client.get_issue(selected_issue_url, token=github_token_input)
                state.issue = {
                    "title": issue_details["title"],
                    "body": issue_details["body"],
                    "comments": issue_details["comments"]
                }
                
                # Step 2: Fetch Repository File Tree
                status.update(label="📁 Fetching repository structure (recursive / top-level)...", state="running")
                repo_tree = github_client.get_repo_tree(
                    issue_details["owner"],
                    issue_details["repo"],
                    token=github_token_input
                )
                state.repo_tree = repo_tree
                
                # Instantiate Triage Agent
                agent = TriageAgent(api_key=api_key_input, model_name=model_name_input)
                
                # Step 3: Classify Bug Report
                status.update(label="🏷️ Classifying bug report (severity, category, layer)...", state="running")
                state = agent.classify(state)
                
                # Step 4: Locate suspected files
                status.update(label="📍 Pinpointing potential culprit files in repository...", state="running")
                state = agent.locate(state)
                
                # Step 5: Generate Suggestion Pathway
                status.update(label="🛠️ Suggesting actionable 3-step debugging plan...", state="running")
                state = agent.suggest(state)
                
                # Step 6: Draft Response for user/maintainer
                status.update(label="📝 Drafting final markdown response template...", state="running")
                state = agent.respond(state)
                
                # Finalize status container
                status.update(label="✅ Triage completed successfully!", state="complete")
                
                # Store back in session state
                st.session_state.triage_state = state
                
            except Exception as e:
                status.update(label="❌ Triage execution crashed!", state="error")
                state.error = str(e)
                state.current_step = "failed"
                st.session_state.triage_state = state
                st.error(f"Execution Error: {str(e)}")

# Render Triage State Results
state = st.session_state.triage_state
if state and state.current_step == "completed":
    st.markdown("## 📊 Triage Agent Results")
    
    # 1. Summary Metrics
    classification = state.classification or {}
    sev = classification.get("severity", "Medium").lower()
    
    # Severity Badge styling mapping
    sev_badge_class = "badge-medium"
    if "crit" in sev:
        sev_badge_class = "badge-critical"
    elif "high" in sev:
        sev_badge_class = "badge-high"
    elif "low" in sev:
        sev_badge_class = "badge-low"

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.markdown(f"""
            <div class="triage-card">
                <div class="meta-label">Severity</div>
                <div><span class="badge {sev_badge_class}">{classification.get("severity", "N/A")}</span></div>
            </div>
        """, unsafe_allow_html=True)
    with col2:
        st.markdown(f"""
            <div class="triage-card">
                <div class="meta-label">Category</div>
                <div><span class="badge badge-category">{classification.get("category", "N/A")}</span></div>
            </div>
        """, unsafe_allow_html=True)
    with col3:
        st.markdown(f"""
            <div class="triage-card">
                <div class="meta-label">Affected Layer</div>
                <div><span class="badge badge-layer">{classification.get("affected_layer", "N/A")}</span></div>
            </div>
        """, unsafe_allow_html=True)
    with col4:
        confidence_val = classification.get("confidence", 0.5)
        st.markdown(f"""
            <div class="triage-card">
                <div class="meta-label">Confidence</div>
                <div class="meta-value">{int(confidence_val * 100)}%</div>
            </div>
        """, unsafe_allow_html=True)
        
    # Render Reasoning justification text
    with st.expander("ℹ️ Read Agent Classification Reasoning", expanded=True):
        st.write(classification.get("reasoning", "No explanation provided."))

    # 2. Key Actions Panel (Draft Response vs Debug/Files)
    col_left, col_right = st.columns([1, 1])
    
    with col_left:
        st.subheader("📝 Draft Response Preview")
        st.markdown("You can copy this response and paste it directly in the GitHub issue:")
        
        # Streamlit's code block provides native hover copy button
        st.code(state.draft_response, language="markdown")
        
        # Render a live markdown view so user can check layout
        st.markdown("### Markdown Rendered Preview")
        st.markdown(
            f"<div style='background-color: rgba(255,255,255,0.02); border: 1px solid rgba(255,255,255,0.06); padding: 15px; border-radius: 8px;'>{state.draft_response}</div>",
            unsafe_allow_html=True
        )

    with col_right:
        st.subheader("🔬 Diagnosis & Debug Path")
        
        # Tabs for Debug Plan and Culprit Files
        tab1, tab2, tab3 = st.tabs(["🛠️ 3-Step Debug Plan", "📍 Suspected Files", "📁 Repo Files Inspect"])
        
        with tab1:
            debug_steps = (state.debug_plan or {}).get("debug_steps", [])
            if not debug_steps:
                st.info("No debug plan generated.")
            for step in debug_steps:
                target_str = ", ".join([f"`{f}`" for f in step.get("target_files", [])])
                st.markdown(f"""
                    <div class="debug-step-card">
                        <div style="font-weight: 700; color: #ff4b4b; margin-bottom: 5px;">
                            Step {step.get("step_number", 1)}: {step.get("title", "")}
                        </div>
                        <div style="font-size: 0.95rem; margin-bottom: 8px;">
                            {step.get("description", "")}
                        </div>
                        <div style="font-size: 0.85rem; color: #888899;">
                            Target Files: {target_str}
                        </div>
                    </div>
                """, unsafe_allow_html=True)
                
        with tab2:
            located = state.located_files or {}
            st.markdown(f"**Culprit Isolation Reasoning:**\n{located.get('reasoning', '')}")
            st.markdown("---")
            relevant = located.get("relevant_files", [])
            if not relevant:
                st.info("No suspected files identified.")
            for f in relevant:
                st.markdown(f"📁 `{f}`")
                
        with tab3:
            st.markdown(f"**Total Tracked Repository Files:** `{len(state.repo_tree)}` (limited to top 300)")
            search_query = st.text_input("🔍 Search File Tree", placeholder="e.g. auth.py")
            filtered_tree = [f for f in state.repo_tree if search_query.lower() in f.lower()]
            
            st.markdown("<div style='height: 200px; overflow-y: scroll; border: 1px solid rgba(255,255,255,0.06); padding: 10px; border-radius: 4px;'>", unsafe_allow_html=True)
            for f in filtered_tree:
                st.markdown(f"📄 {f}")
            st.markdown("</div>", unsafe_allow_html=True)

    # 3. Raw State Inspector
    st.markdown("---")
    with st.expander("🔍 Serialized TriageState Inspector", expanded=False):
        st.code(state.to_json(), language="json")

elif state and state.current_step == "failed":
    st.error(f"The pipeline failed. Error details: {state.error}")
