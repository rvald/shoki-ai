iOS Client                    GCS                     Pub/Sub (audio-uploads)         Cloud Run Worker                    Firestore (state)         Orchestrator (LangGraph)            Tools/Agents & Observability
   |                           |                                  |                           |                                        |                           |                                      |
1) |--(signed URL PUT)-------> |                                  |                           |                                        |                           |                                      |
   |                           |--OBJECT_FINALIZE---------------->|                           |                                        |                           |                                      |
   |                           |                                  |--(push POST; messageId)->|                                        |                           |                                      |
   |                           |                                  |                           |-- jlog(event="received", request_id) -> Cloud Logging            |                           | (structured JSON logs at each step)
   |                           |                                  |                           |-- compute idempotency_key ------------>| (txn) set status=PROCESSING, attempt=1
   |                           |                                  |                           |<---------------------------------------| (if already DONE/PROCESSING: DUPLICATE → 204 ACK)
   |                           |                                  |                           |-- start Orchestrator(graph, audio_file_name) -------------------->|

   Orchestrator Step 0: Validate input
   |                           |                                  |                           |                                        |                           |-- validate(audio_file_name)         |
   |                           |                                  |                           |                                        |                           |-- jlog(step="validate")             |

   Orchestrator Step 1: Transcribe
   |                           |                                  |                           |                                        |                           |-- call transcribe_audio ----------->| Whisper Service (ASR)
   |                           |                                  |                           |                                        |                           |                                      |-- Langfuse trace(span="transcribe_tool")
   |                           |                                  |                           |                                        |                           |<-------------------------------------| {transcription JSON, model_used, duration} 
   |                           |                                  |                           |-- persist artifacts/transcript.json --> GCS (optional)            |                           |
   |                           |                                  |                           |                                        |                           |-- jlog(step="transcribe", duration_ms, model_used)

   Orchestrator Step 2: Redact
   |                           |                                  |                           |                                        |                           |-- call redact_text(redaction policy)->| Presidio Service
   |                           |                                  |                           |                                        |                           |                                      |-- Langfuse trace(span="redact_tool")
   |                           |                                  |                           |                                        |                           |<-------------------------------------| {redacted_text, redaction_summary}
   |                           |                                  |                           |-- persist artifacts/redacted.json ----> GCS (optional)            |                           |
   |                           |                                  |                           |                                        |                           |-- jlog(step="redact", pii_stats)

   Orchestrator Step 3: Audit
   |                           |                                  |                           |                                        |                           |-- call compliance_agent ------------>| LLM (no raw PHI; uses redacted_text)
   |                           |                                  |                           |                                        |                           |                                      |-- Langfuse trace(span="compliance_agent")
   |                           |                                  |                           |                                        |                           |<-------------------------------------| {"hipaa_compliant": true, "fail_identifiers": [], ...}
   |                           |                                  |                           |-- persist artifacts/audit.json -------> GCS (optional)            |                           |
   |                           |                                  |                           |                                        |                           |-- jlog(step="audit", hipaa_compliant=true)

   Orchestrator Step 4: Generate SOAP (only if audit PASS)
   |                           |                                  |                           |                                        |                           |-- (optional) retrieve guidelines --->| RAG Retriever (Qdrant/AI Search)
   |                           |                                  |                           |                                        |                           |                                      |-- Langfuse trace(span="rag_retrieval")
   |                           |                                  |                           |                                        |                           |-- call generate_soap_note --------->| LLM (constrained; uses redacted_text [+ citations])
   |                           |                                  |                           |                                        |                           |                                      |-- Langfuse trace(span="soap_tool")
   |                           |                                  |                           |                                        |                           |<-------------------------------------| {"soap_note": "..."}
   |                           |                                  |                           |-- persist artifacts/soap.json --------> GCS (optional)            |                           |
   |                           |                                  |                           |                                        |                           |-- jlog(step="soap_generate")

   Orchestrator Step 5: Notify (and/or HITL approval if configured)
   |                           |                                  |                           |                                        |                           |-- assemble final result (PASS)      |
   |                           |                                  |                           |-- (optional) post summary to Slack --> Slack (approval/audit)     |                           |-- jlog(step="notify")

   |                           |                                  |                           |-- update status=DONE ----------------->| last_updated, duration_ms
   |                           |                                  |                           |-- jlog(event="done", request_id, idempotency_key, duration_ms)
   |                           |                                  |                           |-- 204 ACK ---------------------------->| (acknowledge delivery)
   |                           |                                  |                           |-- (optional) publish "audio-processed" to Pub/Sub