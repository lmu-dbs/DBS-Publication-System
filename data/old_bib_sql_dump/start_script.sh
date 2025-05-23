#!/bin/bash

# Fix SQL permission issues
chmod 644 /docker-entrypoint-initdb.d/01-bib.sql
chmod 644 /docker-entrypoint-initdb.d/02-mysql.sql

# Fix SQL files to remove definer issues
echo "Removing DEFINER clauses from SQL files..."
sed -i "s/DEFINER=\`[^`]*\`@\`[^`]*\`//g" /docker-entrypoint-initdb.d/01-bib.sql
sed -i "s/DEFINER=\`[^`]*\`@\`[^`]*\`//g" /docker-entrypoint-initdb.d/02-mysql.sql

# Initialize MySQL data directory if needed
if [ ! -d "/var/lib/mysql/mysql" ]; then
  echo "Initializing MySQL data directory..."
  mysqld --initialize-insecure --user=mysql
fi

# Start MySQL in background with explicit path to socket
echo "Starting MySQL server..."
mkdir -p /var/run/mysqld
chown -R mysql:mysql /var/run/mysqld
mysqld --user=mysql --skip-grant-tables &

# Give it a moment to start
echo "Waiting for MySQL to start..."
sleep 10

# Check if MySQL is running
if ! pgrep mysqld > /dev/null; then
  echo "ERROR: MySQL failed to start"
  exit 1
else
  echo "MySQL is running"
fi

# Create both databases if they don't exist
echo "Creating databases if they do not exist..."
mysql -e "CREATE DATABASE IF NOT EXISTS mysql;"
mysql -e "CREATE DATABASE IF NOT EXISTS bib;"

# First import mysql.sql (system tables)
echo "Importing mysql.sql first..."
mysql mysql < /docker-entrypoint-initdb.d/02-mysql.sql || echo "Warning: Some errors occurred during mysql.sql import"

# Then import bib.sql (application data)
echo "Importing bib.sql second..."
mysql bib < /docker-entrypoint-initdb.d/01-bib.sql || echo "Warning: Some errors occurred during bib.sql import"

# Run the Python converter script
echo "Running BibTeX conversion script..."
python3 /mysql_to_bibtex.py

echo "Process complete! BibTeX file should be available in /bibtex_output directory."

# Keep the container running if needed for debugging
if [ "$1" = "keep-alive" ]; then
  echo "Keeping container alive for debugging. Use Ctrl+C to exit."
  tail -f /dev/null
fi
