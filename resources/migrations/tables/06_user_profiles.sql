CREATE TABLE IF NOT EXISTS user_profiles (
    user_id BIGINT PRIMARY KEY,
    description TEXT,
    nickname TEXT,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);