-- Orders  [intermediate]  (from QlikView 'qvd')
select *
from (select 
    OrderID,
    CustomerID,
    ProductID,
    TO_NUMBER(Quantity) as QUANTITY,
    TO_NUMBER(UnitPrice) * TO_NUMBER(Quantity) as GROSSAMOUNT,
    GREATEST(Discount1, Discount2) as MAXDISCOUNT,
    /* TODO review */ Peek('PrevOrder', -1, 'Orders') as PREVORDERREF,
    TO_DATE(OrderDate) as ORDERDATE,
    DATE_TRUNC('MONTH', OrderDate) as ORDERMONTH
from LUNDBECK_UKIE.RAW.ORDERS) as base
left join LUNDBECK_UKIE.STAGING.INT_ORDERS_JOIN3 as j1 using (CUSTOMERID)
;
