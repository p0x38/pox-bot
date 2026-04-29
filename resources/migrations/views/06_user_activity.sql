CREATE OR REPLACE VIEW user_activity AS
SELECT
    s.user_id,
    s.total_messages,
    COALESCE(t.total_transactions, 0) AS total_transactions,
    COALESCE(i.total_items, 0) AS total_items

FROM user_stats s
LEFT JOIN transaction_stats t ON s.user_id = t.user_id
LEFT JOIN inventory_summary i ON s.user_id = i.user_id;