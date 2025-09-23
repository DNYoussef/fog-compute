# Fog Compute Control Panel Setup Guide

## Quick Start

```bash
# 1. Navigate to the control panel directory
cd apps/control-panel

# 2. Install dependencies
npm install

# 3. Copy environment variables
cp .env.local.example .env.local

# 4. Run development server
npm run dev
```

Visit http://localhost:3000 to access the control panel.

## Prerequisites

- Node.js 18+
- npm or yarn
- Modern web browser with WebGL support (for 3D visualization)

## Installation Steps

### 1. Install Dependencies

```bash
npm install
```

This will install all required packages including:
- Next.js 14
- React 18
- Three.js (3D visualization)
- Recharts (performance charts)
- TailwindCSS (styling)

### 2. Environment Configuration

Copy the example environment file:

```bash
cp .env.local.example .env.local
```

Edit `.env.local` to configure your API endpoints:

```env
NEXT_PUBLIC_BETANET_API_URL=http://localhost:8080
NEXT_PUBLIC_BITCHAT_API_URL=http://localhost:8081
NEXT_PUBLIC_BENCHMARK_API_URL=http://localhost:8082
NEXT_PUBLIC_WS_URL=ws://localhost:3001
```

### 3. Development Server

Start the development server:

```bash
npm run dev
```

The control panel will be available at http://localhost:3000

### 4. Production Build

For production deployment:

```bash
# Build the application
npm run build

# Start production server
npm run start
```

## Connecting to Backend Services

### Betanet (Rust)

The Betanet backend should be running on the configured port (default: 8080).

```bash
# Start Betanet service (from project root)
cd src/betanet
cargo run --release
```

### BitChat (TypeScript)

BitChat runs as a P2P mesh network. The control panel provides a UI wrapper.

```bash
# BitChat is integrated directly in the control panel
# No separate service needed
```

### Benchmarks (Python)

Start the Python benchmark API:

```bash
# Start benchmark service (from project root)
cd src/fog/benchmarks
python -m uvicorn api:app --port 8082
```

## Features Overview

### Dashboard
- Real-time system metrics
- Network health monitoring
- Quick access to all services
- Global node distribution map

### Betanet Monitoring
- 3D network topology (interactive)
- Mixnode status and details
- Packet flow visualization
- Network performance metrics

### BitChat Messaging
- P2P peer discovery
- End-to-end encrypted messaging
- Mesh network status
- Connection management

### Performance Benchmarks
- Real-time performance charts
- Latency/throughput/stress tests
- Resource utilization monitoring
- Historical data analysis

## Troubleshooting

### 3D Visualization Not Working

If the 3D network topology doesn't render:
1. Check browser WebGL support: Visit https://get.webgl.org/
2. Update graphics drivers
3. Try a different browser (Chrome/Firefox recommended)

### API Connection Errors

If you see connection errors:
1. Verify backend services are running
2. Check API URLs in `.env.local`
3. Ensure CORS is configured on backend services
4. Check browser console for detailed errors

### Build Errors

If you encounter build errors:
1. Delete `node_modules` and `.next` folders
2. Run `npm install` again
3. Clear npm cache: `npm cache clean --force`
4. Try with Node.js 18 LTS

### Port Already in Use

If port 3000 is already in use:
```bash
# Run on a different port
PORT=3001 npm run dev
```

## Development Tips

### Hot Reload

Changes to files in `app/` and `components/` will auto-reload.

### Mock Data

The control panel uses mock data by default. To use real data:
1. Update API routes in `app/api/`
2. Configure backend service URLs
3. Implement WebSocket connections

### Adding New Pages

1. Create page in `app/your-page/page.tsx`
2. Add route to navigation in `components/Navigation.tsx`
3. Create components in `components/`
4. Add API routes if needed in `app/api/your-page/`

## Performance Optimization

### Production Checklist

- [ ] Enable gzip compression
- [ ] Configure CDN for static assets
- [ ] Set up Redis for caching
- [ ] Enable ISR for dynamic pages
- [ ] Optimize images with Next.js Image
- [ ] Configure bundle analyzer

### Monitoring

Add monitoring tools:
- Vercel Analytics (if deployed on Vercel)
- Google Analytics
- Sentry for error tracking
- Custom metrics dashboard

## Security

### Environment Variables

Never commit `.env.local` to version control.

### API Keys

Store sensitive keys in environment variables, not in code.

### CORS

Configure CORS properly on backend services:
```typescript
// Example CORS config
const allowedOrigins = [
  'http://localhost:3000',
  'https://your-domain.com'
];
```

## Deployment

### Vercel (Recommended)

```bash
# Install Vercel CLI
npm i -g vercel

# Deploy
vercel
```

### Docker

```bash
# Build Docker image
docker build -t fog-control-panel .

# Run container
docker run -p 3000:3000 fog-control-panel
```

### Manual Deployment

1. Build: `npm run build`
2. Copy `.next/`, `public/`, and `package.json`
3. Run: `npm start` on server

## Support

For issues or questions:
- Check the main README.md
- Review API documentation
- Check browser console for errors
- Verify all services are running

## Next Steps

1. Configure real backend connections
2. Implement WebSocket for real-time updates
3. Add authentication/authorization
4. Set up monitoring and analytics
5. Deploy to production

Happy monitoring!