from pydantic import BaseModel, Field
from typing import List

# --- Pydantic Schemas for Gemini Structured JSON Outputs ---

class ClassificationSchema(BaseModel):
    severity: str = Field(description="Severity levels: Low, Medium, High, Critical")
    category: str = Field(description="Issue category, e.g., UI/UX, Backend, Frontend, Database, API, Performance, Security, Setup/Build")
    affected_layer: str = Field(description="Affected layer of the system architecture, e.g., Database, API Router, Frontend View, Auth Middleware, CI/CD")
    confidence: float = Field(description="Confidence rating from 0.0 to 1.0")
    reasoning: str = Field(description="Brief logic explaining why this classification was chosen")

class LocationSchema(BaseModel):
    relevant_files: List[str] = Field(description="Sub-list of exact matching files from the repository tree that are relevant to this issue")
    reasoning: str = Field(description="Explanation of why these files are suspected, based on the issue description and file paths")

class DebugStep(BaseModel):
    step_number: int = Field(description="Step number (1, 2, or 3)")
    title: str = Field(description="Short, actionable title of this debugging step")
    description: str = Field(description="Detailed instructions on what code to check, log, or test to verify the root cause")
    target_files: List[str] = Field(description="Files related to this debugging step")

class SuggestionSchema(BaseModel):
    debug_steps: List[DebugStep] = Field(description="A concrete 3-step debugging path to isolate the issue")

class CriticSchema(BaseModel):
    critique: str = Field(description="A concise review of potential flaws in the existing classification and debugging plan")
    confidence: float = Field(description="Critic confidence from 0.0 to 1.0")
    issues: List[str] = Field(description="Specific problems that the critic identified")
    recommendations: List[str] = Field(description="Suggested corrections or validation actions")

class FinalClassificationSchema(BaseModel):
    severity: str = Field(description="Final severity levels: Low, Medium, High, Critical")
    category: str = Field(description="Final issue category")
    affected_layer: str = Field(description="Final affected system layer")
    confidence: float = Field(description="Final confidence rating from 0.0 to 1.0")
    reasoning: str = Field(description="Final reasoning behind the resolved classification")

class FinalSuggestionSchema(BaseModel):
    debug_steps: List[DebugStep] = Field(description="Final 3-step debugging path after review")
    rationale: str = Field(description="Why these steps are the final recommendation")

class ResolverSchema(BaseModel):
    final_classification: FinalClassificationSchema
    final_debug_plan: FinalSuggestionSchema
    resolution_notes: str = Field(description="High-level summary of how the critic feedback was incorporated")


# --- System Prompt Templates ---

CLASSIFY_PROMPT = """
You are a repository triage agent. Analyze the following GitHub bug report (title, body, and comments) and classify the issue.
Provide your output as a structured JSON object matching the requested schema.

GitHub Issue Details:
Title: {title}
Body:
{body}

Comments:
{comments}
"""

LOCATE_PROMPT = """
Given the GitHub issue details and the repository file tree below, identify which files in the repository are most likely related to this bug or contain the bug.
DO NOT hallucinate or output any files that are not in the repository file tree list.
Provide your output as a structured JSON object matching the requested schema.

GitHub Issue Details:
Title: {title}
Body:
{body}

Comments:
{comments}

Repository File Tree:
{repo_tree}
"""

SUGGEST_PROMPT = """
Based on the GitHub issue details, comments, and the suspected file locations identified by the triage agent, generate a concrete 3-step debugging path to isolate the root cause.
Each step must be clear, actionable, and state which files to check and what to test, log, or analyze.
Provide your output as a structured JSON object matching the requested schema.

GitHub Issue Details:
Title: {title}
Body:
{body}

Comments:
{comments}

Suspected Repository Files:
{located_files}
"""

RESPOND_PROMPT = """
You are a friendly, helpful, and concise open-source project maintainer. Draft a markdown response to the user who opened the issue.
Use the following details gathered during our triage:
- Classification: Category: {category}, Severity: {severity}, Affected Layer: {affected_layer}
- Suspected Files: {located_files}
- 3-Step Debugging Plan: {debug_plan}

In your response:
1. Acknowledge the issue, summarizing your understanding of the bug.
2. Share the suspected files and explain briefly why they might be related.
3. Offer the 3-step debugging plan to guide them (or other contributors) on how to verify/reproduce/fix the issue.
4. Keep the tone professional, supportive, and developer-focused. 

Important: Write the response in clean GitHub-Flavored Markdown. Do NOT wrap the entire output in a single markdown code fence (like ```markdown ... ```). Output the raw Markdown directly.

GitHub Issue Details:
Title: {title}
Body:
{body}

Comments:
{comments}
"""

CRITIC_PROMPT = """
You are the Critic Agent. Review the current issue classification, suspected files, and debugging steps.
Your goal is to identify any flaws, overstatements, or missing context that could weaken the diagnosis.
Provide your output as structured JSON matching the requested schema.

Initial Classification:
{classification}

Suspected Files and Reasoning:
{located_files}

Proposed Debug Plan:
{debug_plan}

Repository File Tree:
{repo_tree}
"""

RESOLVE_PROMPT = """
You are the Resolver Agent. You must synthesize the original triage outputs and the critic's review to produce a final, high-confidence diagnosis.
Do not simply repeat the original outputs. Use the critic feedback to refine or confirm the classification and debugging plan.
Provide your output as structured JSON matching the requested schema.

Initial Classification:
{classification}

Suspected Files and Reasoning:
{located_files}

Proposed Debug Plan:
{debug_plan}

Critic Feedback:
{critic_review}

Repository File Tree:
{repo_tree}
"""
