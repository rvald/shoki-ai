FROM python:3.12-slim-bookworm
COPY --from=ghcr.io/astral-sh/uv:0.8.10 /uv /uvx /bin/

# Install the project into `/app`
WORKDIR /app

RUN uv venv /opt/venv
# Use the virtual environment automatically
ENV VIRTUAL_ENV=/opt/venv
# Place entry points in the environment at the front of the path
ENV PATH="/opt/venv/bin:$PATH"

# --- Dependency Installation ---
COPY requirements.txt /app/requirements.txt 
RUN uv pip install -r requirements.txt

# --- Application Code ---
COPY . /app

# --- Environment ---
ENV PYTHONPATH=/app

# Make port 8080 available to the world outside this container
# Cloud Run uses the PORT env var, but EXPOSE is good practice.
EXPOSE 8080

# --- Run the application ---
CMD ["uv", "run", "mcp_server.py"]