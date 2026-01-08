# Senture Orbit

**Pharmaceutical Commercial Intelligence Platform with Databricks Genie AI**

Senture Orbit helps pharmaceutical companies analyze sales, stock levels, rep performance, and territory data through conversational AI and interactive dashboards.

## Features

- **Executive Dashboard**: High-level KPIs, sales trends, and top opportunities
- **Manager Dashboard**: Territory-specific product and rep performance
- **Rep Dashboard**: Personalized priorities and customer opportunities
- **Genie Chat**: Natural language queries powered by Databricks Genie AI
- **Claude AI Orchestration**: Intelligent question decomposition and parallel query execution

## Tech Stack

- **Backend**: Python 3.11, FastAPI, Databricks SDK
- **Frontend**: React 18, TypeScript, Ant Design, Recharts
- **Database**: Databricks SQL Warehouse (Unity Catalog)
- **AI**: Databricks Genie Conversation API + Claude AI (Anthropic)
- **Deployment**: Databricks Apps (recommended) or standalone

## Deployment Options

### Option 1: Databricks Apps (Recommended)

Deploy as a Databricks App for seamless integration with your workspace:

- **Workspace Authentication**: No need to manage PAT tokens
- **Single Origin**: Frontend and backend served together
- **Native Integration**: Direct access to Databricks resources

[See Databricks Apps Deployment Guide](#databricks-apps-deployment)

### Option 2: Local Development / Standalone

Run locally for development or deploy to your own infrastructure:

- **Explicit Credentials**: Uses PAT tokens for authentication
- **Separate Services**: Frontend and backend run independently

[See Local Development Guide](#local-development)

## Prerequisites

### For Databricks Apps Deployment
- Databricks workspace with Apps enabled
- SQL Warehouse
- Unity Catalog with `pharma_gold` catalog
- Genie Space configured with access to gold tables
- Anthropic API key (for Claude AI orchestration)

### For Local Development
- Python 3.11+
- Node.js 18+
- Databricks Personal Access Token (PAT)
- All prerequisites above

## Databricks Apps Deployment

### 1. Build the Application

```bash
cd senture-orbit

# Run the build script
./scripts/build.sh
```

This will:
- Build the React frontend
- Copy static files to the backend
- Verify backend dependencies

### 2. Create Databricks App

In your Databricks workspace:

1. Navigate to **Compute** > **Apps**
2. Click **Create App**
3. Upload the `senture-orbit` directory
4. The `app.yaml` will be automatically detected

### 3. Configure Environment Variables

In the Databricks Apps configuration, set these required variables:

| Variable | Description | Required |
|----------|-------------|----------|
| `GENIE_SPACE_ID` | Your Databricks Genie Space ID | Yes |
| `ANTHROPIC_API_KEY` | Anthropic API key for Claude AI | Yes |
| `DATABRICKS_WAREHOUSE_ID` | SQL Warehouse ID (if not using HTTP path) | Conditional |

Optional variables:
- `DATABRICKS_CATALOG` (default: `pharma_gold`)
- `DATABRICKS_SCHEMA` (default: `gold`)
- `CLAUDE_MODEL` (default: `claude-sonnet-4-20250514`)

### 4. Deploy

Click **Deploy** in the Databricks Apps UI. The app will:
- Build the Docker container
- Start the FastAPI server
- Serve the React frontend from the same origin
- Use workspace authentication automatically

### 5. Access Your App

Once deployed, access your app at:
```
https://<your-workspace>.cloud.databricks.com/apps/<app-name>
```

---

## Local Development

### 1. Configure Environment

```bash
cd senture-orbit

# Copy environment template
cp backend/.env.example backend/.env

# Edit with your Databricks credentials
nano backend/.env
```

### 2. Configure Environment Variables

Edit `backend/.env` with your values:

```env
DATABRICKS_HOST=https://your-workspace.cloud.databricks.com
DATABRICKS_TOKEN=dapi_your_token_here
DATABRICKS_HTTP_PATH=/sql/1.0/warehouses/your_warehouse_id
DATABRICKS_CATALOG=pharma_gold
DATABRICKS_SCHEMA=gold
GENIE_SPACE_ID=your-genie-space-id
ANTHROPIC_API_KEY=your-anthropic-api-key
```

### 3. Start the Backend

```bash
cd backend

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Start the server
uvicorn app.main:app --reload --port 8000
```

### 4. Start the Frontend

Open a new terminal:

```bash
cd frontend

# Install dependencies
npm install

# Start the development server
npm start
```

### 5. Access the Application

- **Frontend**: http://localhost:3000
- **Backend API**: http://localhost:8000
- **API Docs**: http://localhost:8000/docs

## Project Structure

```
senture-orbit/
├── app.yaml                  # Databricks Apps configuration
├── Dockerfile                # Container build configuration
├── scripts/
│   ├── build.sh              # Build script for deployment
│   └── start.sh              # Startup script
├── backend/
│   ├── app/
│   │   ├── api/routes/       # API endpoints
│   │   ├── services/         # Business logic (Databricks, Genie, AI)
│   │   ├── models/           # Pydantic models
│   │   └── middleware/       # CORS, etc.
│   ├── static/               # Built frontend (created during build)
│   ├── tests/                # pytest tests
│   ├── requirements.txt
│   └── .env.example          # Environment template
├── frontend/
│   ├── src/
│   │   ├── components/       # Reusable UI components
│   │   ├── pages/            # Dashboard pages
│   │   └── services/         # API client
│   └── package.json
└── README.md
```

## API Endpoints

### Health
- `GET /health` - System health check
- `GET /health/databricks` - Databricks connectivity
- `GET /health/genie` - Genie API availability

### Dashboards
- `GET /api/v1/dashboards/executive/overview` - Executive KPIs and trends
- `GET /api/v1/dashboards/manager/territory/{id}` - Territory dashboard
- `GET /api/v1/dashboards/rep/opportunities` - Rep opportunities

### Genie Chat
- `POST /api/v1/genie/query` - Send question to Genie
- `GET /api/v1/genie/conversation/{id}/history` - Get conversation history
- `GET /api/v1/genie/suggestions` - Get suggested questions

### Opportunities
- `GET /api/v1/opportunities/` - List stock opportunities
- `GET /api/v1/opportunities/summary` - Opportunity statistics
- `GET /api/v1/opportunities/priority` - Prioritized opportunities

## Database Schema

The application expects the following tables in Databricks:

### Fact Tables
- `gold.fact_secondary_sales_daily` - Daily sales transactions
- `gold.fact_stock_latest` - Current stock levels
- `gold.fact_rep_activity_monthly` - Rep performance

### Dimension Tables
- `gold.dim_customer` - Customer master data
- `gold.dim_product` - Product master data
- `gold.dim_rep` - Rep master data

### Materialized View
- `gold.mv_kpi_dashboard` - Pre-aggregated KPIs

## Running Tests

### Backend Tests

```bash
cd backend
source venv/bin/activate
pytest tests/ -v
```

### Frontend Tests

```bash
cd frontend
npm test
```

## Genie API Integration

This application uses the **Databricks Genie Conversation API (Public Preview - Dec 2025)**.

Key implementation details:
- Exponential backoff polling (5s to 60s intervals)
- Maximum 10-minute timeout per query
- New conversation per session (best practice)
- Supports SQL, data, and visualization responses

## Troubleshooting

### Databricks Apps Issues

1. **"App deployment failed"**
   - Check the Dockerfile builds successfully locally
   - Verify all required environment variables are set
   - Check the app logs in Databricks Apps UI

2. **"Authentication failed in Apps"**
   - Ensure the SQL Warehouse allows workspace auth
   - Verify the app has permissions to access the Genie space
   - Check that DATABRICKS_WAREHOUSE_ID or DATABRICKS_HTTP_PATH is set

3. **"Static files not found"**
   - Ensure you ran `./scripts/build.sh` before deploying
   - Verify the frontend built successfully
   - Check that `backend/static/` contains the built files

4. **"API calls failing with 401"**
   - In Databricks Apps, workspace auth should be automatic
   - Check the app's service principal has correct permissions
   - Verify the Genie space allows the app's identity

### Local Development Issues

1. **"Databricks connection failed"**
   - Verify DATABRICKS_HOST and DATABRICKS_TOKEN
   - Ensure SQL Warehouse is running
   - Check firewall/network access

2. **"Genie space not found"**
   - Verify GENIE_SPACE_ID is correct
   - Ensure your PAT has access to the Genie space

3. **"Query timeout"**
   - Complex queries may exceed the 90-second limit
   - Try simplifying the question
   - Check SQL Warehouse queue status

4. **"CORS errors"**
   - Ensure backend is running on port 8000
   - Check CORS_ORIGINS in backend/.env includes http://localhost:3000

### Viewing Logs

**Local development:**
```bash
uvicorn app.main:app --reload --log-level debug
```

**Databricks Apps:**
- Navigate to your app in Databricks
- Click on the **Logs** tab
- Filter by severity as needed

## License

Proprietary - Senture Analytics

## Support

For issues and feature requests, contact the development team.
