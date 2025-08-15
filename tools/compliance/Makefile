# Makefile for Build and Deploy to Cloud Run / Artifact Registry

.PHONY: build deploy help

# Defaults (override as needed)
IMAGE_TAG ?= latest
APP_FOLDER_NAME ?= compliance
IMAGE_NAME ?= mcp-tool-server
REGION ?= us-central1
PROJECT_ID ?= shoki-api
REPO_NAME ?= compliance-repo
SERVICE_NAME ?= mcp-tool-server
COMPLIANCE_API_URL ?= https://compliance-service-772943814292.us-central1.run.app

# Build and deploy image paths (as per your script)
IMAGE_PATH_BUILD := $(REGION)-docker.pkg.dev/$(PROJECT_ID)/$(REPO_NAME)/$(IMAGE_NAME):$(IMAGE_TAG)
IMAGE_PATH_DEPLOY := $(REGION)-docker.pkg.dev/$(PROJECT_ID)/$(REPO_NAME)/$(IMAGE_NAME):$(IMAGE_TAG)


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
	  --set-env-vars="COMPLIANCE_API_URL=$(COMPLIANCE_API_URL)" \
	  --project=$(PROJECT_ID) \
	  --min-instances=0

# Optional helper
help:
	@echo "Makefile targets:"
	@echo "  make build        Build and push the image to Artifact Registry"
	@echo "  make deploy       Deploy the image to Cloud Run with env vars"
	@echo "  make help         Show this help"