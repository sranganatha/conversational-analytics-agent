PODMAN ?= podman
IMAGE ?= conversational-analytics-agent:test
export IMAGE
EVALUATION_IMAGE = conversational-analytics-agent:evaluation
EVALUATION_OUTPUT ?= artifacts/task-contracts-v2
VERIFY_OUTPUT ?= artifacts/task-contracts-v2
export EVALUATION_OUTPUT VERIFY_OUTPUT
SOURCE_REVISION := $(shell git -c safe.directory="$(CURDIR)" rev-parse HEAD)
export SOURCE_REVISION
RUN_FLAGS = --rm --network none --read-only --tmpfs /tmp:rw,nosuid,nodev,size=64m --cap-drop all --security-opt no-new-privileges

.PHONY: build build-evaluation chat check demo model-down test test-container verify-model calibrate-judge evaluate-development evaluate-regression evaluate-ragas

build:
	$(PODMAN) build --tag $(IMAGE) .

check: build
	$(PODMAN) run $(RUN_FLAGS) $(IMAGE) python -m conversational_analytics_agent.fixtures

test: build
	$(PODMAN) run $(RUN_FLAGS) $(IMAGE) python -m unittest discover -s tests -v

build-evaluation: build
	$(PODMAN) build -f Containerfile.evaluation --tag $(EVALUATION_IMAGE) .

test-container: build-evaluation
	$(PODMAN) run $(RUN_FLAGS) $(EVALUATION_IMAGE)

calibrate-judge evaluate-development evaluate-regression evaluate-ragas: build-evaluation
	$(PODMAN) compose -f compose.model.yaml up -d ollama
	$(PODMAN) compose -f compose.model.yaml run --rm pull-model
	$(PODMAN) compose -f compose.model.yaml run --rm --no-deps evaluation $(if $(filter calibrate-judge,$@),calibrate,$(if $(filter evaluate-development,$@),development,$(if $(filter evaluate-regression,$@),regression,holdout))) --output $(EVALUATION_OUTPUT)

demo: build
	$(PODMAN) run $(RUN_FLAGS) $(IMAGE) python -m conversational_analytics_agent.demo

verify-model: build
	$(PODMAN) compose -f compose.model.yaml up -d ollama
	$(PODMAN) compose -f compose.model.yaml run --rm pull-model
	$(PODMAN) compose -f compose.model.yaml run --rm --no-deps verify

model-down:
	$(PODMAN) compose -f compose.model.yaml down

chat: build
	$(PODMAN) compose -f compose.model.yaml up -d ollama
	$(PODMAN) compose -f compose.model.yaml run --rm pull-model
	$(PODMAN) compose -f compose.model.yaml run --rm --no-deps chat
