import { NextResponse } from 'next/server';

export async function GET() {
  const stats = {
    devices: {
      total: Math.floor(Math.random() * 150) + 100,
      active: Math.floor(Math.random() * 100) + 50,
      charging: Math.floor(Math.random() * 50) + 20,
      thermal_throttle: Math.floor(Math.random() * 10)
    },
    compute: {
      totalCPU: Math.random() * 200 + 100,
      totalGPU: Math.random() * 50 + 20,
      totalMemory: Math.random() * 500 + 200,
      utilizationRate: Math.random() * 40 + 60
    },
    harvest: {
      tasksCompleted: Math.floor(Math.random() * 10000) + 5000,
      computeHoursCollected: Math.random() * 1000 + 500,
      energyEfficiency: Math.random() * 15 + 85
    },
    mobile: {
      android: Math.floor(Math.random() * 100) + 50,
      ios: Math.floor(Math.random() * 80) + 40,
      batteryHealthAvg: Math.random() * 10 + 90
    }
  };

  return NextResponse.json(stats);
}