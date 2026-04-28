CREATE TABLE IF NOT EXISTS user_stats (
    user_id BIGINT PRIMARY KEY,
    message_count BIGINT DEFAULT 0,
    xp BIGINT DEFAULT 0
);