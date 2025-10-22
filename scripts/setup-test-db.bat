@echo off
REM Fog Compute Database Setup Script
set PGPASSWORD=1qazXSW@3edc
set PSQL="C:\Program Files\PostgreSQL\15\bin\psql.exe"

echo Creating user fog_user...
%PSQL% -U postgres -c "CREATE USER fog_user WITH PASSWORD 'fog_password';" 2>nul

echo Creating databases...
%PSQL% -U postgres -c "CREATE DATABASE fog_compute OWNER fog_user;" 2>nul
%PSQL% -U postgres -c "CREATE DATABASE fog_compute_test OWNER fog_user;" 2>nul

echo Granting privileges...
%PSQL% -U postgres -c "GRANT ALL PRIVILEGES ON DATABASE fog_compute TO fog_user;"
%PSQL% -U postgres -c "GRANT ALL PRIVILEGES ON DATABASE fog_compute_test TO fog_user;"

echo Done!
