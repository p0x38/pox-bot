CREATE TABLE IF NOT EXISTS active_giveaways (
    message_id BIGINT PRIMARY KEY,
    channel_id BIGINT NOT NULL,
    guild_id BIGINT NOT NULL,
    end_time BIGINT NOT NULL,
    winners INTEGER NOT NULL,
    prize TEXT NOT NULL,
    host_id BIGINT NOT NULL
);
