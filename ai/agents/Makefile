# Makefile for Build and Deploy to Cloud Run / Artifact Registry

.PHONY: build deploy help

# Defaults (override as needed)
SERVICE_NAME ?= shoki-agents-service
GOOGLE_CLOUD_LOCATION ?= us-central1
GOOGLE_CLOUD_PROJECT ?= shoki-api
GOOGLE_GENAI_USE_VERTEXAI ?= True
MCP_SERVER_URL ?= "https://mcp-tool-server-772943814292.us-central1.run.app/sse"
PRIVACY_MCP_SERVER_URL ?= "https://privacy-mcp-tool-server-772943814292.us-central1.run.app/sse"
SOAP_MCP_SERVER_URL ?= "https://soap-note-mcp-tool-server-772943814292.us-central1.run.app/sse"


# Deploy the Cloud Run service
deploy:
	@echo "Deploying to Cloud Run: $(SERVICE_NAME)"
	@gcloud run deploy $(SERVICE_NAME) \
	  --source . \
	  --region=$(REGION) \
	  --allow-unauthenticated \
	  --set-env-vars="MCP_SERVER_URL=$(MCP_SERVER_URL)" \
	  --set-env-vars="PRIVACY_MCP_SERVER_URL=$(PRIVACY_MCP_SERVER_URL)" \
	  --set-env-vars="SOAP_MCP_SERVER_URL=$(SOAP_MCP_SERVER_URL)" \
	  --set-env-vars="GOOGLE_CLOUD_PROJECT=$(GOOGLE_CLOUD_PROJECT)" \
	  --set-env-vars="GOOGLE_CLOUD_LOCATION=$(GOOGLE_CLOUD_LOCATION)" \
	  --set-env-vars="OPENAI_API_KEY=$(OPENAI_API_KEY)" \
	  --set-env-vars="GOOGLE_GENAI_USE_VERTEXAI=$(GOOGLE_GENAI_USE_VERTEXAI)" \

# Optional helper
help:
	@echo "Makefile targets:"
	@echo "  make deploy       Deploy the image to Cloud Run with env vars"
	@echo "  make help         Show this help"