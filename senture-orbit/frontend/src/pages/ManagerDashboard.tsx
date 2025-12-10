import React, { useState } from 'react';
import { Row, Col, Select, Space, Typography, Alert, Empty } from 'antd';
import { useQuery } from '@tanstack/react-query';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from 'recharts';
import DashboardCard from '../components/DashboardCard';
import DataTable from '../components/DataTable';
import {
  api,
  ManagerDashboardResponse,
  Territory,
  RepPerformanceData,
  ProductPerformance,
  OpportunityData,
} from '../services/api';

const { Title } = Typography;

const repPerformanceColumns = [
  {
    title: 'Rep Name',
    dataIndex: 'rep_name',
    key: 'rep_name',
  },
  {
    title: 'Coverage %',
    dataIndex: 'coverage_percent',
    key: 'coverage_percent',
    render: (value: number) => `${value?.toFixed(1) ?? '-'}%`,
    sorter: (a: RepPerformanceData, b: RepPerformanceData) =>
      a.coverage_percent - b.coverage_percent,
  },
  {
    title: 'Strike Rate',
    dataIndex: 'strike_rate',
    key: 'strike_rate',
    render: (value: number) => `${value?.toFixed(1) ?? '-'}%`,
    sorter: (a: RepPerformanceData, b: RepPerformanceData) =>
      a.strike_rate - b.strike_rate,
    defaultSortOrder: 'descend' as const,
  },
  {
    title: 'Total Calls',
    dataIndex: 'total_calls',
    key: 'total_calls',
    render: (value: number) => value?.toLocaleString() ?? '-',
  },
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
    title: 'DSOH',
    dataIndex: 'dsoh_days',
    key: 'dsoh_days',
    render: (value: number) => (
      <span className={value < 14 ? 'dsoh-critical' : value < 30 ? 'dsoh-warning' : ''}>
        {value?.toFixed(0) ?? '-'} days
      </span>
    ),
  },
  {
    title: 'Opportunity Value',
    dataIndex: 'opportunity_value',
    key: 'opportunity_value',
    render: (value: number) => (
      <span className="opportunity-value">${value?.toLocaleString() ?? '-'}</span>
    ),
    defaultSortOrder: 'descend' as const,
  },
];

const ManagerDashboard: React.FC = () => {
  const [selectedTerritory, setSelectedTerritory] = useState<string>('');
  const [dateRange, setDateRange] = useState('last_30_days');

  // Fetch territories
  const { data: territories, isLoading: loadingTerritories } = useQuery<Territory[]>({
    queryKey: ['territories'],
    queryFn: () => api.getTerritories(),
  });

  // Fetch dashboard data
  const {
    data: dashboardData,
    isLoading: loadingDashboard,
    error,
    refetch,
  } = useQuery<ManagerDashboardResponse>({
    queryKey: ['managerDashboard', selectedTerritory, dateRange],
    queryFn: () => api.getManagerDashboard(selectedTerritory, dateRange),
    enabled: !!selectedTerritory,
  });

  // Set default territory
  React.useEffect(() => {
    if (territories?.length && !selectedTerritory) {
      setSelectedTerritory(territories[0].territory);
    }
  }, [territories, selectedTerritory]);

  if (error) {
    return (
      <Alert
        message="Error loading dashboard"
        description="Failed to fetch dashboard data. Please try again."
        type="error"
        showIcon
        action={<a onClick={() => refetch()}>Retry</a>}
      />
    );
  }

  const isLoading = loadingTerritories || loadingDashboard;
  const productPerformance = dashboardData?.product_performance || [];
  const repPerformance = dashboardData?.rep_performance || [];
  const opportunities = dashboardData?.opportunities || [];

  const territoryOptions = territories?.map((t) => ({
    value: t.territory,
    label: `${t.territory} (${t.region})`,
  })) || [];

  return (
    <div>
      {/* Header */}
      <div className="dashboard-header">
        <Title level={3} className="dashboard-title">
          Manager Dashboard
        </Title>
        <Space>
          <span>Territory:</span>
          <Select
            value={selectedTerritory}
            onChange={setSelectedTerritory}
            options={territoryOptions}
            loading={loadingTerritories}
            style={{ width: 200 }}
            placeholder="Select territory"
          />
        </Space>
      </div>

      {!selectedTerritory ? (
        <Empty description="Select a territory to view dashboard" />
      ) : (
        <>
          {/* Product Performance and Rep Performance */}
          <Row gutter={[16, 16]}>
            <Col xs={24} lg={12}>
              <DashboardCard
                title="Product Performance"
                subtitle="Top products by sales"
                loading={isLoading}
              >
                {productPerformance.length > 0 ? (
                  <ResponsiveContainer width="100%" height={300}>
                    <BarChart data={productPerformance.slice(0, 8)} layout="vertical">
                      <CartesianGrid strokeDasharray="3 3" />
                      <XAxis
                        type="number"
                        tickFormatter={(value) =>
                          value >= 1000000
                            ? `$${(value / 1000000).toFixed(1)}M`
                            : value >= 1000
                            ? `$${(value / 1000).toFixed(0)}K`
                            : `$${value}`
                        }
                      />
                      <YAxis
                        dataKey="product_name"
                        type="category"
                        width={120}
                        tick={{ fontSize: 12 }}
                      />
                      <Tooltip
                        formatter={(value: number) => [`$${value.toLocaleString()}`, 'Sales']}
                      />
                      <Legend />
                      <Bar dataKey="total_sales" name="Sales" fill="#1890ff" />
                    </BarChart>
                  </ResponsiveContainer>
                ) : (
                  <Empty description="No product data available" />
                )}
              </DashboardCard>
            </Col>
            <Col xs={24} lg={12}>
              <DashboardCard
                title="Rep Performance"
                subtitle="Team performance ranking"
                loading={isLoading}
              >
                <DataTable<RepPerformanceData>
                  columns={repPerformanceColumns}
                  data={repPerformance}
                  loading={isLoading}
                  rowKey="rep_id"
                  pagination={false}
                  size="small"
                />
              </DashboardCard>
            </Col>
          </Row>

          {/* Stock Opportunities */}
          <Row gutter={[16, 16]} style={{ marginTop: 16 }}>
            <Col xs={24}>
              <DashboardCard
                title="Stock Opportunities"
                subtitle="Opportunities in your territory"
                loading={isLoading}
              >
                <DataTable<OpportunityData>
                  columns={opportunityColumns}
                  data={opportunities}
                  loading={isLoading}
                  rowKey={(record) => `${record.product_code}-${record.customer_name}`}
                  showExport
                  exportFilename={`territory_opportunities_${selectedTerritory}`}
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
        </>
      )}
    </div>
  );
};

export default ManagerDashboard;
