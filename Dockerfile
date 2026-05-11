
# Use an official Python runtime as a parent image
FROM python:3.11-slim

# Set the working directory in the container
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy the requirements file into the container at /app
COPY pyproject.toml .

# Install any needed packages specified in requirements.txt
# Since we use pyproject.toml without a lock file mostly, let's install .[dev] to be safe or just essential.
# For production, we usually want precise pinning.
RUN pip install --no-cache-dir .

# Copy the rest of the application code
COPY . .

# Install the package in editable mode or just install it
RUN pip install .

# Define environment variable
ENV PYTHONUNBUFFERED=1

# Run the command to start the application
# We can overwrite this in docker-compose
CMD ["signalvortex", "--help"]
