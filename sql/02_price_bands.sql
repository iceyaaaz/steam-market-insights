-- selected is the filtered, one-row-per-game cohort. Unknown review rates stay NULL.
SELECT price_band, count(*) AS games,
    count(positive_rate) AS rated_games,
    median(positive_rate) AS median_positive_rate,
    sum(positive)::DOUBLE / NULLIF(sum(reviews), 0) AS weighted_positive_rate,
    median(reviews) AS median_reviews,
    avg(CASE WHEN positive_rate IS NOT NULL THEN (positive_rate >= 0.9)::INTEGER END) AS high_rating_share
FROM selected GROUP BY price_band;
