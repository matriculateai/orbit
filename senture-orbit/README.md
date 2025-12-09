# Senture Orbit

**Pharmaceutical Commercial Intelligence Platform with Databricks Genie AI**

Senture Orbit helps pharmaceutical companies analyze sales, stock levels, rep performance, and territory data through conversational AI and interactive dashboards.

## Features

- **Executive Dashboard**: High-level KPIs, sales trends, and top opportunities
- **Manager Dashboard**: Territory-specific product and rep performance
- **Rep Dashboard**: Personalized priorities and customer opportunities
- **Genie Chat**: Natural language queries powered by Databricks Genie AI

## Tech Stack

- **Backend**: Python 3.11, FastAPI, Databricks SDK
- **Frontend**: React 18, TypeScript, Ant Design, Recharts
- **Database**: Databricks SQL Warehouse (Unity Catalog)
- **AI**: Databricks Genie Conversation API (Public Preview - Dec 2025)
- **Deployment**: Docker Compose

## Prerequisites

- Docker and Docker Compose
- Databricks workspace with:
  - SQL Warehouse
  - Unity Catalog with `pharma_gold` catalog
  - Genie Space configured with access to gold tables
- Personal Access Token (PAT) for Databricks

## Quick Start

### 1. Clone and Configure

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
```

### 3. Start the Application

```bash
docker-compose up --build
```

### 4. Access the Application

- **Frontend**: http://localhost:3000
- **Backend API**: http://localhost:8000
- **API Docs**: http://localhost:8000/docs

## Project Structure

```
senture-orbit/
├── backend/
│   ├── app/
│   │   ├── api/routes/       # API endpoints
│   │   ├── services/         # Business logic
│   │   ├── models/           # Pydantic models
│   │   └── middleware/       # CORS, etc.
│   ├── tests/                # pytest tests
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── components/       # Reusable UI components
│   │   ├── pages/            # Dashboard pages
│   │   └── services/         # API client
│   ├── Dockerfile
│   └── package.json
├── docker-compose.yml
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

## Development

### Backend Development

```bash
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

### Frontend Development

```bash
cd frontend
npm install
npm start
```

### Running Tests

```bash
# Backend tests
cd backend
pytest tests/ -v

# Frontend tests
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

### Common Issues

1. **"Databricks connection failed"**
   - Verify DATABRICKS_HOST and DATABRICKS_TOKEN
   - Ensure SQL Warehouse is running
   - Check firewall/network access

2. **"Genie space not found"**
   - Verify GENIE_SPACE_ID is correct
   - Ensure your PAT has access to the Genie space

3. **"Query timeout"**
   - Complex queries may exceed the 10-minute limit
   - Try simplifying the question
   - Check SQL Warehouse queue status

### Logs

```bash
# View backend logs
docker-compose logs backend

# View frontend logs
docker-compose logs frontend
```

## License

Proprietary - Senture Analytics

## Support

For issues and feature requests, contact the development team.
