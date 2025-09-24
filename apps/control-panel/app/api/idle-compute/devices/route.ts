import { NextResponse } from 'next/server';

export async function GET() {
  const platforms = ['android', 'ios'];
  const statuses = ['harvesting', 'charging', 'idle', 'thermal_throttle'];
  const deviceNames = [
    'Pixel 7 Pro', 'iPhone 14', 'Galaxy S23', 'OnePlus 11', 'iPhone 13 Mini',
    'Pixel 6a', 'Galaxy A54', 'iPhone 15 Pro', 'Xiaomi 13', 'Motorola Edge'
  ];

  const devices = Array.from({ length: 12 }, (_, i) => ({
    id: `device-${i}`,
    name: deviceNames[i % deviceNames.length] + ` (${i + 1})`,
    platform: platforms[Math.floor(Math.random() * platforms.length)] as 'android' | 'ios',
    status: statuses[Math.floor(Math.random() * statuses.length)] as any,
    battery: Math.floor(Math.random() * 60) + 40,
    temperature: Math.floor(Math.random() * 15) + 30,
    cpuContribution: Math.random() * 8 + 2
  }));

  return NextResponse.json({ devices });
}