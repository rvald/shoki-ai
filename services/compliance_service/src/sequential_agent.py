from __future__ import annotations

from typing import Dict, List, Optional
from pydantic import BaseModel, Field

from .config import settings  
from .prompt import audit_prompt, compliance_prompt, soap_prompt
from openai import OpenAI
import openai
from .logging import jlog
from .schemas import HipaaRemediationResponse



DEFAULT_MODEL = settings.audit_model
DEFAULT_TEMPERATURE = 0.3
DEFAULT_TIMEOUT_S = settings.audit_timeout_s
DEFAULT_MAX_TURNS = 3


class AgentConfig(BaseModel):
    """Static configuration for a sub-agent."""
    name: str
    system_prompt: str
    max_turns: int = Field(DEFAULT_MAX_TURNS, ge=0)


class AgentTurn(BaseModel):
    """A single interaction turn recorded in memory."""
    input: str
    output: str


class AgentState(BaseModel):
    """Runtime state for a sub-agent: config and recent conversation memory."""
    config: AgentConfig
    memory: List[AgentTurn] = Field(default_factory=list)

    def append_turn(self, turn: AgentTurn) -> None:
        self.memory.append(turn)
        self._prune()

    def _prune(self) -> None:
        max_turns = self.config.max_turns
        if max_turns and len(self.memory) > max_turns:
            self.memory[:] = self.memory[-max_turns:]


class AgentOutputs(BaseModel):
    """Final outputs from the sequential agent pipeline."""
    audit: str
    compliance: str
    soap_notes: str


class LLMClient:
    """Thin wrapper around an OpenAI-compatible client."""

    def __init__(self, client: Optional[object] = None):
        self.client = client or self._make_client()

    def _make_client(self) -> OpenAI:
        if not settings.ollama_gcs_url:
            raise ValueError("Missing OLLAMA_GCS_URL for LLMClient")
        return OpenAI(base_url=f"{settings.ollama_gcs_url}/v1", api_key="dummy")

    def generate(
        self,
        agent_name: str,
        messages: List[Dict[str, str]],
        model: str = DEFAULT_MODEL,
        temperature: float = DEFAULT_TEMPERATURE,
        timeout_s: float = DEFAULT_TIMEOUT_S,
    ) -> str:
        """
        Send a chat completion request and return the assistant's text content.
        messages: list of {"role": "system"|"user"|"assistant", "content": str}
        """
        # Validate message structure lightly
        for m in messages:
            if not isinstance(m, dict) or "role" not in m or "content" not in m:
                raise ValueError(f"Invalid message item: {m}")
            
        if agent_name != "soap":

            resp = self.client.chat.completions.create(  # type: ignore[attr-defined]
                model=model,
                messages=messages, # type: ignore
                temperature=temperature,
                timeout=timeout_s,
            )
            # OpenAI SDK v1 result structure
            content = resp.choices[0].message.content  # type: ignore[index]
            
            return (content or "").strip()
        
        else:
            try:
                resp = self.client.beta.chat.completions.parse(  # type: ignore[attr-defined]
                    model=model,
                    input=messages, # type: ignore
                    temperature=temperature,
                    timeout=timeout_s,
                    response_format=HipaaRemediationResponse
                )
                soap_response = resp.choices[0].message
                if soap_response.parsed:
                        print(soap_response.parsed)
                        return soap_response.parsed.transcript_sanitized
                elif soap_response.refusal:
                        print(soap_response.refusal)
                        return "Error: LLM refused to answer"
            except Exception as e:
                if type(e) == openai.LengthFinishReasonError:
                    print("Too many tokens: ", e)
                    return "Error: Too many tokens in the request/response"
                else:
                    print(e)
                    return "Error: An unknown error occurred during the LLM request"
                
        return "Error: An unknown error occurred"


class SequentialAgent:
    """An agent that processes a transcript through sub-agents sequentially."""

    def __init__(
        self,
        llm_client: Optional[LLMClient] = None,
        model: str = DEFAULT_MODEL,
        temperature: float = DEFAULT_TEMPERATURE,
        timeout_s: float = DEFAULT_TIMEOUT_S,
    ):
        self.llm = llm_client or LLMClient()
        self.model = model
        self.temperature = temperature
        self.timeout_s = timeout_s

        # Shared memory across sub-agents. Keep small textual notes only.
        self.shared_memory: Dict[str, str] = {}

        # Configure sub-agents consistently
        self.sub_agents: Dict[str, AgentState] = {
            "audit": AgentState(
                config=AgentConfig(
                    name="audit",
                    system_prompt=audit_prompt,
                    max_turns=DEFAULT_MAX_TURNS,
                )
            ),
            "compliance": AgentState(
                config=AgentConfig(
                    name="compliance",
                    system_prompt=compliance_prompt,
                    max_turns=DEFAULT_MAX_TURNS,
                )
            ),
            "soap": AgentState(
                config=AgentConfig(
                    name="soap",
                    system_prompt=soap_prompt,
                    max_turns=DEFAULT_MAX_TURNS,
                )
            ),
        }

    def _build_messages(self, sub_agent_name: str, input_text: str) -> List[Dict[str, str]]:
        """Construct OpenAI chat messages for the given sub-agent."""
        if sub_agent_name not in self.sub_agents:
            raise KeyError(f"Unknown sub-agent: {sub_agent_name}")

        agent_state = self.sub_agents[sub_agent_name]
        cfg = agent_state.config

        messages: List[Dict[str, str]] = [{"role": "system", "content": cfg.system_prompt}]

        # Add relevant shared memory for this sub-agent (optional, small)
        if sub_agent_name in self.shared_memory:
            messages.append(
                {
                    "role": "user",
                    "content": f"RELEVANT INFORMATION:\n{self.shared_memory[sub_agent_name]}",
                }
            )

        # Add recent conversation memory (user/assistant pairs)
        for turn in agent_state.memory:
            messages.append({"role": "user", "content": turn.input})
            messages.append({"role": "assistant", "content": turn.output})

        # Add current user input
        messages.append({"role": "user", "content": input_text})

        return messages

    def _call_sub_agent(self, sub_agent_name: str, input_text: str) -> str:
        """Call a sub-agent with the given input text and return its output string."""
        messages = self._build_messages(sub_agent_name, input_text)
        output_text = self.llm.generate(
            agent_name=sub_agent_name,
            messages=messages, 
            model=self.model, 
            temperature=self.temperature, 
            timeout_s=self.timeout_s
        )

        jlog(
            event="sub_agent_call",
            sub_agent=sub_agent_name,   
            messages=messages,
            input_preview=input_text,
            output_preview=output_text,
        )

        # Update memory and prune
        state = self.sub_agents[sub_agent_name]
        state.append_turn(AgentTurn(input=input_text, output=output_text))
        return output_text

    def process_transcript(self, transcript: str) -> AgentOutputs:
        """
        Process a transcript through the sequence:
          1) audit
          2) compliance (uses audit result)
          3) soap (uses compliance result)
        Returns structured outputs for each stage.
        """
        # Step 1: Audit
        audit_prompt = f"Perform an audit on the following redacted transcript:\n\n{transcript}"
        audit_output = self._call_sub_agent("audit", audit_prompt)

        # Share a short audit summary (limit to keep context small)
        self.shared_memory["audit"] = f"Audit result (summary): {audit_output}"

        # Step 2: Compliance
        compliance_prompt = (
            "Using the audit findings, ensure the transcript meets compliance. "
            "Return a concise compliance-focused validation.\n\n"
            f"Transcript:\n{transcript}"
        )
        compliance_output = self._call_sub_agent("compliance", compliance_prompt)

        self.shared_memory["compliance"] = f"Compliance result (summary): {compliance_output}"

        # Step 3: SOAP
        soap_prompt = (
            "Generate SOAP medical notes (Subjective, Objective, Assessment, Plan) for the following "
            "compliance-reviewed transcript. Be concise and structured.\n\n"
            f"Transcript:\n{transcript}"
        )
        soap_output = self._call_sub_agent("soap", soap_prompt)

        return AgentOutputs(audit=audit_output, compliance=compliance_output, soap_notes=soap_output)