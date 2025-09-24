import { NextResponse } from 'next/server';

export async function GET() {
  const slas = ['platinum', 'gold', 'silver', 'bronze'];
  const statuses = ['queued', 'running', 'completed', 'failed'];
  const jobNames = [
    'ML Training Pipeline', 'Data Processing Batch', 'Video Transcoding',
    'Genomics Analysis', 'Financial Modeling', 'Climate Simulation',
    'Protein Folding', 'Neural Architecture Search'
  ];

  const jobs = Array.from({ length: 10 }, (_, i) => {
    const status = statuses[Math.floor(Math.random() * statuses.length)];
    return {
      id: `job-${i}`,
      name: jobNames[i % jobNames.length] + ` #${i + 1}`,
      sla: slas[Math.floor(Math.random() * slas.length)] as 'platinum' | 'gold' | 'silver' | 'bronze',
      status: status as any,
      progress: status === 'running' ? Math.floor(Math.random() * 80) + 10 : 0,
      eta: `${Math.floor(Math.random() * 120) + 10}min`
    };
  });

  return NextResponse.json({ jobs });
}