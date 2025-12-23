# Senture Orbit Frontend

React-based frontend for the Senture Orbit Pharmaceutical Commercial Intelligence Platform.

## Tech Stack

- **React 18.2** - UI framework
- **TypeScript 4.9** - Type safety
- **Ant Design 5.12** - UI component library
- **Recharts 2.10** - Data visualization
- **React Query 5.13** - Server state management
- **React Three Fiber 8.18** - 3D visualizations
- **Axios 1.6** - HTTP client

## Prerequisites

⚠️ **IMPORTANT:** This project requires **Node.js 16 or 18**

- **Node.js:** 16.x or 18.x LTS (NOT Node 19+)
- **npm:** 8.x or higher

### Check Your Node Version

```bash
node --version  # Should show v16.x.x or v18.x.x
```

### Install Correct Node Version

If you have Node 19+ or another incompatible version:

**Using nvm (recommended):**
```bash
nvm install 18
nvm use 18
nvm alias default 18
```

**Using n:**
```bash
n 18
```

## Quick Start

### 1. Install Dependencies

```bash
npm install
```

### 2. Configure Environment

Create a `.env` file (optional - uses defaults):

```env
# Backend API URL (default: http://localhost:8000)
REACT_APP_API_URL=http://localhost:8000
```

### 3. Start Development Server

```bash
npm start
```

Opens http://localhost:3000 in your browser.

### 4. Build for Production

```bash
npm run build
```

Creates optimized production build in `build/` directory.

## Available Scripts

### Development

- `npm start` - Start development server (port 3000)
- `npm test` - Run test suite
- `npm run build` - Create production build
- `npm run eject` - Eject from Create React App (**irreversible!**)

## Project Structure

```
frontend/
├── public/              # Static assets
│   ├── index.html       # HTML template
│   └── favicon.ico      # App icon
├── src/
│   ├── components/      # Reusable UI components
│   ├── pages/           # Page components
│   │   ├── Dashboard/   # Executive dashboard
│   │   ├── Chat/        # AI chat interface
│   │   └── Opportunities/ # Stock opportunities
│   ├── services/        # API client services
│   │   └── api.ts       # Axios configuration
│   ├── types/           # TypeScript type definitions
│   ├── App.tsx          # Root component
│   └── index.tsx        # Entry point
├── package.json         # Dependencies
├── tsconfig.json        # TypeScript configuration
├── SECURITY_NOTES.md    # Security documentation
└── README.md            # This file
```

## Security

### Vulnerability Status

- **Production:** ✅ **0 vulnerabilities**
- **Development:** 9 moderate vulnerabilities (development tools only)

All vulnerabilities affect **development dependencies only** and do **not impact production builds**.

For detailed security information, see [SECURITY_NOTES.md](./SECURITY_NOTES.md).

### Why Some Vulnerabilities Can't Be Fixed

react-scripts 5.0.1 (part of Create React App) has transitive dependencies with known issues. Upgrading these dependencies breaks compatibility. Since:

1. All vulnerabilities are **moderate severity** (not high/critical)
2. All affect **development mode only** (not production)
3. Fixes would require **breaking changes** (migrating away from CRA)

We've chosen to document and accept these known issues. Production builds remain secure.

## Development Best Practices

### 1. Never Expose Dev Server Publicly

The development server (`npm start`) should only run on localhost:

```bash
# ✅ Good (default)
npm start  # Binds to localhost:3000

# ❌ Bad (security risk)
HOST=0.0.0.0 npm start  # Exposes to network
```

### 2. Use Correct Node Version

Always use Node 16 or 18:

```bash
# Check version before installing
node --version

# Use nvm to switch if needed
nvm use 18
```

### 3. Update Dependencies Safely

Only update patch/minor versions:

```bash
# Check for updates
npm outdated

# Update safely (respects ^1.2.3 semver)
npm update

# DO NOT force-fix vulnerabilities (breaks build)
# ❌ npm audit fix --force
```

## Troubleshooting

### Build Fails with "Cannot find module 'ajv/dist/compile/codegen'"

**Cause:** Using Node.js 19+ (incompatible with react-scripts 5.0.1)

**Solution:** Switch to Node 18:
```bash
nvm use 18
npm install
npm start
```

### "npm audit" Shows Vulnerabilities

**Expected:** 9 moderate vulnerabilities in development dependencies

**Verify production is safe:**
```bash
npm audit --production
# Should show: found 0 vulnerabilities
```

See [SECURITY_NOTES.md](./SECURITY_NOTES.md) for details.

### CORS Errors When Connecting to Backend

**Solution:** Ensure backend is running and CORS is configured:

```bash
# In backend/.env
CORS_ORIGINS=["http://localhost:3000"]
```

### Port 3000 Already in Use

**Solution:** Use a different port:
```bash
PORT=3001 npm start
```

## Testing

### Run Tests

```bash
npm test
```

### Run Tests with Coverage

```bash
npm test -- --coverage
```

## Production Deployment

### Build

```bash
npm run build
```

### Deploy to Static Hosting

The `build/` folder can be deployed to:

- **Vercel:** `vercel deploy`
- **Netlify:** Drag & drop `build/` folder
- **AWS S3:** `aws s3 sync build/ s3://your-bucket`
- **GitHub Pages:** `npm install gh-pages && npm run deploy`
- **Any static host:** Upload `build/` contents

### Environment Variables for Production

Create `.env.production`:

```env
REACT_APP_API_URL=https://api.yourdomain.com
```

## Future Migration

**Recommended:** Migrate to Vite for better performance and modern tooling.

See [SECURITY_NOTES.md](./SECURITY_NOTES.md) for migration guide.

## Support

For issues and questions:
- See main repository README
- Contact: development@senture.co.za

---

**Built with React + TypeScript**
