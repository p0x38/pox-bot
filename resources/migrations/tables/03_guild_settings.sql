CREATE TABLE IF NOT EXISTS guild_settings (
    guild_id BIGINT PRIMARY KEY,
    config JSONB DEFAULT '{}'::jsonb
);