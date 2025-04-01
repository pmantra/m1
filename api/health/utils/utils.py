from uuid import uuid4

from maven.feature_flags import Context


def build_user_context(user_id: int) -> Context:
    return (
        Context.builder(str(uuid4()))
        .kind("user")
        .set("userId", user_id)
        .private("userId")
        .build()
    )
