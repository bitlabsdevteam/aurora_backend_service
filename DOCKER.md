# Docker Deployment for Aurora Backend Service

This guide explains how to deploy the Aurora Backend Service using Docker and Docker Compose.

## Prerequisites

- [Docker](https://docs.docker.com/get-docker/)
- [Docker Compose](https://docs.docker.com/compose/install/)

## Quick Start

1. Clone the repository (if you haven't already):
   ```
   git clone <repository-url>
   cd aurora_backend_service
   ```

2. Make sure your `.env` file is properly set up with your API keys:
   ```
   OPENAI_API_KEY=your_openai_api_key
   GEMINI_API_KEY=your_gemini_api_key
   ```

3. Start the service using Docker Compose:
   ```
   docker-compose up -d
   ```

4. The API will be available at: http://localhost:3001

5. Access the API documentation at: http://localhost:3001/docs

## Services

The Docker Compose setup includes the following services:

### Aurora API Service
- The main application service running on port 3001
- Configuration through environment variables
- Logs stored in the `./logs` directory

### PostgreSQL
- PostgreSQL database running on port 5432
- Default credentials:
  - Database: `aurora_db`
  - Username: `aurora`
  - Password: `password`
- Data persisted in a named volume

### Redis
- Redis server running on port 6379
- Used for queue management and caching
- Data persisted in a named volume with AOF (Append Only File) enabled

## Connection Information

The Aurora API service is pre-configured to connect to the database and Redis using these environment variables:
- `DATABASE_URL=postgresql://aurora:password@postgres:5432/aurora_db`
- `REDIS_URL=redis://redis:6379/0`

## Managing the Service

- View logs:
  ```
  docker-compose logs -f
  ```

- Stop the service:
  ```
  docker-compose down
  ```

- Rebuild and restart the service (after code changes):
  ```
  docker-compose up -d --build
  ```

- Access PostgreSQL directly:
  ```
  docker exec -it aurora-postgres psql -U aurora -d aurora_db
  ```

- Access Redis CLI:
  ```
  docker exec -it aurora-redis redis-cli
  ```

## Configuration

- Port: The service runs on port 3001 by default. To change it, modify the `docker-compose.yml` file.
- Database settings: Modify the PostgreSQL environment variables in `docker-compose.yml`.
- Redis settings: Modify the Redis command and settings in `docker-compose.yml`.

## Health Check

All services include health checks for improved reliability:
- Aurora API: `/health` endpoint
- PostgreSQL: `pg_isready` command
- Redis: `ping` command

## Data Persistence

All data is persisted using Docker volumes:
- `postgres_data`: PostgreSQL database files
- `redis_data`: Redis data files 