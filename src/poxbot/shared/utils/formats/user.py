from discord import PublicUserFlags

FLAG_LABELS = {
    'active_developer': 'Active Developer',
    'bug_hunter': 'Bug Hunter',
    'bug_hunter_level_2': 'Level 2 Bug Hunter',
    'discord_certified_moderator': 'Discord Certified Moderator',
    'early_supporter': 'Early Supporter',
    'early_verified_bot_developer': 'Early Verified Bot Developer',
    'hypesquad': 'Hypesquad',
    'hypesquad_balance': 'Hypesquad Balance Member',
    'hypesquad_bravery': 'Hypesquad Bravery Member',
    'hypesquad_brilliance': 'Hypesquad Brilliance Member',
    'partner': 'Partner',
    'spammer': 'Likely Spammer',
    'staff': 'Discord Staff',
    'system': 'Discord System',
    'team_user': 'Team User',
    'verified_bot': 'Bot (Verified)',
    'verified_bot_developer': 'Verified Bot Developer',
}


def format_userflags(
    user_flag: PublicUserFlags,
    use_translation_key: bool = True,
):
    return [
        f'text.user_flags.{flag.name}'
        if use_translation_key
        else FLAG_LABELS.get(flag.name, flag.name)
        for flag in user_flag.all()
    ]
