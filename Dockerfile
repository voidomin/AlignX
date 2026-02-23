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
    && rm -rf /var/lib/apt/lists/*

# Install Mustang from local source
COPY mustang.tgz /tmp/
WORKDIR /tmp
RUN tar -xzf mustang.tgz \
    && cd MUSTANG_v.3.2.3 \
    && make \
    && cp bin/mustang /usr/local/bin/ \
    && cd /app \
    && rm -rf /tmp/mustan*

# Return to app directory
WORKDIR /app

# Copy requirements file
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Expose Streamlit port
EXPOSE 8501

# Healthcheck
HEALTHCHECK CMD curl --fail http://localhost:8501/_stcore/health

# Run the application
ENTRYPOINT ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"]
