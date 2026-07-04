CREATE OR REPLACE VIEW transaction_stats AS
SELECT
    user_id,
    COUNT(*) AS total_transactions,
    SUM(amount) AS total_amount
FROM economy_transactions
GROUP BY user_id;