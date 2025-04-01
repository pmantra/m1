import pytest
import requests

from wallet.models.reimbursement_wallet import ReimbursementWallet


@pytest.fixture()
def get_employee_demographic_response():
    def _get_employee_demographic_response(wallet: ReimbursementWallet):
        return {
            "AddressLine1": "160 Varick St",
            "AddressLine2": "",
            "BirthDate": "",
            "City": "New York",
            "Country": "US",
            "DriverLicenceNumber": "",
            "Email": "",
            "EmployeeSSN": "",
            "FirstName": wallet.member.first_name,
            "Gender": 0,
            "LastName": wallet.member.last_name,
            "LastUpdated": "/Date(1652200771320-0500)/",
            "MaritalStatus": 0,
            "MiddleInitial": "",
            "MiscData": {
                "BaseSalary": 0,
                "CitizenStatusCode": -1,
                "CitizenshipCountry": "",
                "EmployerCity": "",
                "EmployerName": "",
                "EmployerState": "",
                "EmployermentStatus": -1,
                "JobTitle": "",
            },
            "MotherMaidenName": "",
            "ParticipantId": wallet.alegeus_id,
            "Phone": "",
            "ShippingAddressCity": "",
            "ShippingAddressCountry": "",
            "ShippingAddressLine1": "",
            "ShippingAddressLine2": "",
            "ShippingAddressState": "",
            "ShippingAddressZip": "",
            "State": "NY",
            "Zip": "10013",
        }

    return _get_employee_demographic_response


@pytest.fixture()
def get_employee_dependents_list_response():
    def _get_employee_dependents_list_response(wallet: ReimbursementWallet):
        response = []
        for dependent in wallet.authorized_users:
            response.append(
                {
                    "DepId": dependent.alegeus_dependent_id,
                    "DependentStatus": 2,
                    "EmpeFullName": f"{wallet.member.first_name} {wallet.member.last_name}",
                    "EmpeId": "456",
                    "EmprId": "123",
                    "FirstName": dependent.first_name,
                    "LastName": dependent.last_name,
                    "MiddleInitial": "",
                    "NamePrefix": "",
                    "Relationship": 0,
                    "TpaId": "None",
                }
            )
        return response

    return _get_employee_dependents_list_response


@pytest.fixture()
def get_employee_accounts_list_response_hra():
    return [
        {
            "AccountType": "HRA",
            "AcctStatusCde": 1,
            "AcctTypeClassDescription": "HRA",
            "AvailBalance": 5000.0000,
            "Balance": 5000.0000,
            "ExternalFunded": None,
            "FlexAccountKey": 17,
            "HSABalance": 5000.0000,
            "HraAcct": False,
            "IsWCABank": None,
            "Payments": 0.0000,
            "PlanEndDate": "21991231",
            "PlanId": "FAMILYFUND",
            "PlanOptions2": 2,
            "PlanStartDate": "20210101",
            "PlanYear": 1,
        }
    ]


@pytest.fixture()
def get_employee_accounts_list_response_hdhp_family():
    return [
        {
            "AccountType": "DTR",
            "AcctStatusCde": 1,
            "AcctTypeClassDescription": "Deductible",
            "AvailBalance": 2800.0000,
            "Balance": 2800.0000,
            "ExternalFunded": None,
            "FlexAccountKey": 17,
            "HSABalance": 2800.0000,
            "HraAcct": True,
            "IsWCABank": None,
            "Payments": 0.0000,
            "PlanEndDate": "21991231",
            "PlanId": "HDHP",
            "PlanOptions2": 2,
            "PlanStartDate": "20210101",
            "PlanYear": 1,
        }
    ]


@pytest.fixture()
def get_employee_accounts_list_response_hdhp_family_with_two_plans():
    return [
        {
            "AccountType": "DTR",
            "AcctStatusCde": 1,
            "AcctTypeClassDescription": "Deductible",
            "AvailBalance": 2800.0000,
            "Balance": 2800.0000,
            "ExternalFunded": None,
            "FlexAccountKey": 17,
            "HSABalance": 2800.0000,
            "HraAcct": True,
            "IsWCABank": None,
            "Payments": 0.0000,
            "PlanEndDate": "21991231",
            "PlanId": "HDHP",
            "PlanOptions2": 2,
            "PlanStartDate": "20210101",
            "PlanYear": 1,
        },
        {
            "AccountType": "DTR",
            "AcctStatusCde": 1,
            "AcctTypeClassDescription": "Deductible",
            "AvailBalance": 2800.0000,
            "Balance": 2800.0000,
            "ExternalFunded": None,
            "FlexAccountKey": 18,
            "HSABalance": 2800.0000,
            "HraAcct": True,
            "IsWCABank": None,
            "Payments": 0.0000,
            "PlanEndDate": "22001231",
            "PlanId": "HDHP2",
            "PlanOptions2": 2,
            "PlanStartDate": "20230103",
            "PlanYear": 1,
        },
    ]


@pytest.fixture()
def post_claim_response():
    def _post_claim_response(claim_key):
        response = [
            {
                "__type": "ManualClaim:http://schema.wealthcareadmin.com/payload/mobile/2013/01",
                "AccountKey": -1,
                "AcctTypeCde": "",
                "AcctTypeDesc": None,
                "CardHolderDisplay": True,
                "Claimant": None,
                "EmployerId": "MVNEF475482",
                "ExpenseKey": 0,
                "FileKey": -1,
                "FlexAcctKey": 17,
                "HasReceipt": False,
                "InsertDate": "/Date(-2208967200000-0600)/",
                "InsertUserIdKey": -1,
                "PlanEndDate": None,
                "PlanStartDate": None,
                "ProviderDesc": "",
                "ProviderId": "",
                "ReceiptExpired": None,
                "ReceiptsInfo": None,
                "ServiceEndDate": "/Date(1627448400000-0500)/",
                "ServiceStartDate": "/Date(1627448400000-0500)/",
                "Status": None,
                "TpaId": "T01676",
                "TransactionDate": "/Date(1652817732677-0500)/",
                "TxnAmt": 100,
                "TxnAmtDenied": 0,
                "TxnAmtOrig": 0,
                "TxnAmtPending": None,
                "TxnAmtRefund": 0,
                "TxnCde": -1,
                "TxnMsg": "",
                "TxnOptions": 6450839552,
                "TxnOriginCde": 54,
                "Type": None,
                "UpdateDte": "/Date(-2208967200000-0600)/",
                "UpdateUserIdKey": -1,
                "ClaimDesc": "",
                "ClaimKey": claim_key,
                "ClaimStatus": 1,
                "ClaimStatusMsg": "",
                "Notes": "",
                "ReimbModeCde": 0,
                "ScCde": "",
                "ScCdeDesc": None,
                "TrackingNum": "String content",
            }
        ]
        return response

    return _post_claim_response


@pytest.fixture()
def get_employee_activity_response():
    def _get_employee_activity_response(
        tracking_number: str, status="APPROVED", account_type_code="HRA"
    ):
        response = [
            {
                "AccountsPaidAmount": 0,
                "Actions": 0,
                "AcctTypeCode": account_type_code,
                "AllowedAmount": 0,
                "Amount": 100.0000,
                "BilledAmount": 0,
                "CardTransactionDetails": None,
                "CheckNumber": None,
                "ClaimAdjudicationDetails": None,
                "ClaimId": "-1",
                "ClaimKey": 88,
                "Claimant": "",
                "CoveredAmount": 0,
                "Date": "/Date(1652817732600-0500)/",
                "DeductibleAmount": 0,
                "DenialReason": None,
                "Description": "",
                "DisplayStatus": "Pending",
                "ExcludedReason": None,
                "ExpenseKey": 0,
                "ExpensesDetails": None,
                "HasReceipts": True,
                "OffsetAmount": 0,
                "OutOfPocketAmount": 0,
                "PaidToProvider": False,
                "PatientAccountNumber": "",
                "PatientName": "",
                "PendedComment": None,
                "PendedReason": None,
                "Provider": None,
                "ProviderId": None,
                "ProviderKey": -1,
                "ReimbursementDate": None,
                "ReimbursementDetails": None,
                "ReimbursementMethod": None,
                "RemainingResponsibilityAmount": 0,
                "RenderingProvider": None,
                "ResponsibilityAmount": 100.0000,
                "SeqNumber": 0,
                "ServiceCategoryCode": None,
                "ServiceCategoryName": None,
                "ServiceEndDate": "/Date(1627448400000-0500)/",
                "ServiceStartDate": "/Date(1627448400000-0500)/",
                "SettlementDate": None,
                "Status": status,
                "StatusCode": 11,
                "StatusWithAmount": "Submitted – Under Review",
                "TrackingNumber": tracking_number,
                "TransactionKey": None,
                "Type": "MEMBER CLAIM",
                "TypeCode": 7,
            }
        ]
        return response

    return _get_employee_activity_response


@pytest.fixture
def mocked_auto_processed_claim_response():
    def _mocked_response(status_code, reimbursement_mode, amount, error_code="0"):
        mock_response = requests.Response()
        mock_response.status_code = status_code
        payload = {
            "ReimbursementMode": reimbursement_mode,
            "PayProviderFlag": "No",
            "TrackingNumber": "TESTTRACKING",
            "TxnResponseList": [
                {"AcctTypeCde": "HRA", "DisbBal": 0.00, "TxnAmt": amount}
            ],
            "TxnAmtOrig": amount,
            "TxnApprovedAmt": amount,
            "ErrorCode": error_code,
        }
        mock_response.json = lambda: payload

        return mock_response

    return _mocked_response
