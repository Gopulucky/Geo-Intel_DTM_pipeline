FROM python:3.10-slim

WORKDIR /app

# Install system dependencies (Bug 7: added proj-bin libproj-dev for pyproj)
RUN apt-get update && apt-get install -y \
    gdal-bin \
    libgdal-dev \
    proj-bin \
    libproj-dev \
    gcc \
    g++ \
    wget \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy all backend code
COPY . .

# Pipeline files must be placed INTO backend/ before building.
# Use a build script or GitHub Action to copy them:
#   cp GEO_INTEL_pipeline.py Hydrology_pipeline.py lulc_pipeline.py InteractiveMap.py backend/
# They are NOT copied via ../ (Docker forbids parent-directory references).

EXPOSE 7860

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "7860"]
