-- Number of distinct budget requests per community board and responsible
-- agency. The requests table holds the pooled publication years with one row
-- per tracking code (repeats within and across years removed in Python; see
-- Section 3.1 of the notebook).
SELECT
    board,
    responsible_agency,
    COUNT(*) AS requests
FROM requests
GROUP BY board, responsible_agency
ORDER BY board, requests DESC;
