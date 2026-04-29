CREATE OR REPLACE VIEW user_progress AS
SELECT
    user_id,
    xp,
    level,
    total_messages,

    floor(pow(xp, 0.25))::int AS computed_level,

    (xp - pow(level, 4)) AS progress_xp,
    (pow(level + 1, 4) - pow(level, 4)) AS required_xp,

    (floor(pow(xp, 0.25))::int > level) AS should_level_up
FROM user_stats;