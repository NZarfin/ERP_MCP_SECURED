export type SalesStatus = "draft" | "confirmed" | "delivered" | "cancelled";
export type PurchaseStatus = "draft" | "confirmed" | "received" | "cancelled";
export type OrderStatus = SalesStatus | PurchaseStatus;

export interface SalesOrderSummary {
  id: string;
  customer_id: string;
  customer_name: string;
  status: SalesStatus;
  order_date: string;
  currency: string;
  total_amount: string;
  line_count: number;
  created_at: string;
}

export interface PurchaseOrderSummary {
  id: string;
  supplier_id: string;
  supplier_name: string;
  status: PurchaseStatus;
  order_date: string;
  currency: string;
  total_amount: string;
  line_count: number;
  created_at: string;
}

export interface ListResult<T> {
  items: T[];
  total: number;
  total_value: string; // sum over every matching row, not just this page
}

export type SortField = "order_date" | "-order_date" | "total_amount" | "-total_amount";

export interface OrderFilters {
  status: string[];
  dateFrom: string;
  dateTo: string;
  amountMin: string;
  amountMax: string;
  search: string;
  sort: SortField;
  limit: number;
  offset: number;
}

export const DEFAULT_FILTERS: OrderFilters = {
  status: [],
  dateFrom: "",
  dateTo: "",
  amountMin: "",
  amountMax: "",
  search: "",
  sort: "-order_date",
  limit: 25,
  offset: 0,
};
