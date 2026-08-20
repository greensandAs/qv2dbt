-- sales_fact  [mart]  (from QlikView 'resident')
select
    ProductID,
    Country,
    TherapeuticArea,
    YEAR(OrderDate) as ORDERYEAR,
    SUM(GrossAmount) as TOTALREVENUE,
    SUM(Quantity) as TOTALUNITS
from LUNDBECK_UKIE.STAGING.INT_SALES_ENRICHED as base
group by ProductID, Country, TherapeuticArea, YEAR(OrderDate)
;
