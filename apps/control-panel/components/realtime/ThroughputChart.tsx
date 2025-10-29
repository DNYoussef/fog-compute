'use client';

import { useState, useEffect } from 'react';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';

interface ThroughputDataPoint {
  time: string;
  value: number;
}

export function ThroughputChart() {
  const [data, setData] = useState<ThroughputDataPoint[]>([]);
  const [ws, setWs] = useState<WebSocket | null>(null);
  const [connectionStatus, setConnectionStatus] = useState<'connecting' | 'connected' | 'disconnected'>('connecting');

  useEffect(() => {
    let websocket: WebSocket | null = null;
    let reconnectTimeout: NodeJS.Timeout;
    let mockInterval: NodeJS.Timeout;
    let isUnmounted = false;

    const connect = () => {
      if (isUnmounted) return;

      try {
        setConnectionStatus('connecting');
        websocket = new WebSocket('ws://localhost:8000/ws');

        websocket.onopen = () => {
          console.log('✅ ThroughputChart WebSocket connected');
          setConnectionStatus('connected');

          websocket?.send(JSON.stringify({
            type: 'subscribe',
            rooms: ['metrics']
          }));
        };

        websocket.onmessage = (event) => {
          try {
            const message = JSON.parse(event.data);

            if (message.type === 'throughput_update' || message.type === 'metrics_update') {
              const throughput = message.data?.throughput || message.data?.network?.throughput || 0;

              setData((prevData) => {
                const newData = [
                  ...prevData,
                  {
                    time: new Date().toLocaleTimeString(),
                    value: throughput,
                  },
                ];
                return newData.slice(-20);
              });
            }
          } catch (err) {
            console.error('Failed to parse WebSocket message:', err);
          }
        };

        websocket.onerror = (error) => {
          console.error('WebSocket error:', error);
          setConnectionStatus('disconnected');
        };

        websocket.onclose = () => {
          console.log('WebSocket closed, attempting reconnect...');
          setConnectionStatus('disconnected');
          setWs(null);

          if (!isUnmounted) {
            reconnectTimeout = setTimeout(() => {
              connect();
            }, 5000);
          }
        };

        setWs(websocket);
      } catch (error) {
        console.error('Failed to create WebSocket:', error);
        setConnectionStatus('disconnected');

        if (!isUnmounted) {
          mockInterval = setInterval(() => {
            setData((prevData) => {
              const newData = [
                ...prevData,
                {
                  time: new Date().toLocaleTimeString(),
                  value: Math.random() * 100 + 50,
                },
              ];
              return newData.slice(-20);
            });
          }, 2000);
        }
      }
    };

    connect();

    return () => {
      isUnmounted = true;
      if (reconnectTimeout) clearTimeout(reconnectTimeout);
      if (mockInterval) clearInterval(mockInterval);
      if (websocket && websocket.readyState === WebSocket.OPEN) {
        websocket.close();
      }
    };
  }, []);

  return (
    <div data-testid="throughput-chart" className="bg-gray-900 border border-gray-800 rounded-lg p-6">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-semibold text-white">Network Throughput</h3>
        <div className="text-sm">
          {connectionStatus === 'connected' && (
            <span className="text-green-500">● Live</span>
          )}
          {connectionStatus === 'connecting' && (
            <span className="text-yellow-500">● Connecting...</span>
          )}
          {connectionStatus === 'disconnected' && (
            <span className="text-red-500">● Disconnected</span>
          )}
        </div>
      </div>

      {data.length === 0 ? (
        <div className="h-64 flex items-center justify-center text-gray-400">
          Waiting for data...
        </div>
      ) : (
        <ResponsiveContainer width="100%" height={300}>
          <LineChart data={data}>
            <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
            <XAxis
              dataKey="time"
              stroke="#9CA3AF"
              style={{ fontSize: '12px' }}
            />
            <YAxis
              stroke="#9CA3AF"
              style={{ fontSize: '12px' }}
              label={{ value: 'Mbps', angle: -90, position: 'insideLeft', fill: '#9CA3AF' }}
            />
            <Tooltip
              contentStyle={{
                backgroundColor: '#1F2937',
                border: '1px solid #374151',
                borderRadius: '8px',
                color: '#fff'
              }}
            />
            <Line
              type="monotone"
              dataKey="value"
              stroke="#3B82F6"
              strokeWidth={2}
              dot={false}
              name="Throughput"
              isAnimationActive={false}
            />
          </LineChart>
        </ResponsiveContainer>
      )}

      {data.length > 0 && (
        <div className="mt-4 text-sm text-gray-400">
          Current: <span className="text-white font-semibold">{data[data.length - 1]?.value.toFixed(1)} Mbps</span>
        </div>
      )}
    </div>
  );
}
