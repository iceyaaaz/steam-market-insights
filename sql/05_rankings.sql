SELECT app_id, name, price_band, reviews, positive_rate, wilson_lower,
    DENSE_RANK() OVER (PARTITION BY price_band ORDER BY wilson_lower DESC NULLS LAST) AS rank_in_price_band
FROM selected WHERE reviews >= 100
QUALIFY rank_in_price_band <= 10
ORDER BY price_band, rank_in_price_band, app_id;
