import { NextResponse } from 'next/server';

export async function GET() {
  return NextResponse.json({
    balance: Math.floor(Math.random() * 50000) + 10000
  });
}