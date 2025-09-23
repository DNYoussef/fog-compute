#!/bin/bash

# Fog Compute Monitoring Stack Startup Script
set -e

echo "🚀 Starting Fog Compute Monitoring Stack..."

# Check if .env exists
if [ ! -f .env ]; then
    echo "⚠️  Warning: .env file not found. Creating from template..."
    cat > .env << EOF
GRAFANA_ADMIN_PASSWORD=changeme
SMTP_HOST=smtp.gmail.com:587
SMTP_USER=
SMTP_PASSWORD=
SMTP_FROM=alerts@fogcompute.dev
SLACK_WEBHOOK_URL=
PAGERDUTY_SERVICE_KEY=
ALERT_EMAIL=ops@fogcompute.dev
BETANET_API_URL=http://betanet:8080
BITCHAT_WS_URL=ws://bitchat:3001
SENTRY_DB_PASSWORD=secure-password
EOF
    echo "📝 Please edit .env with your configuration"
    exit 1
fi

# Create Docker network if it doesn't exist
if ! docker network inspect fog-compute-network &> /dev/null; then
    echo "📡 Creating fog-compute-network..."
    docker network create fog-compute-network
fi

# Build custom exporters
echo "🔨 Building Betanet exporter (Rust)..."
cd exporters
docker build -t fog-compute-betanet-exporter -f Dockerfile.betanet-exporter .

echo "🔨 Building BitChat exporter (TypeScript)..."
docker build -t fog-compute-bitchat-exporter -f Dockerfile.bitchat-exporter .
cd ..

# Start monitoring stack
echo "🐳 Starting Docker containers..."
docker-compose -f docker-compose.monitoring.yml up -d

# Wait for services to be healthy
echo "⏳ Waiting for services to be healthy..."
sleep 15

# Check service health
check_service() {
    local service=$1
    local url=$2
    local max_attempts=30
    local attempt=1

    echo -n "Checking $service..."
    while [ $attempt -le $max_attempts ]; do
        if curl -sf "$url" > /dev/null 2>&1; then
            echo " ✅"
            return 0
        fi
        echo -n "."
        sleep 2
        attempt=$((attempt + 1))
    done
    echo " ❌ Failed to start"
    return 1
}

check_service "Prometheus" "http://localhost:9090/-/healthy"
check_service "Grafana" "http://localhost:3000/api/health"
check_service "Loki" "http://localhost:3100/ready"
check_service "Tempo" "http://localhost:3200/ready"
check_service "Jaeger" "http://localhost:16686/"
check_service "AlertManager" "http://localhost:9093/-/healthy"
check_service "Betanet Exporter" "http://localhost:9200/health"
check_service "BitChat Exporter" "http://localhost:9201/health"
check_service "Uptime Kuma" "http://localhost:3001/"

echo ""
echo "✨ Monitoring stack started successfully!"
echo ""
echo "📊 Access your dashboards:"
echo "  - Grafana:      http://localhost:3000 (admin/changeme)"
echo "  - Prometheus:   http://localhost:9090"
echo "  - Loki:         http://localhost:3100"
echo "  - Tempo:        http://localhost:3200"
echo "  - Jaeger:       http://localhost:16686"
echo "  - Uptime Kuma:  http://localhost:3001"
echo "  - AlertManager: http://localhost:9093"
echo ""
echo "📈 Metrics endpoints:"
echo "  - Betanet:      http://localhost:9200/metrics"
echo "  - BitChat:      http://localhost:9201/metrics"
echo "  - Node:         http://localhost:9101/metrics"
echo "  - cAdvisor:     http://localhost:9102/metrics"
echo ""
echo "📋 Logs (Loki):"
echo "  - Query via Grafana Explore"
echo "  - API: http://localhost:3100/loki/api/v1/query"
echo ""
echo "🔍 Distributed Tracing:"
echo "  - Jaeger UI: http://localhost:16686"
echo "  - Tempo API: http://localhost:3200"
echo ""
echo "⚠️  Next steps:"
echo "  1. Change default Grafana password"
echo "  2. Configure alert recipients in .env"
echo "  3. Set up Slack/PagerDuty integrations"
echo "  4. Review alert rules in alerting/rules.yml"
echo "  5. Configure Uptime Kuma monitors"
echo "  6. Set up Sentry error tracking"
echo ""