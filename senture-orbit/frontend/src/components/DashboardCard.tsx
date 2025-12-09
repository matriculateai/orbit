import React from 'react';
import { Card, Skeleton, Space } from 'antd';
import type { CardProps } from 'antd';

export interface DashboardCardProps extends CardProps {
  title: string;
  subtitle?: string;
  loading?: boolean;
  actions?: React.ReactNode[];
  headerExtra?: React.ReactNode;
  children: React.ReactNode;
  height?: number | string;
}

const DashboardCard: React.FC<DashboardCardProps> = ({
  title,
  subtitle,
  loading = false,
  actions,
  headerExtra,
  children,
  height,
  ...cardProps
}) => {
  const cardTitle = (
    <Space direction="vertical" size={0}>
      <span style={{ fontSize: '16px', fontWeight: 600 }}>{title}</span>
      {subtitle && (
        <span style={{ fontSize: '12px', color: '#8c8c8c', fontWeight: 400 }}>
          {subtitle}
        </span>
      )}
    </Space>
  );

  return (
    <Card
      className="chart-card"
      title={cardTitle}
      extra={headerExtra}
      actions={actions}
      style={{ height }}
      {...cardProps}
    >
      {loading ? (
        <Skeleton active paragraph={{ rows: 4 }} />
      ) : (
        children
      )}
    </Card>
  );
};

export default DashboardCard;
