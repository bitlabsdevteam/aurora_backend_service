FROM python:3.12-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    redis-tools \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Install UV for Python package management
RUN pip install uv

# Copy project files
COPY pyproject.toml uv.lock README.md ./
COPY src/ ./src/
COPY knowledge/ ./knowledge/
COPY manage.py ./

# Create config directory if not exists
RUN mkdir -p src/aurora_backend_llm/config

# Copy config files
COPY src/aurora_backend_llm/config/ ./src/aurora_backend_llm/config/

# Copy migration files
COPY migrations/ ./migrations/
COPY alembic.ini ./

# Copy environment file
COPY .env ./.env

# Copy wait script
COPY wait-for-services.sh ./
RUN chmod +x wait-for-services.sh

# Install dependencies using UV
RUN uv pip install --system -e .

# Install queue packages
RUN uv pip install --system redis rq

# Create logs directory
RUN mkdir -p logs

# Expose API port
EXPOSE 3001

# Use wait script as entrypoint
ENTRYPOINT ["./wait-for-services.sh"]

# Command to run the app with a single worker
CMD ["python", "src/aurora_backend_llm/api/api_service.py", "--workers", "1"] 