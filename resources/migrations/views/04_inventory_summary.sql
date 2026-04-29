CREATE OR REPLACE VIEW inventory_summary AS
SELECT
    user_id,
    COUNT(*) AS unique_items,
    SUM(quantity) AS total_items
FROM economy_inventory
GROUP BY user_id;