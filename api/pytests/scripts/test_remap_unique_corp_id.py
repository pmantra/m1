from models.enterprise import Organization, OrganizationEmployee
from storage.connection import db
from utils.migrations.corp_id_remapping.remap_corp_ids import remap_corp_ids


def test_remap_corp_ids(factories, session):
    # Given
    org: Organization = factories.OrganizationFactory.create(name="Awesome Corp")
    remapping_data = [
        {"old_corp_id": "0001", "new_corp_id": "1000"},
        {"old_corp_id": "0002", "new_corp_id": "2000"},
        {"old_corp_id": "0003", "new_corp_id": "3000"},
        {"old_corp_id": "3000", "new_corp_id": "0003"},
    ]
    for m in remapping_data:
        factories.OrganizationEmployeeFactory.create(
            organization=org, unique_corp_id=m["old_corp_id"]
        )
    expected_ids = {m["new_corp_id"] for m in remapping_data}
    # When
    remap_corp_ids(org.id, remapping_data, chunk_size=1)
    remapped = (
        db.session.query(OrganizationEmployee.unique_corp_id)
        .filter(OrganizationEmployee.unique_corp_id.in_(expected_ids))
        .all()
    )
    remapped_ids = {r.unique_corp_id for r in remapped}
    # Then
    assert remapped_ids == expected_ids
