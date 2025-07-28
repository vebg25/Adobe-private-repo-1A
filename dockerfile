# To build the Docker image, run:
# docker build --platform linux/amd64 -t pdf-extractor:latest .

# To run the container, mount your local input/output directories:
# docker run --rm -v $(pwd)/input:/app/input -v $(pwd)/output:/app/output --network none pdf-extractor:latest

# Place your PDFs in a local 'input' directory before running.
# The JSON results will appear in a local 'output' directory.

# --- Dockerfile content starts here ---
# Use a slim, official Python base image compatible with AMD64
FROM --platform=linux/amd64 python:3.10-slim

# Set the working directory inside the container
WORKDIR /app

# Copy the requirements file into the container
COPY requirements.txt .

# Install the Python dependencies
# --no-cache-dir reduces the final image size
RUN pip install --no-cache-dir -r requirements.txt

# Copy the application source code into the container
COPY main.py .
COPY extractor.py .

# Define the command to run the application when the container starts
CMD ["python", "main.py"]



