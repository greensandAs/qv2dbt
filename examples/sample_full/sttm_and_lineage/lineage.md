# Lineage — sales_pipeline.qvs

## Table-level lineage

```mermaid
flowchart LR
  subgraph SOURCE
    n_source_products["products\n(qvd)"]
    n_source_sales_2026["sales_2026\n(file)"]
    n_source_sales_2025["sales_2025\n(qvd)"]
  end
  subgraph STAGING
    n_Products["Products"]
    n_SalesPY["SalesPY"]
  end
  subgraph INTERMEDIATE
    n_SalesRaw["SalesRaw"]
    n_SalesRaw_join4["SalesRaw__join4"]
    n_SalesEnriched["SalesEnriched"]
    n_SalesEnriched_join6["SalesEnriched__join6"]
  end
  subgraph MART
    n_sales_fact["sales_fact"]
  end
  subgraph MAPPING
    n_CountryMap["CountryMap"]
  end
  n_CountryMap --> n_SalesRaw
  n_Products --> n_SalesEnriched_join6
  n_SalesEnriched --> n_sales_fact
  n_SalesEnriched_join6 --> n_SalesEnriched
  n_SalesRaw --> n_SalesEnriched
  n_source_products --> n_Products
  n_source_sales_2025 --> n_SalesPY
  n_source_sales_2026 --> n_SalesRaw
  classDef source fill:#DDEBF7,stroke:#2E75B6;
  classDef mart fill:#FCE4D6,stroke:#C55A11;
  class n_source_products n_source_sales_2026 n_source_sales_2025 source;
  class n_sales_fact mart;
```

## Column lineage — sales_fact

```mermaid
flowchart LR
  n_sales_fact_ProductID["ProductID"]
  n_products_ProductID(["products.ProductID"])
  n_products_ProductID --> n_sales_fact_ProductID
  n_sales_fact_Country["Country"]
  n_sales_2026_CountryCode(["sales_2026.CountryCode"])
  n_sales_2026_CountryCode --> n_sales_fact_Country
  n_sales_fact_TherapeuticArea["TherapeuticArea"]
  n_products_Therapeutic_Area(["products.Therapeutic Area"])
  n_products_Therapeutic_Area --> n_sales_fact_TherapeuticArea
  n_sales_fact_OrderYear["OrderYear"]
  n_sales_2026_OrderDate(["sales_2026.OrderDate"])
  n_sales_2026_OrderDate --> n_sales_fact_OrderYear
  n_sales_fact_TotalRevenue["TotalRevenue"]
  n_sales_2026_UnitPrice(["sales_2026.UnitPrice"])
  n_sales_2026_UnitPrice --> n_sales_fact_TotalRevenue
  n_sales_2026_Quantity(["sales_2026.Quantity"])
  n_sales_2026_Quantity --> n_sales_fact_TotalRevenue
  n_sales_fact_TotalUnits["TotalUnits"]
  n_sales_2026_Quantity --> n_sales_fact_TotalUnits
```
