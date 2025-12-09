import React, { useState } from 'react';
import { Row, Col, Select, Space, Typography, Alert } from 'antd';
import { useQuery } from '@tanstack/react-query';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from 'recharts';
import KPICard from '../components/KPICard';
import DashboardCard from '../components/DashboardCard';
import DataTable from '../components/DataTable';
import { api, ExecutiveDashboardResponse, OpportunityData } from '../services/api';

const { Title } = Typography;

const dateRangeOptions = [
  { value: 'last_7_days', label: 'Last 7 Days' },
  { value: 'last_30_days', label: 'Last 30 Days' },
  { value: 'last_90_days', label: 'Last 90 Days' },
  { value: 'ytd', label: 'Year to Date' },
];

const opportunityColumns = [
  {
    title: 'Customer',
    dataIndex: 'customer_name',
    key: 'customer_name',
    ellipsis: true,
  },
  {
    title: 'Product',
    dataIndex: 'product_name',
    key: 'product_name',
    ellipsis: true,
  },
  {
    title: 'Brand',
    dataIndex: 'brand',
    key: 'brand',
  },
  {
    title: 'SOH',
    dataIndex: 'soh',
    key: 'soh',
    render: (value: number) => value?.toLocaleString() ?? '-',
  },
  {
    title: 'DSOH',
    dataIndex: 'dsoh_days',
    key: 'dsoh_days',
    render: (value: number) => (
      <span className={value < 14 ? 'dsoh-critical' : value < 30 ? 'dsoh-warning' : ''}>
        {value?.toFixed(0) ?? '-'} days
      </span>
    ),
    sorter: (a: OpportunityData, b: OpportunityData) => a.dsoh_days - b.dsoh_days,
  },
  {
    title: 'Opportunity Value',
    dataIndex: 'opportunity_value',
    key: 'opportunity_value',
    render: (value: number) => (
      <span className="opportunity-value">${value?.toLocaleString() ?? '-'}</span>
    ),
    sorter: (a: OpportunityData, b: OpportunityData) =>
      a.opportunity_value - b.opportunity_value,
    defaultSortOrder: 'descend' as const,
  },
  {
    title: 'Region',
    dataIndex: 'region',
    key: 'region',
  },
];

const ExecutiveDashboard: React.FC = () => {
  const [dateRange, setDateRange] = useState('last_30_days');

  const { data, isLoading, error, refetch } = useQuery<ExecutiveDashboardResponse>({
    queryKey: ['executiveDashboard', dateRange],
    queryFn: () => api.getExecutiveDashboard(dateRange),
    refetchInterval: 5 * 60 * 1000, // Auto-refresh every 5 minutes
  });

  if (error) {
    return (
      <Alert
        message="Error loading dashboard"
        description="Failed to fetch dashboard data. Please check your connection and try again."
        type="error"
        showIcon
        action={
          <a onClick={() => refetch()}>Retry</a>
        }
      />
    );
  }

  const kpis = data?.kpis;
  const salesTrend = data?.sales_trend || [];
  const opportunities = data?.top_opportunities || [];

  return (
    <div>
      {/* Header */}
      <div className="dashboard-header">
        <Title level={3} className="dashboard-title">
          Executive Dashboard
        </Title>
        <Space>
          <span>Period:</span>
          <Select
            value={dateRange}
            onChange={setDateRange}
            options={dateRangeOptions}
            style={{ width: 150 }}
          />
        </Space>
      </div>

      {/* KPI Cards */}
      <Row gutter={[16, 16]} className="kpi-row">
        <Col xs={24} sm={12} lg={6}>
          <KPICard
            title="Total Sales"
            value={kpis?.total_sales || 0}
            prefix="$"
            loading={isLoading}
          />
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <KPICard
            title="Active Customers"
            value={kpis?.active_customers || 0}
            loading={isLoading}
          />
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <KPICard
            title="Opportunity Value"
            value={kpis?.opportunity_value || 0}
            prefix="$"
            loading={isLoading}
          />
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <KPICard
            title="Critical Gaps"
            value={kpis?.critical_gaps || 0}
            loading={isLoading}
            valueStyle={{
              color: (kpis?.critical_gaps || 0) > 0 ? '#f5222d' : '#52c41a',
              fontSize: '28px',
              fontWeight: 600,
            }}
          />
        </Col>
      </Row>

      {/* Sales Trend Chart */}
      <Row gutter={[16, 16]}>
        <Col xs={24}>
          <DashboardCard
            title="Sales Trend"
            subtitle="Daily sales performance"
            loading={isLoading}
          >
            <ResponsiveContainer width="100%" height={300}>
              <LineChart data={salesTrend}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis
                  dataKey="period"
                  tickFormatter={(value) => {
                    const date = new Date(value);
                    return `${date.getMonth() + 1}/${date.getDate()}`;
                  }}
                />
                <YAxis
                  tickFormatter={(value) =>
                    value >= 1000000
                      ? `$${(value / 1000000).toFixed(1)}M`
                      : value >= 1000
                      ? `$${(value / 1000).toFixed(0)}K`
                      : `$${value}`
                  }
                />
                <Tooltip
                  formatter={(value: number) => [`$${value.toLocaleString()}`, 'Sales']}
                  labelFormatter={(label) => new Date(label).toLocaleDateString()}
                />
                <Legend />
                <Line
                  type="monotone"
                  dataKey="total_sales"
                  name="Sales"
                  stroke="#1890ff"
                  strokeWidth={2}
                  dot={false}
                  activeDot={{ r: 6 }}
                />
              </LineChart>
            </ResponsiveContainer>
          </DashboardCard>
        </Col>
      </Row>

      {/* Top Opportunities Table */}
      <Row gutter={[16, 16]}>
        <Col xs={24}>
          <DashboardCard
            title="Top Stock Opportunities"
            subtitle="Highest value opportunities requiring attention"
            loading={isLoading}
          >
            <DataTable<OpportunityData>
              columns={opportunityColumns}
              data={opportunities}
              loading={isLoading}
              rowKey="customer_id"
              showExport
              exportFilename="top_opportunities"
              pagination={{ pageSize: 10 }}
              rowClassName={(record) =>
                record.dsoh_days < 14
                  ? 'opportunity-critical'
                  : record.dsoh_days < 30
                  ? 'opportunity-warning'
                  : ''
              }
            />
          </DashboardCard>
        </Col>
      </Row>
    </div>
  );
};

export default ExecutiveDashboard;
