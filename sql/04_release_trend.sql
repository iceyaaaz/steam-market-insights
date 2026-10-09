-- Fill missing years BEFORE LAG; current snapshot year is incomplete.
WITH years AS (
    SELECT range::INTEGER AS release_year
    FROM range($start_year, $end_year + 1)
), counts AS (
    SELECT release_year, count(*) AS games FROM selected GROUP BY release_year
), dense AS (
    SELECT y.release_year, coalesce(c.games,0) AS games
    FROM years y LEFT JOIN counts c USING(release_year)
), lagged AS (
    SELECT *, LAG(games) OVER (ORDER BY release_year) AS previous_year_games
    FROM dense
)
SELECT *, CASE WHEN release_year < $snapshot_year THEN
    (games - previous_year_games)::DOUBLE / NULLIF(previous_year_games,0)
    END AS yoy,
    release_year = $snapshot_year AS partial_year
FROM lagged ORDER BY release_year;
