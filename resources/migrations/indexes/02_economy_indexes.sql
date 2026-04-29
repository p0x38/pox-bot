CREATE INDEX IF NOT EXISTS idx_economy_wallet
ON economy_users (wallet DESC);

CREATE INDEX IF NOT EXISTS idx_economy_bank
ON economy_users (bank DESC);

CREATE INDEX IF NOT EXISTS idx_transactions_user
ON economy_transactions (user_id);

CREATE INDEX IF NOT EXISTS idx_inventory_user
ON economy_inventory (user_id);