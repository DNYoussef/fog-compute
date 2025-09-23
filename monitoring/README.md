# Fog Compute Production Monitoring & Observability

Complete observability stack for Fog Compute distributed system (Betanet + BitChat + Control Panel).

## 🚀 Quick Start

```bash
# Start monitoring stack
cd monitoring
docker-compose -f docker-compose.monitoring.yml up -d

# Access services
# Grafana: http://localhost:3000 (admin/changeme)
# Prometheus: http://localhost:9090
# Loki (logs): http://localhost:3100
# Tempo (traces): http://localhost:3200
# Jaeger UI: http://localhost:16686
# Uptime Kuma: http://localhost:3001
```

## 📊 Full Observability Stack

### Metrics (Prometheus + Exporters)
- **Prometheus**: 90-day retention, multi-language scraping
- **Betanet Exporter**: Rust-based mixnode & VRF metrics
- **BitChat Exporter**: TypeScript P2P & WebSocket metrics
- **Node Exporter**: System metrics
- **cAdvisor**: Container metrics

### Logs (Loki + Promtail)
- **Loki**: Log aggregation with 14-day retention
- **Promtail**: Multi-source log shipping
  - Docker containers
  - System logs
  - Application logs (Betanet, BitChat, Control Panel)

### Traces (Tempo + Jaeger)
- **Tempo**: Distributed tracing backend
- **Jaeger**: Tracing UI with service graphs
- **OpenTelemetry**: Multi-language instrumentation

### Uptime & Errors
- **Uptime Kuma**: Visual uptime monitoring
- **Sentry**: Error tracking and crash reporting
- **AlertManager**: Unified alerting

## 🔧 Configuration

### Environment Variables

Create `.env`:

```env
# Grafana
GRAFANA_ADMIN_PASSWORD=your-secure-password

# SMTP
SMTP_HOST=smtp.gmail.com:587
SMTP_USER=alerts@fogcompute.dev
SMTP_PASSWORD=your-app-password
SMTP_FROM=noreply@fogcompute.dev

# Slack
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/YOUR/WEBHOOK

# PagerDuty
PAGERDUTY_SERVICE_KEY=your-key

# Alert recipients
ALERT_EMAIL=ops@fogcompute.dev

# Service URLs
BETANET_API_URL=http://betanet:8080
BITCHAT_WS_URL=ws://bitchat:3001

# Sentry
SENTRY_DB_PASSWORD=secure-password
SENTRY_DSN=https://your-sentry-dsn
```

## 📈 Metrics by Component

### Betanet Network Metrics
```
# Network health
fogcompute_betanet_connected_peers
fogcompute_betanet_bytes_transmitted_total
fogcompute_betanet_bytes_received_total
fogcompute_betanet_packets_dropped_total

# Mixnode performance
fogcompute_betanet_mixnode_active
fogcompute_betanet_mixnode_failures_total
fogcompute_betanet_routing_failures_total

# Latency
fogcompute_betanet_message_latency_seconds
fogcompute_betanet_routing_latency_seconds
fogcompute_betanet_circuit_build_seconds

# VRF
fogcompute_betanet_vrf_verifications_total
fogcompute_betanet_vrf_failures_total
```

### BitChat P2P Metrics
```
# Connections
fogcompute_bitchat_connected_clients
fogcompute_bitchat_active_rooms
fogcompute_bitchat_connections_dropped_total

# Messaging
fogcompute_bitchat_messages_total{room_id,message_type}
fogcompute_bitchat_message_queue_size
fogcompute_bitchat_message_latency_seconds

# Security
fogcompute_bitchat_encryption_operations_total{operation}
fogcompute_bitchat_p2p_latency_seconds

# Performance
fogcompute_bitchat_room_size
```

### Control Panel Metrics
```
# HTTP requests
http_requests_total{status,method,path}
http_request_duration_seconds

# Next.js specific
nextjs_page_render_duration_seconds
nextjs_api_latency_seconds
```

## 🚨 Alert Rules

### Critical Alerts
- **BetanetNodeDown**: Node unavailable 2+ minutes → PagerDuty + Slack
- **BitChatServiceDown**: Service down 2+ minutes → PagerDuty + Slack
- **ControlPanelDown**: UI unavailable 2+ minutes → PagerDuty + Slack
- **HighMemoryUsage**: >90% memory → Slack
- **DiskSpaceLow**: <10% disk space → Slack

### Network Alerts
- **BetanetHighPacketLoss**: >5% packet loss for 5 min
- **BetanetLowPeerCount**: <3 peers for 10 min
- **BetanetMixnodeFailure**: >5 failures in 5 min
- **BetanetRoutingFailure**: >0.1 failures/sec

### Performance Alerts
- **SlowBetanetThroughput**: <1MB/s for 10 min
- **HighBitChatMessageLatency**: 95th p > 500ms
- **SlowControlPanelResponse**: 95th p > 2s

## 🔍 Log Queries (Loki)

### Search by service
```logql
{service="betanet"}
{service="bitchat"}
{service="control-panel"}
```

### Error logs
```logql
{service="betanet"} |= "error" | json
{service="bitchat"} | level="error"
```

### Trace correlation
```logql
{service="betanet"} | json | trace_id="abc123"
```

## 🔎 Distributed Tracing

### Rust (Betanet) Instrumentation

```rust
use opentelemetry::{global, trace::Tracer};
use opentelemetry_jaeger::new_pipeline;

// Initialize tracer
let tracer = new_pipeline()
    .with_service_name("betanet")
    .with_agent_endpoint("jaeger:6831")
    .install_simple()
    .expect("Failed to install tracer");

// Use in code
let span = tracer.start("process_message");
// ... your code ...
span.end();
```

### TypeScript (BitChat) Instrumentation

```typescript
import { trace } from '@opentelemetry/api';
import { JaegerExporter } from '@opentelemetry/exporter-jaeger';
import { NodeTracerProvider } from '@opentelemetry/sdk-trace-node';

// Setup
const provider = new NodeTracerProvider();
const exporter = new JaegerExporter({
  endpoint: 'http://jaeger:14268/api/traces',
  serviceName: 'bitchat'
});
provider.addSpanProcessor(new BatchSpanProcessor(exporter));
provider.register();

// Use
const tracer = trace.getTracer('bitchat');
const span = tracer.startSpan('send_message');
// ... your code ...
span.end();
```

### Python (Control Panel) Instrumentation

```python
from opentelemetry import trace
from opentelemetry.exporter.jaeger.thrift import JaegerExporter
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

# Setup
provider = TracerProvider()
jaeger = JaegerExporter(
    agent_host_name="jaeger",
    agent_port=6831,
)
provider.add_span_processor(BatchSpanProcessor(jaeger))
trace.set_tracer_provider(provider)

tracer = trace.get_tracer(__name__)

# Use
with tracer.start_as_current_span("api_call"):
    # your code
    pass
```

## 📊 Grafana Dashboards

### Pre-configured Dashboards

1. **Betanet Network** (`/d/betanet`)
   - Connected peers
   - Message throughput
   - Mixnode status
   - VRF performance
   - Network latency

2. **BitChat P2P** (`/d/bitchat`)
   - Active connections
   - Message rates
   - Room statistics
   - Encryption metrics
   - P2P latency

3. **System Performance** (`/d/system`)
   - CPU/Memory/Disk usage
   - Container metrics
   - Network I/O
   - Process stats

4. **Control Panel** (`/d/control-panel`)
   - HTTP request rates
   - Response times
   - Error rates
   - User activity

5. **Logs Dashboard** (`/d/logs`)
   - Live log streaming
   - Error aggregation
   - Service correlation
   - Trace links

## 🔐 Security & Compliance

### Authentication
- Grafana: Basic auth with strong password
- Prometheus/Loki/Tempo: Internal network only
- Uptime Kuma: Separate auth configuration

### Data Retention
- Metrics: 90 days
- Logs: 14 days
- Traces: 3 days
- Alerts: 7 days

### Backup Strategy

```bash
# Backup all persistent data
docker-compose -f docker-compose.monitoring.yml exec prometheus \
  tar czf /backup/prometheus-$(date +%Y%m%d).tar.gz /prometheus

docker-compose -f docker-compose.monitoring.yml exec loki \
  tar czf /backup/loki-$(date +%Y%m%d).tar.gz /loki

docker-compose -f docker-compose.monitoring.yml exec tempo \
  tar czf /backup/tempo-$(date +%Y%m%d).tar.gz /tmp/tempo
```

## 🔄 High Availability

### Prometheus HA Setup

For production HA, use Prometheus federation:

```yaml
# prometheus-ha.yml
- job_name: 'federate'
  honor_labels: true
  metrics_path: '/federate'
  params:
    'match[]':
      - '{job=~"betanet|bitchat|control-panel"}'
  static_configs:
    - targets:
      - 'prometheus-01:9090'
      - 'prometheus-02:9090'
```

### Loki HA

Use distributed mode with object storage:

```yaml
# loki-ha.yml
storage_config:
  aws:
    s3: s3://region/bucket
    s3forcepathstyle: true
```

## 📞 Runbook & Troubleshooting

### Common Issues

**High Memory Usage**
1. Check container metrics in Grafana
2. Identify memory-hungry process
3. Scale horizontally or increase resources

**Network Latency Spikes**
1. Check Betanet peer count
2. Verify routing failures
3. Inspect mixnode health

**Message Queue Backlog**
1. Check BitChat message queue size
2. Verify WebSocket connections
3. Scale BitChat workers

## 🎯 SLA & Monitoring

### Service Level Objectives
- Betanet availability: 99.9%
- BitChat availability: 99.5%
- Control Panel availability: 99.9%
- Message latency p95: <500ms
- Network throughput: >1MB/s

### Monitoring Checklist
- [ ] All services reporting to Prometheus
- [ ] Alert rules configured and tested
- [ ] Dashboards accessible and populated
- [ ] Log aggregation working
- [ ] Distributed tracing enabled
- [ ] Backup jobs scheduled
- [ ] Team notifications configured

## 📞 Support

- **Documentation**: See individual READMEs
- **Alerts**: #fog-compute-alerts (Slack)
- **Critical**: PagerDuty escalation
- **Email**: ops@fogcompute.dev