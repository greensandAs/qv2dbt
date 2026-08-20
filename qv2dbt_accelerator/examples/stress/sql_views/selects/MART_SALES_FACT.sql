-- sales_fact  [mart]  (from QlikView 'resident')
select
    ProductID,
    Country,
    YEAR(OrderDate) as ORDERYEAR,
    MONTH(OrderDate) as ORDERMONTH,
    SUM(GrossAmount) as TOTALREVENUE,
    COUNT(OrderID) as ORDERCOUNT,
    AVG(GrossAmount) as AVGORDERVALUE,
    MEDIAN(GrossAmount) as MEDIANORDERVALUE
from LUNDBECK_UKIE.STAGING.INT_ORDERS as base
group by ProductID, Country, YEAR(OrderDate), MONTH(OrderDate)
;
