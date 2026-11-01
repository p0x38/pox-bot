from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .database import DatabaseManager


class PrivacyService:
    """Coordinate user data export and deletion."""

    def __init__(self, database: 'DatabaseManager') -> None:
        self.database = database

    async def export_user_data(self, user_id: int) -> dict[str, Any]:
        privacy_database = self.database.privacy

        if privacy_database is None:
            raise RuntimeError('Privacy database is unavailable.')

        return await privacy_database.export_user_data(user_id)

    async def delete_user_data(
        self,
        user_id: int,
    ) -> dict[str, dict[str, int]]:
        privacy_database = self.database.privacy

        if privacy_database is None:
            raise RuntimeError('Privacy database is unavailable.')

        report = await privacy_database.delete_user_data(user_id)

        # The SQL transaction has committed successfully at this point.
        # Invalidate any cached account data so it cannot be reused.
        economy_database = self.database.economy

        if economy_database is not None:
            economy_database.invalidate_user(user_id)

        settings_database = self.database.settings

        if settings_database is not None:
            settings_database.invalidate_user(user_id)

        guild_database = self.database.guild

        if guild_database is not None:
            guild_database.invalidate_config_cache()

        return report
