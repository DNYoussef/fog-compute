-- Fog Compute Database Setup Script
-- Run this with: psql -U postgres -f create_databases.sql

-- Create the fog_user
CREATE USER fog_user WITH PASSWORD 'fog_password';

-- Create production database
CREATE DATABASE fog_compute OWNER fog_user;

-- Create test database
CREATE DATABASE fog_compute_test OWNER fog_user;

-- Grant all privileges
GRANT ALL PRIVILEGES ON DATABASE fog_compute TO fog_user;
GRANT ALL PRIVILEGES ON DATABASE fog_compute_test TO fog_user;

-- Display success message
\echo ''
\echo '✓ Databases created successfully!'
\echo ''
\echo 'Databases:'
\echo '  - fog_compute (production)'
\echo '  - fog_compute_test (testing)'
\echo ''
\echo 'User: fog_user'
\echo 'Password: fog_password'
