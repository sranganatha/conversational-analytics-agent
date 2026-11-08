PODMAN ?= podman
IMAGE ?= conversational-analytics-agent:test
export IMAGE
RUN_FLAGS = --rm --network none --read-only --tmpfs /tmp:rw,nosuid,nodev,size=64m --cap-drop all --security-opt no-new-privileges

.PHONY: build chat check demo model-down test test-container verify-model

build:
	$(PODMAN) build --tag $(IMAGE) .

check: build
	$(PODMAN) run $(RUN_FLAGS) $(IMAGE) python -m conversational_analytics_agent.fixtures

test: build
	$(PODMAN) run $(RUN_FLAGS) $(IMAGE) python -m unittest discover -s tests -v

test-container: build
	$(PODMAN) run $(RUN_FLAGS) $(IMAGE)

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
