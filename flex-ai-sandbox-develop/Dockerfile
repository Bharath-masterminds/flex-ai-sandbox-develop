# Use internal Optum Python image
FROM edgeinternal1uhg.optum.com:443/glb-docker-uhg-loc/uhg-goldenimages/python:3.12-latest-dev

# Set the working directory
WORKDIR /app

# Add the local bin directory to PATH before installing dependencies
ENV PATH="/home/nonroot/.local/bin:$PATH"

# Copy requirements files
COPY requirements.txt /app/

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the application code
COPY . /app/

# Set environment variable to indicate we're running in Docker
ENV DOCKER_ENV=true

# Make port 8501 available for Streamlit
EXPOSE 8501

# Set the command to run the Streamlit application
CMD ["/home/nonroot/.local/bin/streamlit", "run", "use_cases/ops_resolve/streamlit_app.py", "--server.address=0.0.0.0"]