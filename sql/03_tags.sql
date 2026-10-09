WITH metrics AS (
    SELECT t.tag, count(*) AS games, median(s.positive_rate) AS median_positive_rate,
        sum(s.positive)::DOUBLE / NULLIF(sum(s.reviews),0) AS weighted_positive_rate,
        median(s.reviews) AS median_reviews, median(s.price) AS median_price
    FROM selected s JOIN game_tags t USING(app_id)
    GROUP BY t.tag HAVING count(*) >= $min_games
)
SELECT *, DENSE_RANK() OVER (ORDER BY median_positive_rate DESC NULLS LAST) AS rating_rank
FROM metrics ORDER BY median_positive_rate DESC NULLS LAST, games DESC, tag;
