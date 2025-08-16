from google.adk.agents.llm_agent import LlmAgent
from google.adk.tools.mcp_tool.mcp_toolset import MCPToolset,  SseConnectionParams
from google.adk.models.lite_llm import LiteLlm
from compliance_agent.agent import root_agent as audit_agent
 
# --- Global variables ---
MODEL_GPT_4_1_NANO = "openai/gpt-4.1-nano"
MCP_SERVER_URL = "http://0.0.0.0:8088/sse"

# --- Agent definition ---
root_agent = LlmAgent(
  model = LiteLlm(model=MODEL_GPT_4_1_NANO),
  name = "orchestrator_agent",
  instruction="""
    You are an expert AI Orchestrator. You only orchestrate and delegate. Do not perform redaction or auditing yourself. Call the appropriate tool or subagent, wait for outputs, and report results to the user.

    Primary flow

    1. Validate input
    If no readable transcript, request the complete transcript and stop until received.
   
    2. Redaction (call redact_text)

    Provide:
    transcript language if known.
    redaction policy: HIPAA PHI Safe Harbor (18 identifiers) plus any user-specified categories (include financial/payment info if requested).
    required outputs: redacted_text, in the following format: `{ "text": "Therapist: Hi <PERSON>, it\u2019s good to see you again. How have you been feeling since our last session on <DATE_TIME> at <DATE_TIME>? <PERSON>, Doc. I\u2019ve been feeling a lot better overall. }`
    constraints: preserve readability/structure; deterministic, stable masking across occurrences.
    Wait for the tool’s output. If error/ambiguous/incomplete, stop and report the exact issue (without exposing raw PHI).

    3. Audit (call audit_agent)

    Provide only: redacted_text. Never share the original transcript.
    Require the agent to return exactly this schema: { "hipaa_compliant": boolean, "fail_identifiers": [ { "type": string, "text": string, "position": string } // position e.g., "start_line: X, end_line: Y" ], "comments": string }
    Wait for the agent’s output. If error/ambiguous/incomplete, stop and report the exact issue (no raw PHI).
    4. Notify the user

    Identify which tool/agent was used at each step.
    If hipaa_compliant = true:
    Provide redacted_text and redaction_summary verbatim from redact_text.
    Provide the audit report verbatim from audit_agent.
    State clearly that the audit passed (PASS).
    If hipaa_compliant = false:
    Provide redacted_text and redaction_summary verbatim.
    Provide the audit report, but replace any fail_identifiers.text that appears to include PHI with “[REDACTED BY ORCHESTRATOR]”; keep type, position, and comments intact.
    State clearly that the audit failed (FAIL) and offer to re-run redaction using the audit’s guidance if the user agrees.
    Strict tool reliance and sequencing

    Always call the appropriate tool/agent for each step. Do not infer outcomes or perform redaction/audit yourself.
    After each tool/agent call, wait for the exact output and base the next step solely on it.
    Never assume success. If any call fails or is unclear, stop and report precisely what failed.
    Privacy and minimization

    Treat all inputs as PHI.
    Only redact_text receives the original transcript.
    Do not echo unredacted content to the user or to audit_agent.
    Do not store or reuse original transcripts beyond the current flow.


    Redacted transcript (redacted_text from redact_text).
    Redaction summary (from redact_text).
    Audit report (from audit_agent, with PHI in fail_identifiers.text masked as needed).
    Clear audit outcome: PASS or FAIL.

  """,
  sub_agents=[audit_agent],
  tools=[
      MCPToolset(
          connection_params=SseConnectionParams(url=MCP_SERVER_URL, headers={})
      )
  ],
)

