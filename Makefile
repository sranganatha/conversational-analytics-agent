PODMAN ?= podman
IMAGE ?= conversational-analytics-agent:test

.PHONY: build check test test-container

build:
	$(PODMAN) build --tag $(IMAGE) .

check: build
	$(PODMAN) run --rm --network none --read-only --cap-drop all --security-opt no-new-privileges $(IMAGE) python -m conversational_analytics_agent.fixtures

test: build
	$(PODMAN) run --rm --network none --read-only --cap-drop all --security-opt no-new-privileges $(IMAGE) python -m unittest discover -s tests -v

test-container: build
	$(PODMAN) run --rm --network none --read-only --cap-drop all --security-opt no-new-privileges $(IMAGE)
