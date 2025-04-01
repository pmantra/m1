"""BEX-2158_1_of_n_reimbursement_organization_settings_invoicing

Revision ID: d1e0256e1d90
Revises: 2ae48a561d61
Create Date: 2024-02-13 15:16:34.794913+00:00

"""
from storage.connection import db


# revision identifiers, used by Alembic.
revision = "d1e0256e1d90"
down_revision = "2ae48a561d61"
branch_labels = None
depends_on = None


def upgrade():
    query = """
    create table `reimbursement_organization_settings_invoicing`
    (
        id                           bigint auto_increment 
        comment 'Internal unique ID',
        uuid                         char(36) collate utf8mb4_unicode_ci      not null 
        comment 'External unique id ',
        reimbursement_organization_settings_id bigint                         not null 
        comment 'Foreign key to reimbursement_org_setting',
        created_by_user_id           bigint                                   not null 
        comment 'user_id from the user_table who created the record',
        updated_by_user_id            bigint                                  not null
        comment 'user_id from the user_table who last updated the record',
        created_at                   datetime default CURRENT_TIMESTAMP       not null 
        comment 'The time at which this record was created.',
        updated_at                   datetime default CURRENT_TIMESTAMP       not null on update CURRENT_TIMESTAMP 
        comment 'The time at which this record was updated.',
        invoicing_active_at          datetime                                 null 
        comment 'The date at which the client activated invoice based billing. This field will also serve as the flag to 
        determine whether the client uses invoice based billing. If populated, they do. If not, they do not. Since 
        invoicing is live from this date on, if set to a date in the past invoicing will go live immediately.  If this 
        value is set, invoice_cadence and  invoice_billing_offset_days should not be null. ',
        invoicing_email_active_at    datetime                                 null 
        comment 'The date at which the delivery of invoices to clients gets turned on. Prior to this date, every step of 
        the process excluding email will be performed.  If populated invoice_email_address should not be null. ',
        invoice_cadence              varchar(13)                              null 
        comment 'A string specifying the invoice generation cadence. This will support days of week or days of month 
        cadences in a comma delimited string.  Stored in standard cron format - the restrictions to only allow specified 
        cadences and the user-friendly representation of the cadences will be done by the service layer. ',
        invoice_billing_offset_days  tinyint(3) unsigned                      null
        comment 'Bills will be processed this many days after the invoice is generated',
        invoice_email_addresses      varchar(1024) collate utf8mb4_unicode_ci null 
        comment 'The email addresses to which the invoice must be delivered. Comma delimited list.',        
        primary key (id),
        key `ix_org_sett_inv_uuid` (`uuid`),
        key `ix_invoicing_active_at` (`invoicing_active_at`),
        key `ix_invoicing_email_active_at` (`invoicing_email_active_at`),
        key `ix_invoice_cadence` (`invoice_cadence`),
        CONSTRAINT `reimbursement_organization_settings_invoicing_ibfk_1` 
        FOREIGN KEY (`reimbursement_organization_settings_id`) 
        REFERENCES `reimbursement_organization_settings` (`id`) 
        ON DELETE CASCADE
    );
    """
    db.session.execute(query)
    db.session.commit()


def downgrade():
    query = "DROP TABLE IF EXISTS `reimbursement_organization_settings_invoicing`;"
    db.session.execute(query)
    db.session.commit()
