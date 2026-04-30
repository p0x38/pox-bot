CREATE OR REPLACE VIEW user_profile_full AS
SELECT
    s.user_id,
    s.xp,
    s.level,
    s.total_messages,

    e.wallet,
    e.bank,
    (COALESCE(e.wallet, 0) + COALESCE(e.bank, 0)) AS total_money,

    p.description,
    p.nickname

FROM user_stats s
LEFT JOIN economy_users e ON s.user_id = e.user_id
LEFT JOIN user_profiles p ON s.user_id = p.user_id;