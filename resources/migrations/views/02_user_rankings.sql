CREATE OR REPLACE VIEW user_rankings AS
SELECT
    user_id,
    xp,
    level,
    RANK() OVER (ORDER BY xp DESC) AS rank
FROM user_stats;