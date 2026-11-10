-- Agency totals for ONE budget publication (the latest available for the
-- fiscal year), with each agency's share of the citywide total.
WITH latest AS (
    SELECT MAX(publication_date) AS publication_date FROM expense
),
agency_totals AS (
    SELECT
        e.agency_name,
        SUM(e.adopted_budget_amount)          AS adopted,
        SUM(e.current_modified_budget_amount) AS modified,
        SUM(e.financial_plan_amount)          AS financial_plan
    FROM expense e
    JOIN latest l ON e.publication_date = l.publication_date
    GROUP BY e.agency_name
)
SELECT
    agency_name,
    ROUND(adopted / 1e9, 3)                                AS adopted_billions,
    ROUND(modified / 1e9, 3)                               AS modified_billions,
    ROUND(financial_plan / 1e9, 3)                         AS financial_plan_billions,
    ROUND(100.0 * modified / SUM(modified) OVER (), 2)     AS pct_of_citywide_modified,
    RANK() OVER (ORDER BY modified DESC)                   AS rank_by_modified
FROM agency_totals
ORDER BY modified DESC;
