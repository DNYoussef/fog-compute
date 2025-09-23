# Fog Compute Control Panel

A unified Next.js control panel for monitoring and managing the Fog Compute platform, including Betanet privacy network, BitChat P2P messaging, and performance benchmarks.

## Features

- **Dashboard**: Real-time overview of all systems
- **Betanet Monitor**: 3D network topology visualization, mixnode status, packet flow monitoring
- **BitChat Interface**: Integrated P2P messaging with end-to-end encryption
- **Performance Benchmarks**: Real-time charts, stress testing, system metrics
- **Modern UI**: Glass-morphism design with TailwindCSS
- **Mobile Responsive**: Works on all device sizes
- **Real-time Updates**: WebSocket connections for live data

## Tech Stack

- **Next.js 14** - App Router with TypeScript
- **React 18** - UI components
- **TailwindCSS** - Styling with glass-morphism effects
- **Three.js** - 3D network visualization
- **Recharts** - Performance charts
- **WebSocket** - Real-time updates

## Installation

```bash
# Navigate to the control panel directory
cd apps/control-panel

# Install dependencies
npm install

# Run development server
npm run dev
```

Open [http://localhost:3000](http://localhost:3000) to view the control panel.

## Project Structure

```
apps/control-panel/
├── app/
│   ├── api/              # API routes
│   │   ├── dashboard/    # Dashboard stats
│   │   ├── betanet/      # Betanet status
│   │   └── benchmarks/   # Benchmark APIs
│   ├── betanet/          # Betanet monitoring page
│   ├── bitchat/          # BitChat messaging page
│   ├── benchmarks/       # Performance benchmarks page
│   ├── layout.tsx        # Root layout
│   ├── page.tsx          # Dashboard home
│   └── globals.css       # Global styles
├── components/
│   ├── Navigation.tsx         # Top navigation
│   ├── BetanetTopology.tsx    # 3D network visualization
│   ├── BenchmarkCharts.tsx    # Performance charts
│   ├── FogMap.tsx             # Geographic node distribution
│   ├── SystemMetrics.tsx      # System health metrics
│   ├── QuickActions.tsx       # Quick action buttons
│   ├── PacketFlowMonitor.tsx  # Packet flow visualization
│   ├── MixnodeList.tsx        # Mixnode details list
│   ├── BenchmarkControls.tsx  # Benchmark test controls
│   └── BitChatWrapper.tsx     # BitChat integration
├── lib/                   # Utility functions
├── public/               # Static assets
└── package.json          # Dependencies
```

## Pages

### Dashboard (`/`)
- Real-time system overview
- Health metrics for all services
- Quick access cards
- Global fog node map
- System resource monitoring

### Betanet (`/betanet`)
- 3D network topology visualization
- Mixnode status and details
- Packet flow monitoring
- Network health metrics
- Interactive node selection

### BitChat (`/bitchat`)
- P2P messaging interface
- Peer discovery
- End-to-end encryption status
- Mesh network health
- Message history

### Benchmarks (`/benchmarks`)
- Real-time performance charts
- Latency/Throughput/Stress tests
- CPU and memory monitoring
- Network utilization
- Test controls and configuration

## API Routes

- `GET /api/dashboard/stats` - Dashboard statistics
- `GET /api/betanet/status` - Betanet network status
- `GET /api/benchmarks/data` - Real-time benchmark data
- `POST /api/benchmarks/start` - Start benchmark test
- `POST /api/benchmarks/stop` - Stop benchmark test

## Integration

The control panel integrates with:

1. **Betanet System** (Rust)
   - Monitors mixnode topology
   - Tracks packet flow
   - Network health metrics

2. **BitChat** (TypeScript)
   - P2P mesh messaging
   - Peer discovery
   - Encryption status

3. **Benchmark API** (Python)
   - Performance testing
   - Resource monitoring
   - Stress testing

## Configuration

Update API endpoints in:
- `app/api/*/route.ts` files for backend connections
- Add WebSocket configuration for real-time updates
- Configure environment variables in `.env.local`

## Development

```bash
# Run development server
npm run dev

# Build for production
npm run build

# Start production server
npm run start

# Run linting
npm run lint
```

## Customization

### Colors
Edit `tailwind.config.ts` to customize the color scheme:
- `fog-dark` - Background color
- `fog-blue` - Primary accent
- `fog-purple` - Secondary accent
- `fog-cyan` - Tertiary accent

### Layout
Modify `app/layout.tsx` for global layout changes.

### Components
All components are in `components/` directory and can be customized independently.

## Production Deployment

1. Build the application:
   ```bash
   npm run build
   ```

2. Deploy to your preferred platform:
   - Vercel (recommended for Next.js)
   - AWS
   - Docker container

3. Configure environment variables for production API endpoints

## WebSocket Integration

For real-time updates, implement WebSocket connections in:
- `app/api/ws/route.ts` - WebSocket server
- Update components to subscribe to WebSocket events

## License

Part of the Fog Compute platform.