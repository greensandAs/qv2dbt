SELECT *
FROM (
  SELECT
    COLUMN1::VARCHAR AS MONTH,
    COLUMN2::INTEGER AS MONTHSORT,
    COLUMN3::INTEGER AS MONTHSORT_CY
  FROM VALUES
    (4, 1, 4),
    (5, 2, 5),
    (6, 3, 6),
    (7, 4, 7),
    (8, 5, 8),
    (9, 6, 9),
    (10, 7, 10),
    (11, 8, 11),
    (12, 9, 12),
    (1, 10, 1),
    (2, 11, 2),
    (3, 12, 3)
) AS inline_data(MONTH, MONTHSORT, MONTHSORT_CY)