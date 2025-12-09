import React, { useState } from 'react';
import { Row, Col, Input, Space, Typography, Alert, Card, Statistic, Tag, List } from 'antd';
import { useQuery } from '@tanstack/react-query';
import {
  CheckCircleOutlined,
  WarningOutlined,
  DollarOutlined,
  PhoneOutlined,
} from '@ant-design/icons';
import DashboardCard from '../components/DashboardCard';
import DataTable from '../components/DataTable';
import { api, RepDashboardResponse, OpportunityData } from '../services/api';

const { Title, Text } = Typography;
const { Search } = Input;

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
    title: 'Current Stock',
    dataIndex: 'soh',
    key: 'soh',
    render: (value: number) => value?.toLocaleString() ?? '-',
  },
  {
    title: 'Days Stock',
    dataIndex: 'dsoh_days',
    key: 'dsoh_days',
    render: (value: number) => {
      const className = value < 14 ? 'dsoh-critical' : value < 30 ? 'dsoh-warning' : '';
      return <span className={className}>{value?.toFixed(0) ?? '-'} days</span>;
    },
    sorter: (a: OpportunityData, b: OpportunityData) => a.dsoh_days - b.dsoh_days,
  },
  {
    title: 'Opportunity',
    dataIndex: 'opportunity_value',
    key: 'opportunity_value',
    render: (value: number) => (
      <span className="opportunity-value">${value?.toLocaleString() ?? '-'}</span>
    ),
    sorter: (a: OpportunityData, b: OpportunityData) =>
      a.opportunity_value - b.opportunity_value,
    defaultSortOrder: 'descend' as const,
  },
];

const RepDashboard: React.FC = () => {
  const [repId, setRepId] = useState<string>('');
  const [searchInput, setSearchInput] = useState('');

  const {
    data: dashboardData,
    isLoading,
    error,
    refetch,
  } = useQuery<RepDashboardResponse>({
    queryKey: ['repDashboard', repId],
    queryFn: () => api.getRepDashboard(repId),
    enabled: !!repId,
  });

  const handleSearch = (value: string) => {
    setRepId(value.trim());
  };

  if (error) {
    return (
      <Alert
        message="Error loading dashboard"
        description="Failed to fetch dashboard data. Please check your Rep ID and try again."
        type="error"
        showIcon
        action={<a onClick={() => refetch()}>Retry</a>}
      />
    );
  }

  const myPerformance = dashboardData?.my_performance;
  const priorityOpportunities = dashboardData?.priority_opportunities || [];
  const allOpportunities = dashboardData?.all_opportunities || [];

  const totalOpportunityValue = allOpportunities.reduce(
    (sum, opp) => sum + (opp.opportunity_value || 0),
    0
  );

  return (
    <div>
      {/* Header */}
      <div className="dashboard-header">
        <Title level={3} className="dashboard-title">
          Rep Dashboard
        </Title>
        <Space>
          <Search
            placeholder="Enter Rep ID"
            value={searchInput}
            onChange={(e) => setSearchInput(e.target.value)}
            onSearch={handleSearch}
            enterButton="Load"
            style={{ width: 250 }}
          />
        </Space>
      </div>

      {!repId ? (
        <Card>
          <div style={{ textAlign: 'center', padding: '40px 20px' }}>
            <PhoneOutlined style={{ fontSize: 48, color: '#1890ff', marginBottom: 16 }} />
            <Title level={4}>Enter your Rep ID to view your dashboard</Title>
            <Text type="secondary">
              Your personalized view of opportunities and performance metrics
            </Text>
          </div>
        </Card>
      ) : (
        <>
          {/* Priority Visits */}
          <Row gutter={[16, 16]}>
            <Col xs={24} lg={16}>
              <DashboardCard
                title="Today's Priorities"
                subtitle="Top 5 opportunities to focus on"
                loading={isLoading}
              >
                {priorityOpportunities.length > 0 ? (
                  <List
                    dataSource={priorityOpportunities}
                    renderItem={(item, index) => (
                      <List.Item>
                        <List.Item.Meta
                          avatar={
                            <div
                              style={{
                                width: 32,
                                height: 32,
                                borderRadius: '50%',
                                backgroundColor: index === 0 ? '#f5222d' : '#faad14',
                                color: 'white',
                                display: 'flex',
                                alignItems: 'center',
                                justifyContent: 'center',
                                fontWeight: 'bold',
                              }}
                            >
                              {index + 1}
                            </div>
                          }
                          title={
                            <Space>
                              <span>{item.customer_name}</span>
                              {item.dsoh_days < 14 && (
                                <Tag color="red" icon={<WarningOutlined />}>
                                  Critical
                                </Tag>
                              )}
                            </Space>
                          }
                          description={
                            <Space direction="vertical" size={0}>
                              <Text type="secondary">{item.product_name}</Text>
                              <Text>
                                <DollarOutlined /> Opportunity: $
                                {item.opportunity_value?.toLocaleString()}
                              </Text>
                              <Text type="secondary">
                                Stock: {item.soh?.toLocaleString()} units ({item.dsoh_days?.toFixed(0)} days)
                              </Text>
                            </Space>
                          }
                        />
                      </List.Item>
                    )}
                  />
                ) : (
                  <div style={{ textAlign: 'center', padding: 20 }}>
                    <CheckCircleOutlined style={{ fontSize: 32, color: '#52c41a' }} />
                    <Text style={{ display: 'block', marginTop: 8 }}>
                      No urgent priorities at the moment
                    </Text>
                  </div>
                )}
              </DashboardCard>
            </Col>

            {/* My Performance */}
            <Col xs={24} lg={8}>
              <DashboardCard
                title="My Performance"
                subtitle="Current month metrics"
                loading={isLoading}
              >
                {myPerformance ? (
                  <Row gutter={[16, 16]}>
                    <Col span={12}>
                      <Statistic
                        title="Coverage"
                        value={myPerformance.coverage_percent}
                        suffix="%"
                        precision={1}
                        valueStyle={{
                          color:
                            myPerformance.coverage_percent >= 80
                              ? '#52c41a'
                              : myPerformance.coverage_percent >= 60
                              ? '#faad14'
                              : '#f5222d',
                        }}
                      />
                    </Col>
                    <Col span={12}>
                      <Statistic
                        title="Strike Rate"
                        value={myPerformance.strike_rate}
                        suffix="%"
                        precision={1}
                        valueStyle={{
                          color:
                            myPerformance.strike_rate >= 70
                              ? '#52c41a'
                              : myPerformance.strike_rate >= 50
                              ? '#faad14'
                              : '#f5222d',
                        }}
                      />
                    </Col>
                    <Col span={12}>
                      <Statistic
                        title="Total Calls"
                        value={myPerformance.total_calls}
                      />
                    </Col>
                    <Col span={12}>
                      <Statistic
                        title="Territory"
                        value={myPerformance.territory || '-'}
                        valueStyle={{ fontSize: 16 }}
                      />
                    </Col>
                  </Row>
                ) : (
                  <Text type="secondary">No performance data available</Text>
                )}

                {/* Summary Stats */}
                <div style={{ marginTop: 24, paddingTop: 16, borderTop: '1px solid #f0f0f0' }}>
                  <Row gutter={[8, 8]}>
                    <Col span={12}>
                      <Text type="secondary">Total Opportunities</Text>
                      <div style={{ fontSize: 18, fontWeight: 600 }}>
                        {allOpportunities.length}
                      </div>
                    </Col>
                    <Col span={12}>
                      <Text type="secondary">Total Value</Text>
                      <div style={{ fontSize: 18, fontWeight: 600, color: '#52c41a' }}>
                        ${totalOpportunityValue.toLocaleString()}
                      </div>
                    </Col>
                  </Row>
                </div>
              </DashboardCard>
            </Col>
          </Row>

          {/* All Opportunities */}
          <Row gutter={[16, 16]} style={{ marginTop: 16 }}>
            <Col xs={24}>
              <DashboardCard
                title="All My Opportunities"
                subtitle="Stock opportunities at your customers"
                loading={isLoading}
              >
                <DataTable<OpportunityData>
                  columns={opportunityColumns}
                  data={allOpportunities}
                  loading={isLoading}
                  rowKey={(record) => `${record.customer_id}-${record.product_id}`}
                  showExport
                  exportFilename={`my_opportunities_${repId}`}
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

export default RepDashboard;
