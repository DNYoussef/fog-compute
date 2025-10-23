@echo off
REM Script to run Python tests with Docker services

echo Starting test services (Redis, PostgreSQL)...
docker-compose -f docker-compose.test.yml up -d test-redis test-postgres

echo Waiting for services to be healthy...
timeout /t 10 /nobreak

echo Running Python tests...
cd backend
python -m pytest tests/ -v --tb=short

echo.
echo Test run complete!
echo.
echo To stop test services:
echo   docker-compose -f docker-compose.test.yml down
