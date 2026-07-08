# Use official Python 3.10 slim image
FROM python:3.10-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    wget \
    make \
    tar \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Mustang from local source
COPY mustang.tgz /tmp/
WORKDIR /tmp
RUN tar -xzf mustang.tgz \
    && cd MUSTANG_v3.2.3 \
    && make \
    && cp bin/mustang-3.2.3 /usr/local/bin/mustang \
    && cd /app \
    && rm -rf /tmp/mustan*

# Return to app directory
WORKDIR /app

# Copy requirements file
COPY requirements.txt .

# --only-binary :all: refuses to build any package from source, which is
# what would otherwise let a compromised package's setup.py/build backend
# run arbitrary code during install. fpdf (see requirements.txt) ships no
# wheel at all and is exempted via --no-binary - everything else installs
# from a wheel only.
RUN pip install --no-cache-dir --only-binary :all: --no-binary fpdf -r requirements.txt

# Copy application code. Everything relevant to what's excluded from this
# (.env, .git, credentials) is covered by .dockerignore, not this line.
COPY . .

# Run as a non-root user - the base python image defaults to root, which
# this container has no actual need for (binds an unprivileged port, writes
# only under /app).
RUN useradd --create-home --shell /bin/bash appuser \
    && chown -R appuser:appuser /app
USER appuser

# Expose FastAPI port
EXPOSE 8000

# Healthcheck
HEALTHCHECK CMD curl --fail http://localhost:8000/health || exit 1

# Run the application
ENTRYPOINT ["uvicorn", "src.backend.api:app", "--host", "0.0.0.0", "--port", "8000"]
