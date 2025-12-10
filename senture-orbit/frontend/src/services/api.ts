import axios, { AxiosInstance, AxiosResponse } from 'axios';

// Types
export interface KPIData {
  total_sales: number;
  active_customers: number;
  opportunity_value: number;
  critical_gaps: number;
  period: string;
  highlights?: string[];
}

export interface OpportunityData {
  product_code: string;
  product_name: string;
  brand?: string;
  customer_name: string;
  customer_group?: string;
  region?: string;
  soh: number;
  avg_daily_units?: number;
  dsoh_days: number;
  ideal_stock_45d_units?: number;
  opportunity_units?: number;
  opportunity_value: number;
}

export interface RepPerformanceData {
  rep_id: string;
  rep_name: string;
  coverage_percent: number;
  strike_rate: number;
  total_calls: number;
  territory?: string;
  region?: string;
}

export interface ProductPerformance {
  product_id: string;
  product_name: string;
  brand: string;
  total_sales: number;
  units_sold: number;
  customer_count: number;
}

export interface SalesTrendData {
  period: string;
  total_sales: number;
  customer_count: number;
}

export interface ExecutiveDashboardResponse {
  kpis: KPIData;
  top_opportunities: OpportunityData[];
  sales_trend: SalesTrendData[];
  success: boolean;
  error?: string;
}

export interface ManagerDashboardResponse {
  territory_id: string;
  product_performance: ProductPerformance[];
  rep_performance: RepPerformanceData[];
  opportunities: OpportunityData[];
  success: boolean;
  error?: string;
}

export interface RepDashboardResponse {
  rep_id: string;
  my_performance?: RepPerformanceData;
  priority_opportunities: OpportunityData[];
  all_opportunities: OpportunityData[];
  success: boolean;
  error?: string;
}

export interface GenieResponse {
  conversation_id: string;
  message_id: string;
  response: string;
  sql_query?: string;
  data?: Record<string, unknown>[];
  columns?: string[];
  visualization?: Record<string, unknown>;
  thinking_steps?: string[];
  status: string;
  success: boolean;
  error?: string;
  truncated: boolean;
}

export interface ConversationMessage {
  message_id: string;
  role: 'user' | 'assistant';
  content: string;
  sql_query?: string;
  data?: Record<string, unknown>[];
  timestamp?: string;
}

export interface ConversationHistoryResponse {
  conversation_id: string;
  messages: ConversationMessage[];
  success: boolean;
}

export interface HealthResponse {
  status: string;
  databricks_connected: boolean;
  genie_available: boolean;
  version: string;
  details?: Record<string, unknown>;
}

export interface Territory {
  territory: string;
  region: string;
}

// API Client Class
class ApiClient {
  private client: AxiosInstance;

  constructor() {
    const baseURL = process.env.REACT_APP_API_URL || 'http://localhost:8000';

    this.client = axios.create({
      baseURL,
      headers: {
        'Content-Type': 'application/json',
      },
      timeout: 60000, // 60 second timeout for Genie queries
    });

    // Response interceptor for error handling
    this.client.interceptors.response.use(
      (response) => response,
      (error) => {
        console.error('API Error:', error.response?.data || error.message);
        return Promise.reject(error);
      }
    );
  }

  // Health endpoints
  async getHealth(): Promise<HealthResponse> {
    const response: AxiosResponse<HealthResponse> = await this.client.get('/health');
    return response.data;
  }

  // Executive Dashboard
  async getExecutiveDashboard(
    dateRange: string = 'last_30_days'
  ): Promise<ExecutiveDashboardResponse> {
    const response: AxiosResponse<ExecutiveDashboardResponse> = await this.client.get(
      '/api/v1/dashboards/executive/overview',
      { params: { date_range: dateRange } }
    );
    return response.data;
  }

  async getExecutiveKPIs(dateRange: string = 'last_30_days'): Promise<KPIData> {
    const response = await this.client.get('/api/v1/dashboards/executive/kpis', {
      params: { date_range: dateRange },
    });
    return response.data.data;
  }

  async getSalesTrend(
    dateRange: string = 'last_90_days',
    granularity: string = 'daily'
  ): Promise<SalesTrendData[]> {
    const response = await this.client.get('/api/v1/dashboards/executive/sales-trend', {
      params: { date_range: dateRange, granularity },
    });
    return response.data.data;
  }

  // Manager Dashboard
  async getManagerDashboard(
    territoryId: string,
    dateRange: string = 'last_30_days'
  ): Promise<ManagerDashboardResponse> {
    const response: AxiosResponse<ManagerDashboardResponse> = await this.client.get(
      `/api/v1/dashboards/manager/territory/${territoryId}`,
      { params: { date_range: dateRange } }
    );
    return response.data;
  }

  async getTerritories(): Promise<Territory[]> {
    const response = await this.client.get('/api/v1/dashboards/manager/territories');
    return response.data.territories;
  }

  async getRepPerformance(territoryId?: string): Promise<RepPerformanceData[]> {
    const response = await this.client.get('/api/v1/dashboards/manager/rep-performance', {
      params: territoryId ? { territory_id: territoryId } : {},
    });
    return response.data.data;
  }

  // Rep Dashboard
  async getRepDashboard(repId: string, limit: number = 20): Promise<RepDashboardResponse> {
    const response: AxiosResponse<RepDashboardResponse> = await this.client.get(
      '/api/v1/dashboards/rep/opportunities',
      { params: { rep_id: repId, limit } }
    );
    return response.data;
  }

  async getMyPerformance(repId: string): Promise<RepPerformanceData | null> {
    const response = await this.client.get('/api/v1/dashboards/rep/my-performance', {
      params: { rep_id: repId },
    });
    return response.data.data;
  }

  // Opportunities
  async getOpportunities(params: {
    limit?: number;
    region?: string;
    min_value?: number;
    max_dsoh?: number;
  } = {}): Promise<{ opportunities: OpportunityData[]; total_value: number; critical_count: number }> {
    const response = await this.client.get('/api/v1/opportunities/', { params });
    return response.data;
  }

  async getOpportunitiesSummary(): Promise<Record<string, unknown>> {
    const response = await this.client.get('/api/v1/opportunities/summary');
    return response.data.summary;
  }

  async getOpportunitiesByRegion(): Promise<Record<string, unknown>[]> {
    const response = await this.client.get('/api/v1/opportunities/by-region');
    return response.data.regions;
  }

  async getPriorityOpportunities(
    persona: string = 'executive',
    limit: number = 10,
    region?: string
  ): Promise<{ opportunities: OpportunityData[]; insights: string[] }> {
    const response = await this.client.get('/api/v1/opportunities/priority', {
      params: { persona, limit, region },
    });
    return response.data;
  }

  // Genie Chat
  async sendGenieMessage(
    question: string,
    conversationId?: string
  ): Promise<GenieResponse> {
    const response: AxiosResponse<GenieResponse> = await this.client.post(
      '/api/v1/genie/query',
      {
        question,
        conversation_id: conversationId,
      }
    );
    return response.data;
  }

  async getConversationHistory(conversationId: string): Promise<ConversationHistoryResponse> {
    const response: AxiosResponse<ConversationHistoryResponse> = await this.client.get(
      `/api/v1/genie/conversation/${conversationId}/history`
    );
    return response.data;
  }

  async regenerateResponse(
    conversationId: string,
    messageId: string
  ): Promise<GenieResponse> {
    const response: AxiosResponse<GenieResponse> = await this.client.post(
      `/api/v1/genie/conversation/${conversationId}/regenerate/${messageId}`
    );
    return response.data;
  }

  async deleteConversation(conversationId: string): Promise<boolean> {
    const response = await this.client.delete(
      `/api/v1/genie/conversation/${conversationId}`
    );
    return response.data.success;
  }

  async getSuggestions(persona: string = 'executive'): Promise<string[]> {
    const response = await this.client.get('/api/v1/genie/suggestions', {
      params: { persona },
    });
    return response.data.suggestions;
  }

  async getMessageStatus(
    conversationId: string,
    messageId: string
  ): Promise<{ status: string; completed: boolean }> {
    const response = await this.client.get(
      `/api/v1/genie/conversation/${conversationId}/message/${messageId}/status`
    );
    return response.data;
  }
}

// Export singleton instance
export const api = new ApiClient();
export default api;
