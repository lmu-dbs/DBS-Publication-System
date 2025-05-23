#!/bin/bash

# Create output directory for BibTeX files if it doesn't exist
mkdir -p bibtex_output

# Build and run the container
echo "Building and running MySQL + BibTeX converter container..."
docker build -t mysql-bibtex-converter -f Dockerfile .
docker run --name mysql-bibtex-container \
    -v "$(pwd)/bibtex_output:/bibtex_output" \
    --rm \
    mysql-bibtex-converter

echo "Process completed! BibTeX file should be available in bibtex_output/ directory."
