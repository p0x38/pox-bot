CREATE INDEX IF NOT EXISTS idx_tickets_user_id ON active_tickets(user_id);
CREATE INDEX IF NOT EXISTS idx_tickets_guild_id ON active_tickets(guild_id);