PODMAN ?= podman
IMAGE ?= conversational-analytics-agent:test
RUN_FLAGS = --rm --network none --read-only --tmpfs /tmp:rw,nosuid,nodev,size=64m --cap-drop all --security-opt no-new-privileges

.PHONY: build check demo test test-container

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
