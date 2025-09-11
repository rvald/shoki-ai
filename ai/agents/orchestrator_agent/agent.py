from google.adk.agents.llm_agent import LlmAgent
from google.adk.tools.mcp_tool.mcp_toolset import MCPToolset,  SseConnectionParams
from google.adk.models.lite_llm import LiteLlm
from .prompt import system_propmpt_v4
import os
 
# --- Global variables ---
MODEL_GPT_4_1_NANO = "openai/gpt-4.1-nano"
PRIVACY_MCP_SERVER_URL = os.environ.get("PRIVACY_MCP_SERVER_URL")
SOAP_MCP_SERVER_URL = os.environ.get("SOAP_MCP_SERVER_URL")
TRANSCRIBE_MCP_SERVER_URL = os.environ.get("TRANSCRIBE_MCP_SERVER_URL")
COMPLIANCE_MCP_SERVER_URL = os.environ.get("COMPLIANCE_MCP_SERVER_URL")

# --- Agent definition ---
root_agent = LlmAgent(
  model = LiteLlm(model=MODEL_GPT_4_1_NANO),
  name = "orchestrator_agent",
  instruction=system_propmpt_v4,
  tools=[
      MCPToolset(
          connection_params=SseConnectionParams(url=PRIVACY_MCP_SERVER_URL, headers={})
      ),
      MCPToolset(
          connection_params=SseConnectionParams(url=SOAP_MCP_SERVER_URL, headers={})
      ),
      MCPToolset(
          connection_params=SseConnectionParams(url=TRANSCRIBE_MCP_SERVER_URL, headers={})
      ),
      MCPToolset(
          connection_params=SseConnectionParams(url=COMPLIANCE_MCP_SERVER_URL, headers={})
      )
  ],
)

