from payer_accumulator.edi.models.segments import (
    ClaimData,
    ClaimLevelStatusInformation,
    ClaimStatusTrackingInformation,
    InterchangeControlHeader,
    TransactionSetHeader,
    X12Data277,
)

file_contents_277ca = """ISA*00*          *00*          *01*030240928      *ZZ*AV09311993     *241025*1500*^*00501*008055218*0*T*:~
    GS*HN*030240928*AV01101957*20241025*1500*220781*X*005010X214~
    ST*277*1001*005010X214~
    BHT*0085*08*124250095*20241025*150002*TH~
    HL*1**20*1~
    NM1*AY*2*AVAILITY LLC*****46*030240928~
    TRN*1*20241025150002316~
    DTP*050*D8*20241025~
    DTP*009*D8*20241025~
    HL*2*1*21*1~
    NM1*41*2*MAVEN CLINIC CO*****46*770465766~
    TRN*2*2RFAUCEKQY2ZFA4X9KEX~
    STC*A1:20*20241025*WQ*600~
    QTY*90*1~
    AMT*YU*600~
    HL*3*2*19*1~
    NM1*85*2*MAVEN CLINIC CO*****XX*1285263806~
    TRN*1*0~
    REF*TJ*770465766~
    QTY*QA*1~
    AMT*YU*600~
    HL*4*3*PT~
    NM1*QC*1*DOE*JANE****MI*W123456789~
    TRN*2*2RFAUCEKQY2ZFA4X9KEX~
    STC*A4:20*20241025*WQ*600~
    REF*D9*2RFAUCEKQY2ZFA4X9KEX~
    DTP*472*RD8*20240603-20240608~
    SE*26*1001~
    GE*1*220781~
    IEA*1*008055218~"""


parsed_277ca_data = X12Data277(
    interchange_control_header=InterchangeControlHeader(
        authorization_information_qualifier="00",
        authorization_information="",
        security_information_qualifier="00",
        security_information="",
        interchange_sender_id_qualifier="01",
        interchange_sender_id="030240928",
        interchange_receiver_id_qualifier="ZZ",
        interchange_receiver_id="AV09311993",
        interchange_date="241025",
        interchange_time="1500",
        repetition_separator="^",
        interchange_control_version_number="00501",
        interchange_control_number="008055218",
        acknowledgment_requested="0",
        interchange_usage_indicator="T",
        component_element_separator=":",
    ),
    transaction_set_header=TransactionSetHeader(
        transaction_set_identifier_code="277",
        transaction_set_control_number="1001",
        version_release_industry_identifier_code="005010X214",
    ),
    claims=[
        ClaimData(
            claim_status_tracking=ClaimStatusTrackingInformation(
                trace_type_code="2",
                referenced_transaction_trace_number="2RFAUCEKQY2ZFA4X9KEX",
            ),
            claim_level_status=ClaimLevelStatusInformation(
                health_care_claim_status_category_code="A1", claim_status_code="20"
            ),
        ),
        ClaimData(
            claim_status_tracking=ClaimStatusTrackingInformation(
                trace_type_code="2",
                referenced_transaction_trace_number="2RFAUCEKQY2ZFA4X9KEX",
            ),
            claim_level_status=ClaimLevelStatusInformation(
                health_care_claim_status_category_code="A4", claim_status_code="20"
            ),
        ),
    ],
)
