from assessments.resources.hdc_webhook import HDCWebhookResource
from care_plans.activities_completed.resource import CarePlanActivitiesCompletedResource
from health.resources.care_coaching_eligibility import CareCoachingEligibilityResource
from health.resources.health_profile import (
    HealthProfileResource,
    PregnancyAndRelatedConditionsResource,
    UserPregnancyAndRelatedConditionsResource,
)
from health.resources.hps_backfill_resource import HealthProfileBackfillResource
from health.resources.life_stages import LifeStagesResource
from health.resources.member_risk_resource import MemberRiskResource
from search.resources.content import ContentSingleResource
from tracks.resources.member_tracks import (
    ActiveTracksResource,
    InactiveTracksResource,
    ScheduledTracksResource,
    TrackResource,
    TracksOnboardingAssessmentResource,
)
from user_locale.resources.user_locale import UserLocaleResource
from views.address import AddressResource
from views.advertising import MATPostbackResource
from views.agreements import (
    AgreementResource,
    AgreementsResource,
    PendingAgreementsResource,
)
from views.assessments import (
    AssessmentResource,
    AssessmentsResource,
    UserAssessmentAnswersResource,
)
from views.assets import (
    AssetDownloadResource,
    AssetDownloadUrlResource,
    AssetResource,
    AssetsResource,
    AssetThumbnailResource,
    AssetUploadResource,
)
from views.content import (
    ActivityDashboardMetadataResource,
    ActivityDashboardMetadataResourceBatch,
    DismissalsResource,
    EnterprisePrivateContentResource,
    EnterprisePublicContentResource,
    ProgramTransitionsResource,
    UserCurrentDashboardView,
    UserCurrentPromptView,
)
from views.credits import UserCreditsResource
from views.current_user import CurrentUserResource
from views.dashboard_metadata import (
    DashboardMetadataAssessmentResource,
    DashboardMetadataPractitionerResource,
    DashboardMetadataResource,
    ExpiredTrackDashboardMetadataResource,
    MarketplaceDashboardMetadataResource,
)
from views.enterprise import (
    CanInvitePartnerResource,
    CensusVerificationEndpoint,
    ClaimFilelessInviteResource,
    CreateEligibilityTestMemberRecordsEndpoint,
    CreateFilelessInviteResource,
    CreateInviteResource,
    GetInviteResource,
    OrganizationEligibilityResource,
    OrganizationSearchAutocompleteResource,
    OrganizationsEligibilityResource,
    ReportVerificationFailureEndpoint,
    UnclaimedInviteResource,
    UserOrganizationInBoundPhoneNumberResource,
    UserOrganizationSetupResource,
)
from views.features import FeaturesResource
from views.fhir import FHIRPatientHealthResource
from views.forum import (
    CategoryGroupsResource,
    PostBookmarksResource,
    PostResource,
    PostsResource,
    UserBookmarksResource,
)
from views.images import ImageAssetURLResource, ImageResource, ImagesResource
from views.internal import (
    BrazeAttachmentResource,
    BrazeConnectedEventPropertiesResource,
    EmailBizLeadsEndpoint,
    IosNonDeeplinkUrlsResource,
    MetadataResource,
    PractitionerServiceAgreementResource,
    VendorMetadataResource,
    VerticalGroupingsResource,
)
from views.launchdarkly import LaunchDarklyContextResource
from views.library import (
    CourseResource,
    CoursesResource,
    LibraryResource,
    OnDemandClassesResource,
)
from views.medications import MedicationsResource
from views.patient_profile import (
    NonAppointmentPharmacySearchResource,
    PatientProfileResource,
)
from views.payments import (
    GiftingResource,
    RecipientInformationResource,
    UserBankAccountsResource,
    UserPaymentMethodResource,
    UserPaymentMethodsResource,
)
from views.prescription import (
    PatientDetailsURLResource,
    PharmacySearchResource,
    RefillTransmissionErrorCountsResource,
)
from views.products import PractitionerProductsResource
from views.profiles import (
    CareTeamResource,
    CareTeamsResource,
    CategoriesResource,
    CurrentUserMemberProfileResource,
    CurrentUserPractitionerProfileResource,
    MemberProfileResource,
    MeResource,
    MyPatientsResource,
    PractitionerNotesResource,
    PractitionerProfileResource,
    PractitionersResource,
    UserFilesResource,
    UserOnboardingStateResource,
    VerticalsResource,
)
from views.questionnaires import (
    QuestionnairesResource,
    RecordedAnswerSetResource,
    RecordedAnswerSetsResource,
)
from views.referrals import (
    ReferralCodeInfoResource,
    ReferralCodesResource,
    ReferralCodeUseResource,
)
from views.resources import ResourcesResource
from views.search import SearchClickResource, SearchResource
from views.settings import UserDevicesResource
from views.tags import TagsResource
from views.tracks import (
    ScheduledTrackCancellationResource,
    TracksCancelTransitionResource,
    TracksFinishTransitionResource,
    TracksIntroAppointmentEligibilityResource,
    TracksRenewalResource,
    TracksResource,
    TracksStartTransitionResource,
)
from views.virtual_events import (
    VirtualEventResource,
    VirtualEventsResource,
    VirtualEventUserRegistrationResource,
)


def add_routes(api):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    api.add_resource(MetadataResource, "/v1/_/metadata")
    api.add_resource(VendorMetadataResource, "/v1/_/metadata/vendor")

    api.add_resource(
        PractitionerServiceAgreementResource,
        "/v1/_/agreements/subscription/<int:version_number>",
    )
    api.add_resource(IosNonDeeplinkUrlsResource, "/v1/_/ios_non_deeplink_urls")

    api.add_resource(AgreementsResource, "/v1/_/agreements")
    api.add_resource(AgreementResource, "/v1/_/agreements/<string:agreement_name>")
    api.add_resource(VerticalGroupingsResource, "/v1/_/vertical_groupings")
    api.add_resource(EmailBizLeadsEndpoint, "/v1/_/mail_biz_lead")
    api.add_resource(CensusVerificationEndpoint, "/v1/_/manual_census_verification")
    api.add_resource(
        ReportVerificationFailureEndpoint,
        "/v1/_/report_eligibility_verification_failure",
    )
    api.add_resource(GiftingResource, "/v1/unauthenticated/gifting")
    api.add_resource(CategoriesResource, "/v1/categories")
    api.add_resource(CategoryGroupsResource, "/v1/forums/categories")

    api.add_resource(MeResource, "/v1/me")
    api.add_resource(LaunchDarklyContextResource, "/v1/launchdarkly_context")
    api.add_resource(
        UserOnboardingStateResource, "/v1/users/<int:user_id>/onboarding_state"
    )
    api.add_resource(UserDevicesResource, "/v1/users/<int:user_id>/devices")
    api.add_resource(UserCreditsResource, "/v1/users/<int:user_id>/credits")
    api.add_resource(HealthProfileResource, "/v1/users/<int:user_id>/health_profile")
    api.add_resource(
        UserPregnancyAndRelatedConditionsResource,
        "/v1/users/<int:user_id>/pregnancy_and_related_conditions",
    )
    api.add_resource(
        PregnancyAndRelatedConditionsResource,
        "/v1/pregnancy_and_related_conditions/<string:pregnancy_id>",
    )
    api.add_resource(
        FHIRPatientHealthResource, "/v1/users/<int:user_id>/patient_health_record"
    )
    api.add_resource(LifeStagesResource, "/v1/users/life_stages")
    api.add_resource(CareTeamsResource, "/v1/users/<int:user_id>/care_team")
    api.add_resource(
        CareTeamResource, "/v1/users/<int:user_id>/care_team/<int:practitioner_id>"
    )
    api.add_resource(MyPatientsResource, "/v1/users/<int:user_id>/my_patients")
    api.add_resource(UserBookmarksResource, "/v1/me/bookmarks")
    api.add_resource(
        UserOrganizationSetupResource, "/v1/users/<int:user_id>/organizations"
    )
    api.add_resource(
        ProgramTransitionsResource, "/v1/users/<int:user_id>/transitions/programs"
    )
    api.add_resource(DismissalsResource, "/v1/users/<int:user_id>/dismissals")
    api.add_resource(UserLocaleResource, "/v1/users/<int:user_id>/locale")

    api.add_resource(FeaturesResource, "/v1/features")

    api.add_resource(
        CreateEligibilityTestMemberRecordsEndpoint,
        "/v1/create_e9y_test_members_for_organization",
    )

    api.add_resource(CreateInviteResource, "/v1/invite")
    api.add_resource(GetInviteResource, "/v1/invite/<string:invite_id>")
    api.add_resource(UnclaimedInviteResource, "/v1/invite/unclaimed")

    api.add_resource(CreateFilelessInviteResource, "/v1/fileless_invite")
    api.add_resource(ClaimFilelessInviteResource, "/v1/fileless_invite/claim")

    api.add_resource(OrganizationSearchAutocompleteResource, "/v1/organizations/search")

    api.add_resource(
        OrganizationEligibilityResource, "/v1/organizations/<int:organization_id>"
    )

    api.add_resource(
        UserOrganizationInBoundPhoneNumberResource,
        "/v1/organization/<int:organization_id>/inbound_phone_number",
    )

    api.add_resource(OrganizationsEligibilityResource, "/v1/organizations")

    api.add_resource(VerticalsResource, "/v1/verticals")

    api.add_resource(CurrentUserResource, "/v1/users/me")

    api.add_resource(
        PractitionerProfileResource, "/v1/users/<int:user_id>/profiles/practitioner"
    )
    api.add_resource(MemberProfileResource, "/v1/users/<int:user_id>/profiles/member")
    api.add_resource(
        CurrentUserPractitionerProfileResource, "/v1/users/profiles/practitioner"
    )
    api.add_resource(CurrentUserMemberProfileResource, "/v1/users/profiles/member")

    api.add_resource(
        UserPaymentMethodsResource, "/v1/users/<int:user_id>/payment_methods"
    )
    api.add_resource(
        UserPaymentMethodResource, "/v1/users/<int:user_id>/payment_methods/<card_id>"
    )
    api.add_resource(UserBankAccountsResource, "/v1/users/<int:user_id>/bank_accounts")
    api.add_resource(
        RecipientInformationResource, "/v1/users/<int:user_id>/recipient_information"
    )

    api.add_resource(AddressResource, "/v1/users/<int:user_id>/address")

    api.add_resource(PractitionerNotesResource, "/v1/users/<int:user_id>/notes")

    api.add_resource(PendingAgreementsResource, "/v1/agreements/pending")

    api.add_resource(PractitionersResource, "/v1/practitioners")

    api.add_resource(PractitionerProductsResource, "/v1/products")

    api.add_resource(PostsResource, "/v1/posts")
    api.add_resource(PostResource, "/v1/posts/<int:post_id>")
    api.add_resource(PostBookmarksResource, "/v1/posts/<int:post_id>/bookmarks")

    api.add_resource(ReferralCodesResource, "/v1/referral_codes")
    api.add_resource(ReferralCodeUseResource, "/v1/referral_code_uses")
    api.add_resource(ReferralCodeInfoResource, "/v1/referral_code_info")

    api.add_resource(ImagesResource, "/v1/images")
    api.add_resource(ImageResource, "/v1/images/<int:image_id>")
    api.add_resource(ImageAssetURLResource, "/v1/images/<int:image_id>/<size>")

    api.add_resource(
        PatientDetailsURLResource,
        "/v1/prescriptions/patient_details/<int:appointment_id>",
    )
    api.add_resource(
        RefillTransmissionErrorCountsResource,
        "/v1/prescriptions/errors/<int:practitioner_id>",
    )
    api.add_resource(
        PharmacySearchResource, "/v1/prescriptions/pharmacy_search/<int:appointment_id>"
    )

    api.add_resource(MATPostbackResource, "/v1/vendor/mat/webhooks")

    api.add_resource(
        BrazeConnectedEventPropertiesResource,
        "/v1/vendor/braze/connected_event_properties/<string:connected_event_token>",
    )

    api.add_resource(AssessmentsResource, "/v1/assessments")
    api.add_resource(AssessmentResource, "/v1/assessments/<int:assessment_id>")
    api.add_resource(HDCWebhookResource, "/v1/webhook/health_data_collection")

    api.add_resource(UserFilesResource, "/v1/users/<int:user_id>/files")

    api.add_resource(AssetsResource, "/v1/assets")
    api.add_resource(AssetResource, "/v1/assets/<int:asset_id>")
    api.add_resource(AssetUploadResource, "/v1/assets/<int:asset_id>/upload")
    api.add_resource(AssetDownloadResource, "/v1/assets/<int:asset_id>/download")
    api.add_resource(AssetDownloadUrlResource, "/v1/assets/<int:asset_id>/url")
    api.add_resource(AssetThumbnailResource, "/v1/assets/<int:asset_id>/thumbnail")

    api.add_resource(
        EnterprisePublicContentResource, "/v1/content/resources/public/<url_slug>"
    )
    api.add_resource(
        EnterprisePrivateContentResource, "/v1/content/resources/private/<content_id>"
    )
    api.add_resource(
        ActivityDashboardMetadataResource,
        "/v1/content/resources/metadata/<resource_id>",
    )
    api.add_resource(
        ActivityDashboardMetadataResourceBatch,
        "/v1/content/resources/metadata",
    )
    api.add_resource(UserCurrentDashboardView, "/v1/users/<int:user_id>/dashboard")
    api.add_resource(UserCurrentPromptView, "/v1/users/<int:user_id>/prompt")
    api.add_resource(TagsResource, "/v1/tags")
    api.add_resource(ResourcesResource, "/v1/resources")
    api.add_resource(BrazeAttachmentResource, "/v1/braze_attachment")

    api.add_resource(
        ExpiredTrackDashboardMetadataResource,
        "/v1/dashboard-metadata/expired-track/<int:track_id>",
    )
    api.add_resource(
        DashboardMetadataResource,
        "/v1/dashboard-metadata/track/<int:track_id>",
    )
    api.add_resource(
        DashboardMetadataPractitionerResource, "/v1/dashboard-metadata/practitioner"
    )
    api.add_resource(
        DashboardMetadataAssessmentResource, "/v1/dashboard-metadata/assessment"
    )
    api.add_resource(
        MarketplaceDashboardMetadataResource, "/v1/dashboard-metadata/marketplace"
    )

    api.add_resource(PatientProfileResource, "/v1/users/<int:user_id>/patient_profile")
    api.add_resource(NonAppointmentPharmacySearchResource, "/v1/pharmacy_search")
    api.add_resource(
        UserAssessmentAnswersResource, "/v1/users/<int:user_id>/assessment_answers"
    )
    api.add_resource(QuestionnairesResource, "/v1/questionnaires")
    api.add_resource(
        RecordedAnswerSetsResource, "/v1/users/<int:user_id>/recorded_answer_sets"
    )
    api.add_resource(
        RecordedAnswerSetResource,
        "/v1/users/<int:user_id>/recorded_answer_sets/<int:id>",
    )
    api.add_resource(MedicationsResource, "/v1/medications")

    api.add_resource(LibraryResource, "/v1/library/<int:track_id>")

    api.add_resource(VirtualEventsResource, "/v1/library/virtual_events/<int:track_id>")

    api.add_resource(
        OnDemandClassesResource, "/v1/library/on_demand_classes/<int:track_id>"
    )
    api.add_resource(CourseResource, "/v1/library/courses/<slug>")
    api.add_resource(CoursesResource, "/v1/library/courses")

    api.add_resource(VirtualEventResource, "/v1/virtual_events/<int:event_id>")
    api.add_resource(
        VirtualEventUserRegistrationResource,
        "/v1/virtual_events/<int:virtual_event_id>/user_registration",
    )

    api.add_resource(SearchResource, "/v1/search/<resource_type>")
    api.add_resource(SearchClickResource, "/v1/search/<resource_type>/click")

    api.add_resource(
        CanInvitePartnerResource, "/v1/users/<int:user_id>/invite_partner_enabled"
    )

    # Tracks
    api.add_resource(TracksResource, "/v1/tracks")
    api.add_resource(
        TrackResource, "/v1/-/tracks/<int:track_id>"
    )  # /-/ makes it internal-only
    api.add_resource(ActiveTracksResource, "/v1/tracks/active")
    api.add_resource(InactiveTracksResource, "/v1/tracks/inactive")
    api.add_resource(ScheduledTracksResource, "/v1/tracks/scheduled")
    api.add_resource(
        TracksOnboardingAssessmentResource,
        "/v1/tracks/<int:track_id>/onboarding_assessment",
    )
    api.add_resource(
        TracksStartTransitionResource, "/v1/tracks/<int:track_id>/start-transition"
    )
    api.add_resource(
        TracksFinishTransitionResource, "/v1/tracks/<int:track_id>/finish-transition"
    )
    api.add_resource(
        TracksCancelTransitionResource, "/v1/tracks/<int:track_id>/cancel-transition"
    )

    api.add_resource(TracksRenewalResource, "/v1/tracks/<int:track_id>/renewal")
    api.add_resource(
        ScheduledTrackCancellationResource, "/v1/tracks/<int:track_id>/scheduled"
    )
    api.add_resource(
        TracksIntroAppointmentEligibilityResource,
        "/v1/tracks/intro_appointment_eligibility",
    )
    api.add_resource(CareCoachingEligibilityResource, "/v1/care_coaching_eligibility")

    # Internal routes contain dash prefix
    api.add_resource(
        CarePlanActivitiesCompletedResource, "/v1/-/care_plans/activities_completed"
    )
    api.add_resource(HealthProfileBackfillResource, "/v1/-/health_profile_backfill")

    api.add_resource(MemberRiskResource, "/v1/risk-flags/member/<int:user_id>")

    api.add_resource(
        ContentSingleResource,
        "/v1/-/search/content/<string:resource_slug>",
        endpoint="content_single_resource_internal",
    )

    return api
