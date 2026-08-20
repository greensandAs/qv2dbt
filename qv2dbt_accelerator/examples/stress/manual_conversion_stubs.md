# Manual Conversion Stubs — stress_test.qvs

QlikView control flow has no row-level SQL equivalent, so these blocks were **not** auto-converted. Each is listed below with recommended conversion guidance. Inner `LOAD` statements were still parsed into models; only the control scaffolding needs manual work.

## Summary

| Construct | Count |
|---|---|
| `call` | 1 |
| `for` | 1 |
| `if` | 1 |
| `sub` | 1 |

## 1. `sub` (lines 6–9)

**Guidance:** SUB routine -> convert to a dbt macro (macros/) or a parameterised model; replace CALL sites with the macro/ref.

```qlik
SUB LoadQVD(tableName, fileName)
    [$(tableName)]:
    LOAD * FROM [$(vPath)$(fileName)] (qvd);
END SUB
```

## 2. `call` (lines 11–11)

**Guidance:** SUB invocation -> reference the converted macro/model.

```qlik
CALL LoadQVD('RawCustomers', 'customers.qvd')
```

## 3. `for` (lines 14–17)

**Guidance:** Loop (often over files/QVDs) -> in dbt use an external stage + one COPY/LOAD, or a for-loop over a var/seed that UNIONs sources.

```qlik
FOR EACH vFile IN 'sales_2023.qvd', 'sales_2024.qvd'
    SalesHist:
    LOAD OrderID, Amount FROM [$(vPath)$(vFile)] (qvd);
NEXT vFile
```

## 4. `if` (lines 20–22)

**Guidance:** Conditional script branch -> encode with dbt vars / target-based conditional refs; this is not a row-level WHERE.

```qlik
IF WeekDay(vRunDate) = 0 THEN
    TRACE Running Monday full load;
ENDIF
```
