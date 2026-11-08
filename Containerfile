FROM docker.io/library/python:3.12.12-slim-bookworm@sha256:2986c55feb36e6cae00fa1fefb454283e4b33f35e75ff8bdd123b134130be301

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 LANGSMITH_TRACING=false LANGCHAIN_TRACING_V2=false
WORKDIR /app
COPY requirements.lock .
RUN python -m pip install --no-cache-dir --only-binary=:all: --no-deps --require-hashes -r requirements.lock
COPY conversational_analytics_agent conversational_analytics_agent
COPY tests tests
COPY fixtures fixtures
COPY config config
RUN python -m conversational_analytics_agent.prepare fixtures data
USER 65532:65532
CMD ["sh", "-c", "python -m conversational_analytics_agent.fixtures && python -m unittest discover -s tests -v"]
