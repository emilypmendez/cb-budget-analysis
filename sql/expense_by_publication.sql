-- Data quality check: how many budget publications exist for the fiscal year?
-- Each publication (preliminary, executive, adopted, and later modifications)
-- restates the whole budget, so totals summed across publications count the
-- same dollars more than once.
SELECT
    publication_date,
    COUNT(*)                                          AS line_items,
    ROUND(SUM(current_modified_budget_amount) / 1e9, 2) AS modified_budget_billions
FROM expense
GROUP BY publication_date
ORDER BY publication_date;
