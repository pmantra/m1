from direct_payment.billing.http.bill import BillEntityResource
from direct_payment.billing.http.webhook_payments_gateway import (
    BillPaymentGatewayEventConsumptionResource,
)
from direct_payment.clinic.resources.aggregate_procedures import (
    FertilityClinicAggregateProceduresResource,
)
from direct_payment.clinic.resources.clinic_auth import ClinicCheckAccessResource
from direct_payment.clinic.resources.fertility_clinic_user import (
    FertilityClinicUserMeResource,
)
from direct_payment.clinic.resources.fertility_clinics import FertilityClinicsResource
from direct_payment.clinic.resources.patient import MemberLookupResource
from direct_payment.clinic.resources.procedures import FertilityClinicProceduresResource
from direct_payment.consent.resources.billing_consent import BillingConsentResource
from direct_payment.help.resources.content import (
    BenefitsExperienceHelpArticleResource,
    BenefitsExperienceHelpArticleTopicsResource,
    FertilityClinicPortalHelpArticleResource,
    FertilityClinicPortalHelpArticleTopicsResource,
    MMBGeneralArticleResource,
)
from direct_payment.notification.http.webhook_payments_gateway import (
    NotificationServicePaymentGatewayEventConsumptionResource,
)
from direct_payment.payments.http.estimates_detail import EstimateDetailResource
from direct_payment.payments.http.estimates_details_for_wallet import (
    EstimateDetailsForWalletResource,
)
from direct_payment.payments.http.payments_detail import PaymentDetailResource
from direct_payment.payments.http.payments_history import PaymentHistoryResource
from direct_payment.treatment_procedure.resources.treatment_procedure import (
    TreatmentProcedureMemberResource,
    TreatmentProcedureResource,
    TreatmentProceduresResource,
)
from direct_payment.treatment_procedure.resources.treatment_procedure_questionnaire import (
    TreatmentProcedureQuestionnairesResource,
)


def add_routes(api):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    # Fertility Clinics
    api.add_resource(
        FertilityClinicsResource,
        "/v1/direct_payment/clinic/fertility_clinics/<int:fertility_clinic_id>",
    )
    api.add_resource(MemberLookupResource, "/v1/direct_payment/clinic/member-lookup")
    api.add_resource(
        FertilityClinicProceduresResource,
        "/v1/direct_payment/clinic/fertility_clinics/<int:fertility_clinic_id>/procedures",
    )
    api.add_resource(
        ClinicCheckAccessResource, "/v1/direct_payment/clinic/check_access"
    )
    api.add_resource(FertilityClinicUserMeResource, "/v1/direct_payment/clinic/me")

    # Billing & Payments
    api.add_resource(
        BillingConsentResource,
        "/v1/direct_payment/billing_consent/reimbursement_wallet/<int:wallet_id>",
    )
    api.add_resource(
        BillEntityResource, "/v1/direct_payment/billing/bill/<string:bill_uuid>"
    )
    api.add_resource(
        BillPaymentGatewayEventConsumptionResource,
        "/v1/direct_payment/billing/ingest_payment_gateway_event",
    )
    api.add_resource(
        NotificationServicePaymentGatewayEventConsumptionResource,
        "/v1/direct_payment/notification/ingest_payment_gateway_event",
    )
    api.add_resource(
        PaymentDetailResource,
        "/v1/direct_payment/payments/bill/<string:bill_uuid>/detail",
    )
    api.add_resource(
        PaymentHistoryResource,
        "/v1/direct_payment/payments/reimbursement_wallet/<int:wallet_id>",
    )
    api.add_resource(
        EstimateDetailResource,
        "/v1/direct_payment/payments/estimate/<string:bill_uuid>/detail",
    )
    api.add_resource(
        EstimateDetailsForWalletResource,
        "/v1/direct_payment/payments/reimbursement_wallet/estimates/<int:wallet_id>",
    )

    # Treatment Procedures
    api.add_resource(
        TreatmentProcedureResource,
        "/v1/direct_payment/treatment_procedure/<int:treatment_procedure_id>",
    )
    api.add_resource(
        TreatmentProceduresResource,
        "/v1/direct_payment/treatment_procedure",
    )
    api.add_resource(
        TreatmentProcedureMemberResource,
        "/v1/direct_payment/treatment_procedure/member/<int:member_id>",
    )

    # Treatment Procedure Questionnaires
    api.add_resource(
        TreatmentProcedureQuestionnairesResource,
        "/v1/direct_payment/treatment_procedure_questionnaires",
    )

    # MMB Contentful
    api.add_resource(
        BenefitsExperienceHelpArticleTopicsResource,
        "/v1/direct_payment/benefits_experience_help/articles",
    )

    api.add_resource(
        BenefitsExperienceHelpArticleResource,
        "/v1/direct_payment/benefits_experience_help/articles/<string:url_slug>",
    )

    api.add_resource(
        FertilityClinicPortalHelpArticleTopicsResource,
        "/v1/direct_payment/fertility_clinic_portal_help/articles",
    )

    api.add_resource(
        FertilityClinicPortalHelpArticleResource,
        "/v1/direct_payment/fertility_clinic_portal_help/articles/<string:url_slug>",
    )
    api.add_resource(
        MMBGeneralArticleResource,
        "/v1/direct_payment/general/articles/<string:url_slug>",
    )

    # Aggregate Procedures
    api.add_resource(
        FertilityClinicAggregateProceduresResource,
        "/v1/direct_payment/clinic/treatment_procedures",
    )
    return api
