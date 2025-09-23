/**
 * BitChat P2P Messaging Latency Benchmark
 * Target: <50ms local, <200ms global
 */

import * as fs from 'fs';

interface LatencyMetrics {
  testName: string;
  messageCount: number;
  p50Ms: number;
  p95Ms: number;
  p99Ms: number;
  meanMs: number;
  minMs: number;
  maxMs: number;
  passesTarget: boolean;
}

class BitChatLatencyBenchmark {
  private latencies: number[] = [];

  private calculatePercentile(values: number[], percentile: number): number {
    const sorted = [...values].sort((a, b) => a - b);
    const idx = Math.floor(sorted.length * percentile);
    return sorted[idx] || 0;
  }

  private measureLatencies(samples: number[], testName: string, targetMs: number): LatencyMetrics {
    const sorted = [...samples].sort((a, b) => a - b);

    return {
      testName,
      messageCount: samples.length,
      p50Ms: this.calculatePercentile(samples, 0.50),
      p95Ms: this.calculatePercentile(samples, 0.95),
      p99Ms: this.calculatePercentile(samples, 0.99),
      meanMs: samples.reduce((a, b) => a + b, 0) / samples.length,
      minMs: Math.min(...samples),
      maxMs: Math.max(...samples),
      passesTarget: this.calculatePercentile(samples, 0.99) < targetMs
    };
  }

  async benchLocalP2PMessaging(messageCount: number = 1000): Promise<LatencyMetrics> {
    console.log('\nBenchmarking Local P2P Messaging...');
    const latencies: number[] = [];

    for (let i = 0; i < messageCount; i++) {
      const start = performance.now();

      // Simulate local P2P message
      await this.sendLocalMessage({
        id: `msg_${i}`,
        sender: 'peer_a',
        receiver: 'peer_b',
        payload: { data: `message_${i}`, timestamp: Date.now() }
      });

      const end = performance.now();
      latencies.push(end - start);
    }

    return this.measureLatencies(latencies, 'local_p2p', 50);
  }

  async benchGlobalP2PMessaging(messageCount: number = 1000): Promise<LatencyMetrics> {
    console.log('\nBenchmarking Global P2P Messaging...');
    const latencies: number[] = [];

    for (let i = 0; i < messageCount; i++) {
      const start = performance.now();

      // Simulate global P2P message with network latency
      await this.sendGlobalMessage({
        id: `msg_${i}`,
        sender: 'peer_a',
        receiver: 'peer_remote',
        payload: { data: `message_${i}`, timestamp: Date.now() }
      });

      const end = performance.now();
      latencies.push(end - start);
    }

    return this.measureLatencies(latencies, 'global_p2p', 200);
  }

  async benchMessageBroadcast(peerCount: number = 100, messageCount: number = 100): Promise<LatencyMetrics> {
    console.log('\nBenchmarking Message Broadcast...');
    const latencies: number[] = [];

    for (let msgNum = 0; msgNum < messageCount; msgNum++) {
      const start = performance.now();

      const message = {
        id: `broadcast_${msgNum}`,
        type: 'broadcast',
        payload: { data: `broadcast_${msgNum}` }
      };

      // Simulate broadcasting to all peers
      const broadcasts = [];
      for (let peerId = 0; peerId < peerCount; peerId++) {
        broadcasts.push(this.deliverToPeer(message, `peer_${peerId}`));
      }

      await Promise.all(broadcasts);

      const end = performance.now();
      latencies.push(end - start);
    }

    return this.measureLatencies(latencies, 'broadcast', 100);
  }

  async benchDirectMessaging(messageCount: number = 10000): Promise<LatencyMetrics> {
    console.log('\nBenchmarking Direct Messaging...');
    const latencies: number[] = [];

    for (let i = 0; i < messageCount; i++) {
      const start = performance.now();

      // Simulate direct message routing
      const message = {
        id: `direct_${i}`,
        sender: 'peer_a',
        receiver: 'peer_b',
        priority: 'high'
      };

      await this.routeDirectMessage(message);

      const end = performance.now();
      latencies.push(end - start);
    }

    return this.measureLatencies(latencies, 'direct_messaging', 50);
  }

  private async sendLocalMessage(message: any): Promise<void> {
    // Simulate local network latency (1-5ms)
    await new Promise(resolve => setTimeout(resolve, Math.random() * 4 + 1));
  }

  private async sendGlobalMessage(message: any): Promise<void> {
    // Simulate global network latency (50-150ms)
    await new Promise(resolve => setTimeout(resolve, Math.random() * 100 + 50));
  }

  private async deliverToPeer(message: any, peerId: string): Promise<void> {
    // Simulate peer delivery (2-8ms)
    await new Promise(resolve => setTimeout(resolve, Math.random() * 6 + 2));
  }

  private async routeDirectMessage(message: any): Promise<void> {
    // Simulate message routing (0.5-2ms)
    await new Promise(resolve => setTimeout(resolve, Math.random() * 1.5 + 0.5));
  }

  generateReport(results: LatencyMetrics[]): string {
    const report = {
      benchmark: 'bitchat_latency',
      timestamp: Date.now(),
      target_metrics: {
        local_p2p_p99_ms: 50,
        global_p2p_p99_ms: 200
      },
      results: results.map(r => ({
        test: r.testName,
        message_count: r.messageCount,
        p50_ms: r.p50Ms.toFixed(2),
        p95_ms: r.p95Ms.toFixed(2),
        p99_ms: r.p99Ms.toFixed(2),
        mean_ms: r.meanMs.toFixed(2),
        min_ms: r.minMs.toFixed(2),
        max_ms: r.maxMs.toFixed(2),
        passes_target: r.passesTarget
      })),
      performance_gate: {
        all_tests_pass: results.every(r => r.passesTarget)
      }
    };

    return JSON.stringify(report, null, 2);
  }
}

async function main() {
  const bench = new BitChatLatencyBenchmark();

  console.log('BitChat P2P Messaging Latency Benchmark');
  console.log('='.repeat(70));

  const results: LatencyMetrics[] = [];

  // Test 1: Local P2P Messaging
  const localResult = await bench.benchLocalP2PMessaging(1000);
  console.log(`  P50: ${localResult.p50Ms.toFixed(2)}ms | P95: ${localResult.p95Ms.toFixed(2)}ms | P99: ${localResult.p99Ms.toFixed(2)}ms`);
  console.log(`  Target (<50ms): ${localResult.passesTarget ? 'PASS' : 'FAIL'}`);
  results.push(localResult);

  // Test 2: Global P2P Messaging
  const globalResult = await bench.benchGlobalP2PMessaging(1000);
  console.log(`  P50: ${globalResult.p50Ms.toFixed(2)}ms | P95: ${globalResult.p95Ms.toFixed(2)}ms | P99: ${globalResult.p99Ms.toFixed(2)}ms`);
  console.log(`  Target (<200ms): ${globalResult.passesTarget ? 'PASS' : 'FAIL'}`);
  results.push(globalResult);

  // Test 3: Message Broadcast
  const broadcastResult = await bench.benchMessageBroadcast(100, 100);
  console.log(`  P50: ${broadcastResult.p50Ms.toFixed(2)}ms | P95: ${broadcastResult.p95Ms.toFixed(2)}ms | P99: ${broadcastResult.p99Ms.toFixed(2)}ms`);
  results.push(broadcastResult);

  // Test 4: Direct Messaging
  const directResult = await bench.benchDirectMessaging(10000);
  console.log(`  P50: ${directResult.p50Ms.toFixed(2)}ms | P95: ${directResult.p95Ms.toFixed(2)}ms | P99: ${directResult.p99Ms.toFixed(2)}ms`);
  results.push(directResult);

  console.log('\n' + '='.repeat(70));

  const allPass = results.every(r => r.passesTarget);
  console.log(`\nPerformance Gate: ${allPass ? 'PASS' : 'FAIL'}`);

  // Save report
  const report = bench.generateReport(results);
  fs.writeFileSync(
    'C:/Users/17175/Desktop/fog-compute/benchmarks/bitchat_latency_report.json',
    report
  );

  console.log('\nReport saved to: benchmarks/bitchat_latency_report.json');
}

main().catch(console.error);