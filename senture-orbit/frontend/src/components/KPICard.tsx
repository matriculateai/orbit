import React from 'react';
import { Card, Statistic } from 'antd';
import { ArrowUpOutlined, ArrowDownOutlined } from '@ant-design/icons';

export interface KPICardProps {
  title: string;
  value: number | string;
  trend?: number;
  trendDirection?: 'up' | 'down';
  prefix?: string;
  suffix?: string;
  precision?: number;
  loading?: boolean;
  valueStyle?: React.CSSProperties;
}

const KPICard: React.FC<KPICardProps> = ({
  title,
  value,
  trend,
  trendDirection,
  prefix,
  suffix,
  precision = 0,
  loading = false,
  valueStyle,
}) => {
  const getTrendColor = () => {
    if (!trendDirection) return undefined;
    return trendDirection === 'up' ? '#52c41a' : '#f5222d';
  };

  const getTrendIcon = () => {
    if (!trendDirection) return null;
    return trendDirection === 'up' ? <ArrowUpOutlined /> : <ArrowDownOutlined />;
  };

  const formatValue = (val: number | string): string | number => {
    if (typeof val === 'string') return val;
    if (prefix === '$') {
      return val >= 1000000
        ? `${(val / 1000000).toFixed(1)}M`
        : val >= 1000
        ? `${(val / 1000).toFixed(1)}K`
        : val.toFixed(precision);
    }
    return val.toLocaleString(undefined, {
      minimumFractionDigits: precision,
      maximumFractionDigits: precision,
    });
  };

  return (
    <Card className="kpi-card" loading={loading}>
      <Statistic
        title={title}
        value={formatValue(value)}
        precision={precision}
        valueStyle={valueStyle || { color: '#262626', fontSize: '28px', fontWeight: 600 }}
        prefix={prefix}
        suffix={suffix}
      />
      {trend !== undefined && (
        <div
          className={`kpi-trend ${trendDirection === 'up' ? 'positive' : 'negative'}`}
          style={{ color: getTrendColor(), marginTop: '8px' }}
        >
          {getTrendIcon()} {Math.abs(trend).toFixed(1)}%
          <span style={{ color: '#8c8c8c', marginLeft: '8px' }}>vs last period</span>
        </div>
      )}
    </Card>
  );
};

export default KPICard;
