# Multi-stage build for optimized Docker image
FROM python:3.11-slim AS builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    curl \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first to leverage Docker cache
COPY deployment/requirements.txt .
# Install Python packages
RUN pip install --no-cache-dir --user -r requirements.txt

# Second stage for the final image
FROM python:3.11-slim

WORKDIR /app

# Install only runtime dependencies
RUN apt-get update && apt-get install -y \
    libpq5 \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Copy installed packages from builder stage
COPY --from=builder /root/.local /root/.local
ENV PATH=/root/.local/bin:$PATH

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Create necessary directories
RUN mkdir -p /app/logs /app/static/uploads

# Copy application code
COPY . .

# Expose the port
EXPOSE 5000

# Create volumes for persistent data
VOLUME ["/app/logs", "/app/static/uploads"]

# Set permissions
RUN chmod +x deployment/*.sh

# Health check
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
  CMD curl -f http://localhost:5000/ || exit 1

# Run gunicorn with optimal settings for production
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "4", "--worker-class", "gthread", "--threads", "2", "--timeout", "120", "--access-logfile", "-", "--error-logfile", "-", "main:app"]