FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY server.py .
COPY .env* ./

# Expose the MCP port
EXPOSE 9000

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV MCP_PORT=9000

# Run the server
CMD ["python", "server.py"]
