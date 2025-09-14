# Makefile for Build and Deploy to Cloud Run / Artifact Registry

.PHONY: build deploy help

# Defaults (override as needed)
IMAGE_TAG ?= latest
APP_FOLDER_NAME ?= compliance
IMAGE_NAME ?= orchestrator-service
REGION ?= us-central1
PROJECT_ID ?= shoki-api
REPO_NAME ?= compliance-repo
SERVICE_NAME ?= orchestrator-service


# Build and deploy image paths (as per your script)
IMAGE_PATH_BUILD := $(REGION)-docker.pkg.dev/$(PROJECT_ID)/$(REPO_NAME)/$(IMAGE_NAME):$(IMAGE_TAG)
IMAGE_PATH_DEPLOY := $(REGION)-docker.pkg.dev/$(PROJECT_ID)/$(REPO_NAME)/$(IMAGE_NAME):$(IMAGE_TAG)

USE_CLOUD_TRACE ?=true
ENVIRONMENT ?=prod


# Build the container image and push to Artifact Registry
build:
	@echo "Building and pushing image: $(IMAGE_PATH_BUILD)"
	@gcloud builds submit . \
	  --tag=$(IMAGE_PATH_BUILD) \
	  --project=$(PROJECT_ID)

# Deploy the Cloud Run service
deploy:
	@echo "Deploying to Cloud Run: $(SERVICE_NAME)"
	@gcloud run deploy $(SERVICE_NAME) \
	  --image=$(IMAGE_PATH_DEPLOY) \
	  --platform=managed \
	  --region=$(REGION) \
	  --allow-unauthenticated \
	  --set-env-vars="APP_HOST=0.0.0.0" \
	  --set-env-vars="APP_PORT=8080" \
	  --set-env-vars="GOOGLE_CLOUD_LOCATION=$(REGION)" \
	  --set-env-vars="GOOGLE_CLOUD_PROJECT=$(PROJECT_ID)" \
	  --set-env-vars="GOOGLE_PROJECT_ID=$(PROJECT_ID)" \
	  --set-env-vars="USE_CLOUD_TRACE=$(USE_CLOUD_TRACE)" \
	  --set-env-vars="ENVIRONMENT=$(ENVIRONMENT)" \
	  --set-env-vars="PROJECT_ID=$(PROJECT_ID),FIRESTORE_COLLECTION=runs,SERVICE_NAME=$(SERVICE_NAME),ORCH_TIMEOUT_S=120,ORCH_MAX_RETRIES=2,ORCH_BACKOFF_BASE_MS=200,ORCH_BACKOFF_CAP_MS=3000,ORCH_CONCURRENCY=64,ORCH_RETRY_BUDGET_S=6.0,REQUIRE_PUBSUB_AUTH=false,PUBSUB_PUSH_AUDIENCE=https://orchestrator-service-772943814292.us-central1.run.app/events/pubsub,TRANSCRIBE_REQUESTED_TOPIC=transcribe-requested,TRANSCRIBE_COMPLETED_TOPIC=transcribe-completed,REDACT_REQUESTED_TOPIC=redact-requested,REDACT_COMPLETED_TOPIC=redact-completed,AUDIT_REQUESTED_TOPIC=audit-requested,AUDIT_COMPLETED_TOPIC=audit-completed,SOAP_REQUESTED_TOPIC=soap-requested,SOAP_COMPLETED_TOPIC=soap-completed,IDEM_TTL_DAYS=14,INCLUDE_SESSION_IN_IDEM=true"
	  --project=$(PROJECT_ID) \
	  --min-instances=0

# Optional helper
help:
	@echo "Makefile targets:"
	@echo "  make build        Build and push the image to Artifact Registry"
	@echo "  make deploy       Deploy the image to Cloud Run with env vars"
	@echo "  make help         Show this help"