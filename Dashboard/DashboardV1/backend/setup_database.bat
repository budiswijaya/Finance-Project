@echo off
echo Setting up PostgreSQL database for Finance Dashboard...
echo.

echo 1. Download and install PostgreSQL from: https://www.postgresql.org/download/windows/
echo 2. During installation, set password for 'postgres' user to match your .env file
echo 3. After installation, run this script to set up the database
echo.
echo Press any key to continue with database setup...
pause >nul

echo.
echo Creating database and tables...
echo.

REM Create database
createdb -U postgres finance_dashboard

REM Run schema setup
psql -U postgres -d finance_dashboard -f database_setup.sql

echo.
echo Database setup complete!
echo.
echo You can now run the backend with: python main.py
echo.
pause