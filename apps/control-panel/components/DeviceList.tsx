'use client';

import { useEffect, useState } from 'react';

interface Device {
  id: string;
  name: string;
  platform: 'android' | 'ios';
  status: 'harvesting' | 'charging' | 'idle' | 'thermal_throttle';
  battery: number;
  temperature: number;
  cpuContribution: number;
}

export function DeviceList() {
  const [devices, setDevices] = useState<Device[]>([]);

  useEffect(() => {
    const fetchDevices = async () => {
      try {
        const response = await fetch('/api/idle-compute/devices');
        const data = await response.json();
        setDevices(data.devices || []);
      } catch (error) {
        console.error('Failed to fetch devices:', error);
      }
    };

    fetchDevices();
    const interval = setInterval(fetchDevices, 5000);
    return () => clearInterval(interval);
  }, []);

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'harvesting': return 'text-green-400';
      case 'charging': return 'text-yellow-400';
      case 'thermal_throttle': return 'text-red-400';
      default: return 'text-gray-400';
    }
  };

  const getPlatformIcon = (platform: string) => {
    return platform === 'android' ? '🤖' : '🍎';
  };

  return (
    <div className="space-y-3">
      {devices.map((device) => (
        <div key={device.id} className="glass rounded-lg p-4 flex items-center justify-between">
          <div className="flex items-center gap-4">
            <div className="text-3xl">{getPlatformIcon(device.platform)}</div>
            <div>
              <div className="font-semibold">{device.name}</div>
              <div className="text-sm text-gray-400 capitalize">
                <span className={getStatusColor(device.status)}>
                  {device.status.replace('_', ' ')}
                </span>
              </div>
            </div>
          </div>
          <div className="grid grid-cols-3 gap-6 text-center">
            <div>
              <div className="text-sm text-gray-400">Battery</div>
              <div className={`font-semibold ${device.battery < 20 ? 'text-red-400' : 'text-green-400'}`}>
                {device.battery}%
              </div>
            </div>
            <div>
              <div className="text-sm text-gray-400">Temp</div>
              <div className={`font-semibold ${device.temperature > 40 ? 'text-red-400' : 'text-fog-cyan'}`}>
                {device.temperature}°C
              </div>
            </div>
            <div>
              <div className="text-sm text-gray-400">CPU</div>
              <div className="font-semibold">{device.cpuContribution.toFixed(1)} GHz</div>
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}