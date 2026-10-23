# Runs the Instinct bridge and the Swytchcode CLI in one container.
# Build from instinct-book-my-trip/:  docker compose -f instinct-bridge/docker-compose.yml build
FROM python:3.12-slim

RUN apt-get update \
 && apt-get install -y --no-install-recommends nodejs npm ca-certificates tzdata \
 && rm -rf /var/lib/apt/lists/* \
 && npm install -g swytchcode@2.24.5 \
 && npm cache clean --force

WORKDIR /app/instinct-bridge
COPY instinct-bridge/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# The Swytchcode project: Duffel's tools and the policies. Keys aren't in it:
# they live in /root/.swytchcode, which is a volume.
COPY .swytchcode /app/.swytchcode
COPY instinct-bridge/*.py instinct-bridge/traveller.json.example ./

ENV SWYTCHCODE_PROJECT=/app \
    PYTHONUNBUFFERED=1

CMD ["python", "bridge.py"]
