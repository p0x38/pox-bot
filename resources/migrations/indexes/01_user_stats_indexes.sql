CREATE INDEX IF NOT EXISTS idx_user_stats_xp
ON user_stats (xp DESC);

CREATE INDEX IF NOT EXISTS idx_user_stats_level
ON user_stats (level DESC);