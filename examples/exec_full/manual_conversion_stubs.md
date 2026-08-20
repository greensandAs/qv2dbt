# Manual Conversion Stubs — Executive Dashboard.qvs

QlikView control flow has no row-level SQL equivalent, so these blocks were **not** auto-converted. Each is listed below with recommended conversion guidance. Inner `LOAD` statements were still parsed into models; only the control scaffolding needs manual work.

## Summary

| Construct | Count |
|---|---|
| `exit` | 1 |

## 1. `exit` (lines 272–272)

**Guidance:** EXIT SCRIPT -> no equivalent; ensure downstream models still build.

```qlik
Exit Script
```
