FROM debian:bullseye-slim

# Install MySQL and Python
RUN apt-get update && apt-get install -y \
    default-mysql-server \
    default-mysql-client \
    python3 \
    python3-pip \
    procps \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
RUN pip3 install mysql-connector-python pybtex

# Configure MySQL
RUN mkdir -p /var/run/mysqld && \
    chown -R mysql:mysql /var/run/mysqld && \
    mkdir -p /var/lib/mysql && \
    chown -R mysql:mysql /var/lib/mysql

# Create directory for SQL files
RUN mkdir -p /docker-entrypoint-initdb.d

# Copy SQL dump files
COPY bib.sql /docker-entrypoint-initdb.d/01-bib.sql
COPY mysql.sql /docker-entrypoint-initdb.d/02-mysql.sql

# Copy the converter script
COPY mysql_to_bibtex.py /

# Create directory for output
RUN mkdir -p /bibtex_output

# Create a startup script
COPY start_script.sh /start_script.sh
RUN chmod +x /start_script.sh

# Set the entry point
ENTRYPOINT ["/start_script.sh"]
