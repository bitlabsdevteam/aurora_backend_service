#!/bin/bash
set -e

# Function to check Redis
check_redis() {
  echo "Checking Redis connection..."
  redis-cli -h redis ping | grep -q "PONG" || exit 1
  echo "Redis is ready"
}

# Function to check PostgreSQL
check_postgres() {
  echo "Checking PostgreSQL connection..."
  pg_isready -h postgres -U postgres || exit 1
  echo "PostgreSQL is ready"
}

# Main check loop
echo "Waiting for services to be ready..."
until check_redis && check_postgres; do
  echo "Services not ready yet. Waiting..."
  sleep 2
done

echo "All services are ready. Starting the application..."
exec "$@" 