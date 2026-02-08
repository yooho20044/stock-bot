# Base image
FROM python:3.12-slim

# Set working directory
WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY . .

# Environment variables (Optional: can be overridden at runtime)
# ENV PYTHONUNBUFFERED=1

# Run the application
CMD ["python", "main.py"]
