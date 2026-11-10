-- Council discretionary awards grouped by funding source (initiative) or by
-- recipient organization. :group_by is chosen in Python from a fixed list,
-- never from user input.
SELECT
    {group_by}                         AS category,
    COUNT(*)                           AS awards,
    ROUND(SUM(amount), 0)              AS total_dollars,
    ROUND(AVG(amount), 0)              AS mean_award,
    ROUND(100.0 * SUM(amount) / SUM(SUM(amount)) OVER (), 2) AS pct_of_total_dollars
FROM discretionary
GROUP BY {group_by}
ORDER BY total_dollars DESC;
