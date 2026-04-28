CREATE TABLE IF NOT EXISTS user_preferences (
    user_id BIGINT PRIMARY KEY,
    data JSONB DEFAULT '{}'::jsonb
);