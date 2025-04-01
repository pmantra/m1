"""Drop OrganizationModuleAssignedAdvocate and ModuleAssignedAdvocate tables

Revision ID: 997b191e8fca
Revises: 1bef8e26445d
Create Date: 2022-02-08 15:23:27.468767+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "997b191e8fca"
down_revision = "b3419f9197d0"
branch_labels = None
depends_on = None


def upgrade():
    op.drop_table("organization_module_assigned_advocate")
    op.drop_table("module_assigned_advocate")


def downgrade():
    op.execute(
        """
        CREATE TABLE `organization_module_assigned_advocate` (
            `id` bigint(20) NOT NULL,
            `organization_id` int(11) NOT NULL,
            `module_id` int(11) NOT NULL,
            `advocate_id` int(11) NOT NULL,
            PRIMARY KEY (`id`),
            UNIQUE KEY `organization_module_assigned_advocate_uq_1` (`organization_id`,`module_id`,`advocate_id`),
            KEY `organization_module_assigned_advocate_ibfk_2` (`module_id`),
            KEY `organization_module_assigned_advocate_ibfk_3` (`advocate_id`),
            CONSTRAINT `organization_module_assigned_advocate_ibfk_1` FOREIGN KEY (`organization_id`) REFERENCES `organization` (`id`),
            CONSTRAINT `organization_module_assigned_advocate_ibfk_2` FOREIGN KEY (`module_id`) REFERENCES `module` (`id`),
            CONSTRAINT `organization_module_assigned_advocate_ibfk_3` FOREIGN KEY (`advocate_id`) REFERENCES `assignable_advocate` (`practitioner_id`)
        );
    """
    )

    op.execute(
        """
        CREATE TABLE `module_assigned_advocate` (
            `id` bigint(20) NOT NULL,
            `module_id` int(11) NOT NULL,
            `advocate_id` int(11) NOT NULL,
            PRIMARY KEY (`id`),
            UNIQUE KEY `module_assigned_advocate_uq_1` (`module_id`,`advocate_id`),
            KEY `module_assigned_advocate_ibfk_2` (`advocate_id`),
            CONSTRAINT `module_assigned_advocate_ibfk_1` FOREIGN KEY (`module_id`) REFERENCES `module` (`id`),
            CONSTRAINT `module_assigned_advocate_ibfk_2` FOREIGN KEY (`advocate_id`) REFERENCES `assignable_advocate` (`practitioner_id`)
        );
    """
    )
