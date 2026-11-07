FROM docker.io/library/python:3.12.12-slim-bookworm@sha256:2986c55feb36e6cae00fa1fefb454283e4b33f35e75ff8bdd123b134130be301

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY conversational_analytics_agent conversational_analytics_agent
COPY tests tests
COPY fixtures fixtures
USER 65532:65532
CMD ["sh", "-c", "python -m conversational_analytics_agent.fixtures && python -m unittest discover -s tests -v"]
