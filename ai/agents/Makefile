# Makefile for Build and Deploy to Cloud Run / Artifact Registry

.PHONY: build deploy help

# Defaults (override as needed)
SERVICE_NAME ?= shoki-agents-service
GOOGLE_CLOUD_LOCATION ?= us-central1
GOOGLE_CLOUD_PROJECT ?= shoki-api
GOOGLE_GENAI_USE_VERTEXAI ?= True

PRIVACY_MCP_SERVER_URL ?= "https://privacy-mcp-tool-server-772943814292.us-central1.run.app/sse"
SOAP_MCP_SERVER_URL ?= "https://soap-note-mcp-tool-server-772943814292.us-central1.run.app/sse"
TRANSCRIBE_MCP_SERVER_URL ?= "https://transcribe-mcp-tool-server-772943814292.us-central1.run.app/sse"
COMPLIANCE_MCP_SERVER_URL ?= "https://mcp-tool-server-772943814292.us-central1.run.app/sse"


# Deploy the Cloud Run service
deploy:
	@echo "Deploying to Cloud Run: $(SERVICE_NAME)"
	@gcloud run deploy $(SERVICE_NAME) \
	  --source . \
	  --region=$(REGION) \
	  --allow-unauthenticated \
	  --set-env-vars="PRIVACY_MCP_SERVER_URL=$(PRIVACY_MCP_SERVER_URL)" \
	  --set-env-vars="SOAP_MCP_SERVER_URL=$(SOAP_MCP_SERVER_URL)" \
	  --set-env-vars="GOOGLE_CLOUD_PROJECT=$(GOOGLE_CLOUD_PROJECT)" \
	  --set-env-vars="GOOGLE_CLOUD_LOCATION=$(GOOGLE_CLOUD_LOCATION)" \
	  --set-env-vars="OPENAI_API_KEY=$(OPENAI_API_KEY)" \
	  --set-env-vars="GOOGLE_GENAI_USE_VERTEXAI=$(GOOGLE_GENAI_USE_VERTEXAI)" \
	  --set-env-vars="TRANSCRIBE_MCP_SERVER_URL=$(TRANSCRIBE_MCP_SERVER_URL)" \
	  --set-env-vars="COMPLIANCE_MCP_SERVER_URL=$(COMPLIANCE_MCP_SERVER_URL)" \

# Optional helper
help:
	@echo "Makefile targets:"
	@echo "  make deploy       Deploy the image to Cloud Run with env vars"
	@echo "  make help         Show this help"