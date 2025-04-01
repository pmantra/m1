from unittest.mock import call


def test_get_related_reads(
    thumbnail_service_mock, title_service_mock, related_reads_list
):

    # Import to ensure that the mocks are loaded
    from learn.services.predicted_related_reads_service import (
        PredictedRelatedReadsService,
    )

    service = PredictedRelatedReadsService()

    # Act
    result = service.get_related_reads("how-to-baby-proof-your-home")

    # Verify the thumbnail service was called with the correct slugs
    call_list = [
        call("4-safety-tips-for-dressing-your-baby-in-cold-weather"),
        call("must-have-items-for-bringing-baby-home-its-way-less-than-you-think"),
        call("dressing-baby-for-hot-weather"),
    ]

    # Verify that the thumbnail service was called by the correct slugs
    thumbnail_service_mock().get_thumbnail_by_slug.assert_has_calls(call_list)

    # Verify that the title service was called by the correct slugs
    title_service_mock().get_value.assert_has_calls(call_list)

    # Verify the expected result

    related_reads_list.sort(key=lambda x: x.slug)
    result.sort(key=lambda x: x.slug)
    assert result == related_reads_list


def test_empty_related_reads(thumbnail_service_mock, title_service_mock):
    from learn.services.predicted_related_reads_service import (
        PredictedRelatedReadsService,
    )

    service = PredictedRelatedReadsService()
    results = service.get_related_reads("this-is-not-an-article")
    assert results == []
