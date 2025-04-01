from clinical_documentation.models.mpractice_template import MPracticeTemplate
from clinical_documentation.repository.mpractice_template import (
    MPracticeTemplateRepository,
)


def test_create(db, factories):
    # Given
    mpractice_template_repository = MPracticeTemplateRepository(session=db.session)
    template = factories.MPracticeTemplateFactory.create()
    inputs = (
        template.owner_id,
        template.sort_order,
        template.is_global,
        template.title,
        template.text,
    )
    # When
    created = mpractice_template_repository.create_mpractice_template(
        owner_id=template.owner_id,
        sort_order=template.sort_order,
        is_global=template.is_global,
        text=template.text,
        title=template.title,
    )
    # Then
    assert (
        created.id
        and (
            created.owner_id,
            created.sort_order,
            created.is_global,
            created.title,
            created.text,
        )
        == inputs
    )


def test_get_all(
    db,
    factories,
    created_mpractice_template: MPracticeTemplate,
    mpractice_template_repository,
):
    # Given
    owner_id = created_mpractice_template.owner_id
    # When
    templates = mpractice_template_repository.get_mpractice_templates_by_owner(
        owner_id=owner_id
    )
    # Then
    assert len(templates) == 1
    assert templates[0] == created_mpractice_template


def test_get_all_for_owner_with_no_templates(
    db,
    factories,
    created_mpractice_template: MPracticeTemplate,
    mpractice_template_repository,
):
    # Given
    owner_id = created_mpractice_template.owner_id + 1
    # When
    templates = mpractice_template_repository.get_mpractice_templates_by_owner(
        owner_id=owner_id
    )
    # Then
    assert len(templates) == 0


def test_get_by_title(
    db,
    factories,
    created_mpractice_template: MPracticeTemplate,
    mpractice_template_repository,
):
    # Given
    owner_id = created_mpractice_template.owner_id
    title = created_mpractice_template.title
    # When
    template = mpractice_template_repository.get_mpractice_templates_by_title(
        owner_id=owner_id,
        title=title,
    )
    # Then
    assert template.title == title


def test_update_title(
    db,
    factories,
    created_mpractice_template: MPracticeTemplate,
    mpractice_template_repository,
):
    # Given
    new_title = "A new title"
    assert new_title != created_mpractice_template.title

    # When
    updated = mpractice_template_repository.edit_mpractice_template_by_id(
        template_id=created_mpractice_template.id,
        owner_id=created_mpractice_template.owner_id,
        title=new_title,
        text=None,
    )
    # Then
    assert updated.title == new_title


def test_update_text(
    db,
    factories,
    created_mpractice_template: MPracticeTemplate,
    mpractice_template_repository,
):
    # Given
    new_text = "Some new text"
    assert new_text != created_mpractice_template.text

    # When
    updated = mpractice_template_repository.edit_mpractice_template_by_id(
        template_id=created_mpractice_template.id,
        owner_id=created_mpractice_template.owner_id,
        title=None,
        text=new_text,
    )
    # Then
    assert updated.text == new_text


def test_update_title_and_text(
    db,
    factories,
    created_mpractice_template: MPracticeTemplate,
    mpractice_template_repository,
):
    # Given
    new_title = "A new title"
    new_text = "Some new text"
    assert new_title != created_mpractice_template.title
    assert new_text != created_mpractice_template.text

    # When
    updated = mpractice_template_repository.edit_mpractice_template_by_id(
        template_id=created_mpractice_template.id,
        owner_id=created_mpractice_template.owner_id,
        title=new_title,
        text=new_text,
    )
    # Then
    assert updated.title == new_title
    assert updated.text == new_text


def test_update_without_changes(
    db,
    factories,
    created_mpractice_template: MPracticeTemplate,
    mpractice_template_repository,
):
    # When
    updated = mpractice_template_repository.edit_mpractice_template_by_id(
        template_id=created_mpractice_template.id,
        owner_id=created_mpractice_template.owner_id,
        title=None,
        text=None,
    )
    # Then
    assert updated.title == created_mpractice_template.title
    assert updated.text == created_mpractice_template.text


def test_delete(
    db,
    factories,
    created_mpractice_template: MPracticeTemplate,
    mpractice_template_repository,
):
    # Given
    pre_deletion_templates = (
        mpractice_template_repository.get_mpractice_templates_by_owner(
            owner_id=created_mpractice_template.owner_id
        )
    )

    # When
    delete_success = mpractice_template_repository.delete_mpractice_template_by_id(
        template_id=created_mpractice_template.id,
        owner_id=created_mpractice_template.owner_id,
    )
    post_deletion_templates = (
        mpractice_template_repository.get_mpractice_templates_by_owner(
            owner_id=created_mpractice_template.owner_id
        )
    )

    # Then
    assert delete_success is True
    assert len(post_deletion_templates) == len(pre_deletion_templates) - 1


def test_delete_when_does_not_exist(
    db,
    factories,
    created_mpractice_template: MPracticeTemplate,
    mpractice_template_repository,
):
    # Given
    pre_deletion_templates = (
        mpractice_template_repository.get_mpractice_templates_by_owner(
            owner_id=created_mpractice_template.owner_id
        )
    )

    # When
    delete_success = mpractice_template_repository.delete_mpractice_template_by_id(
        template_id=created_mpractice_template.id + 1,
        owner_id=created_mpractice_template.owner_id,
    )

    post_deletion_templates = (
        mpractice_template_repository.get_mpractice_templates_by_owner(
            owner_id=created_mpractice_template.owner_id
        )
    )

    # Then
    assert delete_success is False
    assert len(post_deletion_templates) == len(pre_deletion_templates)


def test_get_no_templates(
    db,
    factories,
):
    # Given
    mpractice_template_repository = MPracticeTemplateRepository(session=db.session)
    owner_id = 1
    # When
    templates = mpractice_template_repository.get_mpractice_templates_by_owner(
        owner_id=owner_id
    )
    # Then
    assert len(templates) == 0


# todo: test sorting by sort_order and by created_at
# def test_get_sorted_templates(
#         db,
#         factories,
# )
