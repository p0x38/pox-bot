CREATE TABLE IF NOT EXISTS economy_inventory (
    user_id BIGINT NOT NULL,
    item_id TEXT NOT NULL,
    quantity INT DEFAULT 1,
    PRIMARY KEY (user_id, item_id)
);

CREATE TABLE IF NOT EXISTS economy_items (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    buy_price BIGINT,
    sell_price BIGINT,
    description TEXT
);

CREATE TABLE IF NOT EXISTS economy_transactions (
    id SERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL,
    type TEXT NOT NULL,
    amount BIGINT NOT NULL,
    description TEXT,
    timestamp BIGINT NOT NULL
);

CREATE TABLE IF NOT EXISTS economy_users (
    user_id BIGINT PRIMARY KEY,
    wallet BIGINT DEFAULT 0,
    bank BIGINT DEFAULT 0,
    last_daily BIGINT DEFAULT 0,
    last_work BIGINT DEFAULT 0
);