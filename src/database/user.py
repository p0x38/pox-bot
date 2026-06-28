from src.bases import BaseDatabase
from src.models.user_profile_orm import UserActivity, UserProfile


class UserDatabase(BaseDatabase):
    def __init__(self, dsn: str):
        super().__init__(dsn)

    async def get_full_profile(self, user_id: int) -> UserProfile | None:
        async with self.async_session() as session:
            return await session.get(UserProfile, user_id)

    async def update_profile(
        self,
        user_id: int,
        description: str | None = None,
        nickname: str | None = None,
    ):
        async with self.async_session() as session, session.begin():
            profile = await session.get(UserProfile, user_id) or UserProfile(user_id=user_id)

            if description is not None:
                profile.description = description

            if nickname is not None:
                profile.nickname = nickname

            await session.merge(profile)

    async def get_activity_stats(self, user_id: int) -> UserActivity | None:
        async with self.async_session() as session:
            return await session.get(UserActivity, user_id)

    async def increment_activity(self, user_id: int, activity_type: str):
        async with self.async_session() as session, session.begin():
            activity = await session.get(UserActivity, user_id) or UserActivity(user_id=user_id)

            if activity_type == "command":
                activity.commands_run += 1
            elif activity_type == "message":
                activity.messages_sent += 1

            await session.merge(activity)
