-- Raw JSON fields are staged as strings. Invalid values become NULL, never zero.
CREATE OR REPLACE TABLE typed AS
SELECT
    TRY_CAST(app_id AS BIGINT) AS app_id, NULLIF(TRIM(name), '') AS name,
    COALESCE(TRY_STRPTIME(release_date, '%b %d, %Y')::DATE,
             TRY_STRPTIME(release_date, '%b %Y')::DATE,
             TRY_CAST(release_date AS DATE)) AS release_date,
    TRY_CAST(price AS DOUBLE) AS price,
    TRY_CAST(positive AS BIGINT) AS positive,
    TRY_CAST(negative AS BIGINT) AS negative,
    TRY_CAST(peak_ccu AS BIGINT) AS peak_ccu,
    TRY_CAST(discount AS DOUBLE) AS discount,
    genres, developers, estimated_owners,
    ROW_NUMBER() OVER (PARTITION BY app_id ORDER BY source_row) AS duplicate_rank
FROM raw_games;

CREATE OR REPLACE TABLE audited AS
SELECT *, CASE
    WHEN app_id IS NULL OR app_id <= 0 THEN 'invalid_app_id'
    WHEN duplicate_rank > 1 THEN 'duplicate_app_id'
    WHEN name IS NULL THEN 'missing_name'
    WHEN regexp_matches(lower(name), '\b(demo|playtest|dedicated server|soundtrack)\b') THEN 'non_base_game_name'
    WHEN release_date IS NULL THEN 'invalid_release_date'
    WHEN release_date > (SELECT as_of FROM settings) THEN 'future_release'
    ELSE 'included' END AS disposition
FROM typed;

CREATE OR REPLACE TABLE games AS
WITH valid AS (
    SELECT app_id, name, release_date, year(release_date)::INTEGER AS release_year,
        CASE WHEN price >= 0 AND isfinite(price) THEN price END AS price,
        CASE WHEN positive >= 0 AND negative >= 0 THEN positive END AS positive,
        CASE WHEN positive >= 0 AND negative >= 0 THEN negative END AS negative,
        CASE WHEN peak_ccu >= 0 THEN peak_ccu END AS peak_ccu,
        CASE WHEN discount BETWEEN 0 AND 100 THEN discount END AS discount,
        genres, developers, estimated_owners
    FROM audited WHERE disposition = 'included'
), metrics AS (
    SELECT *, positive + negative AS reviews,
        positive::DOUBLE / NULLIF(positive + negative, 0) AS positive_rate
    FROM valid
)
SELECT *, CASE
    WHEN price IS NULL THEN '价格未知'
    WHEN price = 0 THEN '零价'
    WHEN price < 5 THEN '(0,5)'
    WHEN price < 10 THEN '[5,10)'
    WHEN price < 20 THEN '[10,20)'
    WHEN price < 40 THEN '[20,40)'
    ELSE '40+' END AS price_band,
    -- Wilson lower bound rewards confidence, not just a perfect small sample.
    CASE WHEN reviews > 0 THEN
      (positive_rate + 3.8416/(2*reviews) - 1.96 *
       sqrt(positive_rate*(1-positive_rate)/reviews + 3.8416/(4.0*reviews*reviews)))
      / (1 + 3.8416/reviews) END AS wilson_lower
FROM metrics;

CREATE OR REPLACE TABLE game_tags AS
SELECT DISTINCT t.app_id::BIGINT AS app_id, TRIM(t.tag) AS tag
FROM raw_tags t JOIN games g ON t.app_id::BIGINT = g.app_id
WHERE NULLIF(TRIM(t.tag), '') IS NOT NULL;
