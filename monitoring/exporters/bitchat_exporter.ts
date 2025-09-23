import express from 'express';
import client from 'prom-client';
import WebSocket from 'ws';

// Create a Registry
const register = new client.Registry();

// Add default metrics
client.collectDefaultMetrics({ register });

// BitChat specific metrics
const connectedClients = new client.Gauge({
  name: 'bitchat_connected_clients',
  help: 'Number of connected WebSocket clients',
  registers: [register]
});

const activeRooms = new client.Gauge({
  name: 'bitchat_active_rooms',
  help: 'Number of active chat rooms',
  registers: [register]
});

const messagesTotal = new client.Counter({
  name: 'bitchat_messages_total',
  help: 'Total messages sent',
  labelNames: ['room_id', 'message_type'],
  registers: [register]
});

const connectionsDropped = new client.Counter({
  name: 'bitchat_connections_dropped_total',
  help: 'Total connections dropped',
  labelNames: ['reason'],
  registers: [register]
});

const messageQueueSize = new client.Gauge({
  name: 'bitchat_message_queue_size',
  help: 'Current message queue size',
  registers: [register]
});

const messageLatency = new client.Histogram({
  name: 'bitchat_message_latency_seconds',
  help: 'Message delivery latency in seconds',
  labelNames: ['room_id'],
  buckets: [0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0],
  registers: [register]
});

const roomSize = new client.Histogram({
  name: 'bitchat_room_size',
  help: 'Number of users per room',
  labelNames: ['room_id'],
  buckets: [1, 2, 5, 10, 25, 50, 100, 250, 500],
  registers: [register]
});

const p2pLatency = new client.Histogram({
  name: 'bitchat_p2p_latency_seconds',
  help: 'P2P message latency in seconds',
  buckets: [0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.0],
  registers: [register]
});

const encryptionOperations = new client.Counter({
  name: 'bitchat_encryption_operations_total',
  help: 'Total encryption/decryption operations',
  labelNames: ['operation'],
  registers: [register]
});

// BitChat API client
class BitChatMetricsCollector {
  private wsUrl: string;
  private ws: WebSocket | null = null;
  private reconnectInterval: number = 5000;

  constructor(wsUrl: string) {
    this.wsUrl = wsUrl;
  }

  connect() {
    this.ws = new WebSocket(this.wsUrl);

    this.ws.on('open', () => {
      console.log('Connected to BitChat WebSocket');
      // Subscribe to metrics events
      this.ws?.send(JSON.stringify({
        type: 'subscribe',
        channel: 'metrics'
      }));
    });

    this.ws.on('message', (data: WebSocket.Data) => {
      try {
        const message = JSON.parse(data.toString());
        this.handleMetricsMessage(message);
      } catch (error) {
        console.error('Failed to parse metrics message:', error);
      }
    });

    this.ws.on('error', (error) => {
      console.error('WebSocket error:', error);
    });

    this.ws.on('close', () => {
      console.log('WebSocket closed, reconnecting...');
      setTimeout(() => this.connect(), this.reconnectInterval);
    });
  }

  private handleMetricsMessage(message: any) {
    switch (message.type) {
      case 'connected_clients':
        connectedClients.set(message.value);
        break;

      case 'active_rooms':
        activeRooms.set(message.value);
        break;

      case 'message':
        messagesTotal.inc({
          room_id: message.room_id,
          message_type: message.message_type
        });
        if (message.latency) {
          messageLatency.observe(
            { room_id: message.room_id },
            message.latency
          );
        }
        break;

      case 'connection_dropped':
        connectionsDropped.inc({ reason: message.reason });
        break;

      case 'queue_size':
        messageQueueSize.set(message.value);
        break;

      case 'room_users':
        roomSize.observe(
          { room_id: message.room_id },
          message.user_count
        );
        break;

      case 'p2p_latency':
        p2pLatency.observe(message.latency);
        break;

      case 'encryption':
        encryptionOperations.inc({ operation: message.operation });
        break;

      default:
        console.log('Unknown metrics message type:', message.type);
    }
  }

  disconnect() {
    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }
  }
}

// Express server
const app = express();
const port = process.env.METRICS_PORT || 9201;

// Metrics endpoint
app.get('/metrics', async (req, res) => {
  res.set('Content-Type', register.contentType);
  res.end(await register.metrics());
});

// Health endpoint
app.get('/health', (req, res) => {
  res.json({ status: 'healthy' });
});

// Start server
const server = app.listen(port, () => {
  console.log(`BitChat metrics exporter listening on port ${port}`);
});

// Connect to BitChat WebSocket
const wsUrl = process.env.BITCHAT_WS_URL || 'ws://localhost:3001';
const collector = new BitChatMetricsCollector(wsUrl);
collector.connect();

// Graceful shutdown
process.on('SIGTERM', () => {
  console.log('SIGTERM signal received: closing HTTP server');
  collector.disconnect();
  server.close(() => {
    console.log('HTTP server closed');
    process.exit(0);
  });
});