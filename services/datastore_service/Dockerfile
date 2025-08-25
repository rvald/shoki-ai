FROM python:3.12-slim-bookworm
COPY --from=ghcr.io/astral-sh/uv:0.8.10 /uv /uvx /bin/

# Install ffmpeg (system dependency for audio processing)
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

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

# Run the FastAPI application by default
# Uses `fastapi dev` to enable hot-reloading when the `watch` sync occurs
# Uses `--host 0.0.0.0` to allow access from outside the container
CMD ["uv", "run", "fastapi", "run", "--host", "0.0.0.0", "--port", "8080"]