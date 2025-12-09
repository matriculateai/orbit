import React, { useMemo } from 'react';
import { Table, Button, Space, Tooltip } from 'antd';
import { DownloadOutlined } from '@ant-design/icons';
import type { ColumnsType, TablePaginationConfig } from 'antd/es/table';

export interface DataTableProps<T> {
  columns: ColumnsType<T>;
  data: T[];
  loading?: boolean;
  pagination?: TablePaginationConfig | false;
  rowKey?: string | ((record: T) => string);
  scroll?: { x?: number | string; y?: number | string };
  showExport?: boolean;
  exportFilename?: string;
  size?: 'small' | 'middle' | 'large';
  rowClassName?: (record: T, index: number) => string;
  onRow?: (record: T, index?: number) => React.HTMLAttributes<HTMLTableRowElement>;
  title?: () => React.ReactNode;
}

function DataTable<T extends object>({
  columns,
  data,
  loading = false,
  pagination = { pageSize: 10, showSizeChanger: true, showTotal: (total) => `Total ${total} items` },
  rowKey = 'id',
  scroll,
  showExport = false,
  exportFilename = 'data',
  size = 'middle',
  rowClassName,
  onRow,
  title,
}: DataTableProps<T>): React.ReactElement {
  // Convert data to CSV
  const exportToCSV = () => {
    if (!data.length) return;

    const headers = columns
      .filter((col) => 'dataIndex' in col && col.dataIndex)
      .map((col) => {
        const title = typeof col.title === 'string' ? col.title : String(col.title);
        return title;
      });

    const dataIndexes = columns
      .filter((col) => 'dataIndex' in col && col.dataIndex)
      .map((col) => ('dataIndex' in col ? col.dataIndex : '') as keyof T);

    const csvContent = [
      headers.join(','),
      ...data.map((row) =>
        dataIndexes
          .map((key) => {
            const value = row[key];
            const stringValue = value === null || value === undefined ? '' : String(value);
            // Escape quotes and wrap in quotes if contains comma
            return stringValue.includes(',') || stringValue.includes('"')
              ? `"${stringValue.replace(/"/g, '""')}"`
              : stringValue;
          })
          .join(',')
      ),
    ].join('\n');

    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const link = document.createElement('a');
    link.href = URL.createObjectURL(blob);
    link.download = `${exportFilename}_${new Date().toISOString().split('T')[0]}.csv`;
    link.click();
  };

  const tableTitle = useMemo(() => {
    if (!showExport && !title) return undefined;

    return () => (
      <Space style={{ display: 'flex', justifyContent: 'space-between', width: '100%' }}>
        <div>{title?.()}</div>
        {showExport && (
          <Tooltip title="Export to CSV">
            <Button
              icon={<DownloadOutlined />}
              onClick={exportToCSV}
              disabled={!data.length}
              size="small"
            >
              Export
            </Button>
          </Tooltip>
        )}
      </Space>
    );
  }, [showExport, title, data.length]);

  return (
    <Table<T>
      className="data-table"
      columns={columns}
      dataSource={data}
      loading={loading}
      pagination={pagination}
      rowKey={rowKey}
      scroll={scroll}
      size={size}
      rowClassName={rowClassName}
      onRow={onRow}
      title={tableTitle}
    />
  );
}

export default DataTable;
