# Lineage — stress_test.qvs

## Table-level lineage

```mermaid
flowchart LR
  subgraph SOURCE
    n_source_customers["customers\n(qvd)"]
    n_source_orders["orders\n(qvd)"]
  end
  subgraph STAGING
    n_Customers["Customers"]
  end
  subgraph INTERMEDIATE
    n_Orders["Orders"]
    n_Orders_join3["Orders__join3"]
  end
  subgraph MART
    n_sales_fact["sales_fact"]
  end
  subgraph MAPPING
    n_map_1["map_1"]
  end
  n_Customers --> n_Orders_join3
  n_Orders --> n_sales_fact
  n_Orders_join3 --> n_Orders
  n_source_customers --> n_Customers
  n_source_orders --> n_Orders
  classDef source fill:#DDEBF7,stroke:#2E75B6;
  classDef mart fill:#FCE4D6,stroke:#C55A11;
  class n_source_customers n_source_orders source;
  class n_sales_fact mart;
```

## Column lineage — sales_fact

```mermaid
flowchart LR
  n_sales_fact_ProductID["ProductID"]
  n_orders_ProductID(["orders.ProductID"])
  n_orders_ProductID --> n_sales_fact_ProductID
  n_sales_fact_Country["Country"]
  n_customers_CountryCode(["customers.CountryCode"])
  n_customers_CountryCode --> n_sales_fact_Country
  n_sales_fact_OrderYear["OrderYear"]
  n_orders_OrderDate(["orders.OrderDate"])
  n_orders_OrderDate --> n_sales_fact_OrderYear
  n_sales_fact_OrderMonth["OrderMonth"]
  n_orders_OrderDate --> n_sales_fact_OrderMonth
  n_sales_fact_TotalRevenue["TotalRevenue"]
  n_orders_UnitPrice(["orders.UnitPrice"])
  n_orders_UnitPrice --> n_sales_fact_TotalRevenue
  n_orders_Quantity(["orders.Quantity"])
  n_orders_Quantity --> n_sales_fact_TotalRevenue
  n_sales_fact_OrderCount["OrderCount"]
  n_orders_OrderID(["orders.OrderID"])
  n_orders_OrderID --> n_sales_fact_OrderCount
  n_sales_fact_AvgOrderValue["AvgOrderValue"]
  n_orders_UnitPrice --> n_sales_fact_AvgOrderValue
  n_orders_Quantity --> n_sales_fact_AvgOrderValue
  n_sales_fact_MedianOrderValue["MedianOrderValue"]
  n_orders_UnitPrice --> n_sales_fact_MedianOrderValue
  n_orders_Quantity --> n_sales_fact_MedianOrderValue
```
