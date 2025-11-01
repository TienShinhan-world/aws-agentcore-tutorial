FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim
WORKDIR /app

# Environment variables
ENV UV_SYSTEM_PYTHON=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_NO_PROGRESS=1 \
    PYTHONUNBUFFERED=1 \
    DOCKER_CONTAINER=1 \
    AWS_REGION=eu-central-1 \
    AWS_DEFAULT_REGION=eu-central-1

# Copy and install dependencies
COPY requirements.txt requirements.txt
RUN uv pip install -r requirements.txt

# Install OpenTelemetry for observability
RUN uv pip install aws-opentelemetry-distro>=0.10.1

# Create non-root user
RUN useradd -m -u 1000 bedrock_agentcore
USER bedrock_agentcore

# Expose ports
EXPOSE 8000
EXPOSE 8080
EXPOSE 9000

# Copy entire project (respecting .dockerignore)
COPY . .

# Run the agent with OpenTelemetry instrumentation
CMD ["opentelemetry-instrument", "python", "src/agent/my_agent.py"]
