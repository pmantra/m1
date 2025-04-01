import enum
from typing import Optional, Tuple

from requests import JSONDecodeError, Response

from common import stats
from cost_breakdown.constants import ClaimType
from cost_breakdown.errors import (
    CreateDirectPaymentClaimErrorResponseException,
    InvalidDirectPaymentClaimCreationRequestException,
)
from direct_payment.pharmacy.errors import AutoProcessedDirectPaymentException
from direct_payment.treatment_procedure.models.treatment_procedure import (
    TreatmentProcedureType,
)
from models.failed_external_api_call import Status
from storage.connection import db
from utils.failed_external_api_call_recorder import FailedVendorAPICallRecorder
from utils.log import logger
from utils.payments import convert_cents_to_dollars
from wallet.alegeus_api import AlegeusApi, is_request_successful
from wallet.models.constants import (
    ALEGEUS_NONE_REIMBURSABLE_REIMBURSEMENT_METHOD,
    ReimbursementMethod,
    ReimbursementRequestAutoProcessing,
    ReimbursementRequestState,
)
from wallet.models.reimbursement import (
    ReimbursementAccount,
    ReimbursementClaim,
    ReimbursementRequest,
)
from wallet.models.reimbursement_wallet import ReimbursementWallet
from wallet.utils.admin_helpers import FlashMessage, FlashMessageCategory
from wallet.utils.alegeus.common import download_user_asset_to_b64_str

log = logger(__name__)

METRIC_PREFIX = "api.wallet.utils.alegeus.claims.create"

VALID_REIMBURSEMENT_REQUEST_STATES_BY_CLAIM_TYPE = {
    ClaimType.EMPLOYER: [ReimbursementRequestState.APPROVED],
    ClaimType.EMPLOYEE_DEDUCTIBLE: [ReimbursementRequestState.DENIED],
}

CLAIM_STATUS_BY_CLAIM_TYPE = {
    ClaimType.EMPLOYER: "APPROVED",
    ClaimType.EMPLOYEE_DEDUCTIBLE: "DENIED",
}

failed_api_call_recorder = FailedVendorAPICallRecorder()


class DirectPaymentClaimErrorReason(enum.Enum):
    INVALID_REQUEST = 1
    ACCOUNT_NOT_FOUND = 2
    ERROR_RESPONSE_FROM_ALEGEUS = 3


def create_direct_payment_claim_in_alegeus(
    wallet: ReimbursementWallet,
    reimbursement_request: ReimbursementRequest,
    claim_type: ClaimType,
    bypass_check_balance: bool = False,
) -> None:
    def tag_successful(
        successful: bool, reason: DirectPaymentClaimErrorReason = None
    ) -> None:
        metric_name = f"{METRIC_PREFIX}.create_direct_payment_claim"
        tags = (
            ["success:true", f"claim_type:{claim_type.name}"]
            if successful
            else [
                "success:false",
                "error_cause:failed_create_direct_payment_claim",
                f"claim_type:{claim_type.name}",
                f"reason:{reason.name if reason is not None else ''}",
            ]
        )
        stats.increment(
            metric_name=metric_name,
            pod_name=stats.PodNames.PAYMENTS_POD,
            tags=tags,
        )

    api = AlegeusApi()

    reimbursement_account = get_reimbursement_account_from_request_and_wallet(
        reimbursement_request, wallet
    )

    if reimbursement_account is None:
        tag_successful(False, DirectPaymentClaimErrorReason.ACCOUNT_NOT_FOUND)

        error_message = (
            "Can not find reimbursement account from Reimbursement "
            f"request_id:{reimbursement_request.id}, "
            f"wallet_id:{wallet.id}"
        )
        raise InvalidDirectPaymentClaimCreationRequestException(error_message)

    reimbursement_claim = ReimbursementClaim(
        reimbursement_request=reimbursement_request,
        amount=convert_cents_to_dollars(reimbursement_request.amount),
        status=CLAIM_STATUS_BY_CLAIM_TYPE.get(claim_type, ""),
    )
    reimbursement_claim.create_alegeus_claim_id()

    try:
        response = api.post_direct_payment_claim(
            wallet,
            reimbursement_request,
            reimbursement_account,
            reimbursement_claim,
            claim_type,
        )
        _validate_response(response, reimbursement_claim, bypass_check_balance)
    except Exception as e:
        tag_successful(False, DirectPaymentClaimErrorReason.ERROR_RESPONSE_FROM_ALEGEUS)

        (
            route,
            body,
        ) = AlegeusApi.build_request_route_and_body_of_post_direct_payment_claim(
            wallet,
            reimbursement_request,
            reimbursement_account,
            reimbursement_claim,
            claim_type,
        )

        called_by = "create_direct_payment_claim_in_alegeus"
        vendor_name = "Alegeus"
        failed_api_call_recorder.create_record(
            external_id=FailedVendorAPICallRecorder.generate_external_id(
                str(wallet.id), called_by, vendor_name, route
            ),
            payload=body,
            called_by=called_by,
            vendor_name=vendor_name,
            api_name=route,
            status=Status.pending,
        )
        # Abort ReimbursementClaim creation since it could not be sent to Alegeus
        _rollback_failed_claim(
            reimbursement_request=reimbursement_request,
            reimbursement_claim=reimbursement_claim,
        )
        log.info(
            "Reimbursement Claim rolled back.",
            reimbursement_request_id=str(reimbursement_request.id),
        )
        raise e

    db.session.add(reimbursement_claim)
    db.session.commit()
    tag_successful(True)


def create_claim_in_alegeus(
    wallet: ReimbursementWallet,
    reimbursement_request: ReimbursementRequest,
    messages: list,
) -> Tuple[bool, list, Optional[ReimbursementClaim]]:
    """
    Creates a Claim in Alegeus from a Reimbursement Request.
    """

    def tag_successful(successful: bool) -> None:
        metric_name = f"{METRIC_PREFIX}.create_claim"
        tags = (
            ["success:true"]
            if successful
            else ["success:false", "error_cause:failed_create_claim"]
        )
        stats.increment(
            metric_name=metric_name,
            pod_name=stats.PodNames.PAYMENTS_POD,
            tags=tags,
        )

    api = AlegeusApi()

    reimbursement_account = get_reimbursement_account_from_request_and_wallet(
        reimbursement_request, wallet
    )

    reimbursement_claim = ReimbursementClaim(
        reimbursement_request=reimbursement_request,
        amount=convert_cents_to_dollars(reimbursement_request.usd_reimbursement_amount),
    )
    reimbursement_claim.create_alegeus_claim_id()

    is_claim_created_in_alegeus, claim_key = _create_claim(
        api, wallet, reimbursement_request, reimbursement_account, reimbursement_claim
    )

    if not is_claim_created_in_alegeus:
        messages.append(
            FlashMessage(
                message=f"Could not submit Claim (ID: {reimbursement_claim.alegeus_claim_id}) "
                f"in Alegeus for Reimbursement Request ID: {reimbursement_request.id}.",
                category=FlashMessageCategory.ERROR,
            )
        )
        # Abort ReimbursementClaim creation since it could not be sent to Alegeus
        _rollback_failed_claim(
            reimbursement_request=reimbursement_request,
            reimbursement_claim=reimbursement_claim,
        )
        tag_successful(False)
        return False, messages, None

    reimbursement_claim.alegeus_claim_key = claim_key
    db.session.add(reimbursement_claim)
    db.session.commit()

    messages.append(
        FlashMessage(
            message=f"Successfully submitted Claim (ID: {reimbursement_claim.alegeus_claim_id}) "
            f"in Alegeus for Reimbursement Request ID: {reimbursement_request.id}.",
            category=FlashMessageCategory.SUCCESS,
        )
    )
    tag_successful(True)
    return True, messages, reimbursement_claim


def _validate_response(
    response: Response,
    reimbursement_claim: ReimbursementClaim,
    bypass_check_balance: bool = False,
) -> None:
    reimbursement_claim_id = reimbursement_claim.id
    try:
        if not is_request_successful(response):
            if not response.status_code:
                raise CreateDirectPaymentClaimErrorResponseException(
                    f"Response status code unavailable in the response for claim {reimbursement_claim_id}"
                )
            else:
                raise CreateDirectPaymentClaimErrorResponseException(
                    f"Unsuccessful response status code {str(response.status_code)} in the response for claim {reimbursement_claim_id}"
                )

        response_json = response.json()

        if response_json.get("ErrorCode") is None:
            raise CreateDirectPaymentClaimErrorResponseException(
                f"ErrorCode in the response is unavailable for claim {reimbursement_claim_id}",
            )

        error_code = str(response_json.get("ErrorCode"))
        if error_code != "0":
            raise CreateDirectPaymentClaimErrorResponseException(
                f"Error in the response for claim {reimbursement_claim_id}, code: {error_code}"
            )

        if response_json.get("TxnAmtOrig") is None:
            raise CreateDirectPaymentClaimErrorResponseException(
                f"TxnAmtOrig in the response is unavailable for claim {reimbursement_claim_id}",
            )

        if response_json.get("TxnApprovedAmt") is None:
            raise CreateDirectPaymentClaimErrorResponseException(
                f"TxnApprovedAmt in the response is unavailable for claim {reimbursement_claim_id}",
            )

        # Insufficient balance is okay for auto-approved rx reimbursement requests or historical spend.
        if not bypass_check_balance and response_json.get(
            "TxnAmtOrig"
        ) != response_json.get("TxnApprovedAmt"):
            raise CreateDirectPaymentClaimErrorResponseException(
                f"Insufficient balance: TxnApprovedAmt and TxnAmtOrig are not equal for claim {reimbursement_claim_id}",
            )
    except Exception as e:
        try:
            # Response should not contain PHI/PII -- see:
            # https://developer.api.wealthcare.com/api-details/overview#api=wealthcare-system-integration-rest-api-8-0&operation=SubmitManualClaim_2021_04
            log.exception(
                "Error in validating response",
                response=response.json(),
                error_type=type(e).__name__,
                error=str(e),
            )
        except JSONDecodeError:
            log.exception(
                "Error in validating response",
                response=response.content,  # log a non-json response in validating the response
                error_type=type(e).__name__,
                error=str(e),
            )
        raise e


def _rollback_failed_claim(
    reimbursement_request: ReimbursementRequest,
    reimbursement_claim: ReimbursementClaim,
) -> None:
    db.session.delete(reimbursement_claim)
    db.session.commit()
    db.session.expire(reimbursement_request)


def _create_claim(
    api: AlegeusApi,
    reimbursement_wallet: ReimbursementWallet,
    reimbursement_request: ReimbursementRequest,
    reimbursement_account: ReimbursementAccount,
    reimbursement_claim: ReimbursementClaim,
) -> Tuple[bool, Optional[int]]:
    response = api.post_claim(
        reimbursement_wallet,
        reimbursement_request,
        reimbursement_account,
        reimbursement_claim,
    )

    if not is_request_successful(response):
        return False, None

    claim_key_str = response.json()[0].get("ClaimKey")
    if not claim_key_str:
        log.error(
            f"Claim response from Alegeus [TrackingNumber: {reimbursement_claim.alegeus_claim_id}] does not have a ClaimKey."
        )
        return False, None

    try:
        claim_key = int(claim_key_str)
    except ValueError:
        log.error("ClaimKey in Alegeus response is not an integer representation")
        return False, None

    return True, claim_key


def upload_claim_attachments_to_alegeus(
    wallet: ReimbursementWallet,
    reimbursement_request: ReimbursementRequest,
    reimbursement_claim: ReimbursementClaim,
    messages: list,
    source_ids: Optional[list] = None,
) -> Tuple[bool, list]:
    """
    Upload all attachments for a Pending ReimbursementRequest / Claim to Alegeus
    """

    def tag_successful(
        successful: bool,
        reason: Optional[str] = None,
        content_type: Optional[str] = None,
        end_point: Optional[str] = None,
    ) -> None:
        metric_name = f"{METRIC_PREFIX}.upload_claim_attachments"
        if successful:
            tags = ["success:true"]
        else:
            tags = [
                "success:false",
                "error_cause:failed_upload_claim_attachments",
                f"reason:{reason}",
                f"content_type:{content_type}",
                f"end_point:{end_point}",
            ]
        stats.increment(
            metric_name=metric_name,
            pod_name=stats.PodNames.PAYMENTS_POD,
            tags=tags,
        )

    api = AlegeusApi()

    claim_key = reimbursement_claim.alegeus_claim_key

    if not claim_key:
        messages.append(
            FlashMessage(
                message=f"Claim ID: {reimbursement_claim.id} does not have an alegeus_claim_key",
                category=FlashMessageCategory.WARNING,
            )
        )
        return False, messages

    sources = reimbursement_request.sources

    for source in sources:
        if source_ids and source.id not in source_ids:
            continue
        try:
            user_asset = source.user_asset
            blob_bytes_b64_str = download_user_asset_to_b64_str(user_asset)
        except Exception as e:
            message = f"Could not download attachment for UserAsset ID: {user_asset.id} as bytes"
            messages.append(
                FlashMessage(message=message, category=FlashMessageCategory.ERROR)
            )
            log.exception(message, error=e)
            tag_successful(
                False,
                reason="error_in_getting_user_asset",
                end_point="upload_attachment_for_claim",
            )
            return False, messages
        else:
            try:
                response = api.upload_attachment_for_claim(
                    wallet, source.user_asset, claim_key, blob_bytes_b64_str
                )
                if is_request_successful(response):
                    messages.append(
                        FlashMessage(
                            message=f"Successfully uploaded attachment for Source ID: {source.id}, "
                            f"UserAsset ID: {source.user_asset.id}",
                            category=FlashMessageCategory.SUCCESS,
                        )
                    )
                    tag_successful(True)
                else:
                    messages.append(
                        FlashMessage(
                            message=f"Could not upload attachment for Source ID: {source.id}, "
                            f"UserAsset ID: {source.user_asset.id}",
                            category=FlashMessageCategory.ERROR,
                        )
                    )
                    tag_successful(
                        False,
                        reason="alegeus_api_failure",
                        content_type=response.headers["content-type"],
                        end_point="upload_attachment_for_claim",
                    )
                    return False, messages

            except Exception as e:
                message = f"Could not get attachment for UserAsset ID: {user_asset.id} as bytes"
                messages.append(
                    FlashMessage(message=message, category=FlashMessageCategory.ERROR)
                )
                log.exception(message, error=e)
                tag_successful(
                    False, reason="exception", end_point="upload_attachment_for_claim"
                )

    return True, messages


def get_reimbursement_account_from_request_and_wallet(
    reimbursement_request: ReimbursementRequest, wallet: ReimbursementWallet
) -> ReimbursementAccount:
    """
    Returns the ReimbursementAccount that is linked to this ReimbursementRequest and ReimbursementPlan, by finding
    the intersection of accounts between the ReimbursementWallet and ReimbursementPlan
    """
    category = reimbursement_request.category
    plan = category.reimbursement_plan

    return ReimbursementAccount.query.filter_by(
        wallet=wallet,
        plan=plan,
    ).one_or_none()


def create_auto_processed_claim_in_alegeus(
    wallet: ReimbursementWallet,
    reimbursement_request: ReimbursementRequest,
    reimbursement_amount: int,
    claim_type: ClaimType,
    reimbursement_mode: Optional[ReimbursementMethod],
) -> None:
    """
    Auto processed Reimbursements skip adjudication in Alegeus and are submitted directly as transactions.
    We will submit both HRA and DTR plans if applicable. DTR plans do not get reimbursed, but they get submitted, so
    we can deduct from the IRS threshold in Alegeus.  Employer responsibility claims are submitted to the associated
    plan in Alegeus for reimbursement.
    """

    def tag_successful(
        successful: bool, reason: DirectPaymentClaimErrorReason = None
    ) -> None:
        metric_name = f"{METRIC_PREFIX}.create_auto_processed_claim"
        tags = (
            ["success:true", f"claim_type:{claim_type.name}"]
            if successful
            else [
                "success:false",
                "error_cause:create_auto_processed_claim",
                f"claim_type:{claim_type.name}",
                f"reason:{reason.name if reason is not None else ''}",
            ]
        )
        stats.increment(
            metric_name=metric_name,
            pod_name=stats.PodNames.PAYMENTS_POD,
            tags=tags,
        )

    if (
        reimbursement_request.procedure_type != TreatmentProcedureType.PHARMACY.value
        or reimbursement_request.auto_processed != ReimbursementRequestAutoProcessing.RX
    ):
        tag_successful(False, DirectPaymentClaimErrorReason.INVALID_REQUEST)

        error_message = (
            "The reimbursement request is invalid for an auto approved claim."
        )
        log.error(
            error_message,
            wallet_id=str(wallet.id),
            reimbursement_request_id=str(reimbursement_request.id),
            state=reimbursement_request.state,
        )
        raise AutoProcessedDirectPaymentException(error_message)

    api = AlegeusApi()

    reimbursement_account = get_reimbursement_account_from_request_and_wallet(
        reimbursement_request, wallet
    )

    if reimbursement_account is None:
        tag_successful(False, DirectPaymentClaimErrorReason.ACCOUNT_NOT_FOUND)

        error_message = "Can not find reimbursement account from Reimbursement"
        log.error(
            "Can not find reimbursement account from Reimbursement",
            wallet_id=str(wallet.id),
            reimbursement_request_id=str(reimbursement_request.id),
        )
        raise AutoProcessedDirectPaymentException(error_message)

    reimbursement_claim = ReimbursementClaim(
        reimbursement_request=reimbursement_request,
        amount=convert_cents_to_dollars(reimbursement_amount),
        status=CLAIM_STATUS_BY_CLAIM_TYPE.get(claim_type, ""),
    )
    reimbursement_claim.create_alegeus_claim_id()
    reimbursement_method = (
        reimbursement_mode.value
        if reimbursement_mode
        else ALEGEUS_NONE_REIMBURSABLE_REIMBURSEMENT_METHOD
    )

    try:
        response = api.post_direct_payment_claim(
            wallet=wallet,
            reimbursement_request=reimbursement_request,
            reimbursement_account=reimbursement_account,
            reimbursement_claim=reimbursement_claim,
            claim_type=claim_type,
            reimbursement_mode=reimbursement_method,
            reimbursement_amount=reimbursement_amount,
        )

        _validate_response(response, reimbursement_claim, bypass_check_balance=True)
    except Exception as e:
        tag_successful(False, DirectPaymentClaimErrorReason.ERROR_RESPONSE_FROM_ALEGEUS)
        log.exception(
            "Failed to submit an auto approved claim to Alegeus.",
            error=str(e),
            wallet_id=str(wallet.id),
            reimbursement_request_id=str(reimbursement_request.id),
        )
        # Abort ReimbursementClaim creation since it could not be sent to Alegeus
        _rollback_failed_claim(
            reimbursement_request=reimbursement_request,
            reimbursement_claim=reimbursement_claim,
        )
        log.info(
            "Reimbursement Claim rolled back.",
            reimbursement_request_id=str(reimbursement_request.id),
            wallet_id=str(wallet.id),
        )
        raise e

    db.session.add(reimbursement_claim)
    db.session.commit()
    tag_successful(True)
