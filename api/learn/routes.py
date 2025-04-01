from learn.resources import (
    bookmarks,
    course_member_status,
    user_courses_resource,
    videos,
    webhook,
)


def add_routes(api):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    api.add_resource(
        course_member_status.CourseMemberStatusesResource,
        "/v1/library/courses/<course_slug>/member_statuses",
    )
    api.add_resource(
        course_member_status.CourseMemberStatusResource,
        "/v1/library/courses/<course_slug>/member_statuses/<int:user_id>",
    )
    api.add_resource(
        user_courses_resource.UserCoursesResource, "/v1/users/<int:user_id>/courses"
    )
    api.add_resource(
        bookmarks.MemberSavedContentResource, "/v1/library/bookmarks/<url_slug>"
    )
    api.add_resource(
        bookmarks.MemberSavedContentLibraryResource, "/v1/library/bookmarks"
    )
    api.add_resource(webhook.LearnContentfulWebhook, "/v1/library/contentful/webhook")
    api.add_resource(videos.VideosResource, "/v1/-/library/videos")

    return api
