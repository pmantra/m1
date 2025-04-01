from payer_accumulator.edi.models.segments import (
    ClaimData,
    ClaimLevelStatusInformation,
    ClaimStatusTrackingInformation,
    InterchangeControlHeader,
    TransactionSetHeader,
    X12Data277,
)

file_contents_277 = """ISA*00*          *00*          *01*030240928      *ZZ*AV09311993     *240927*1300*^*00501*007205100*0*T*:~
        GS*HN*030240928*AV01101957*20240927*1300*156441*X*005010X212~
        ST*277*1001*005010X212~
        BHT*0010*08*ABC276XXX*20050915*1425*DG~
        HL*1**20*1~
        NM1*PR*2*ABC INSURANCE*****PI*12345~
        HL*2*1*21*1~
        NM1*41*2*XYZ SERVICE*****46*X67E~
        HL*3*2*19*1~
        NM1*1P*2*HOME HOSPITAL*****XX*1666666661~
        HL*4*3*22*0~
        NM1*IL*1*SMITH*FRED****MI*123456789A~
        TRN*2*ABCXYZ1~
        STC*A1:21*20240927**8513.88*0*****E0:0~
        REF*BLT*111~
        REF*EJ*SM123456~
        DTP*472*RD8*20050831-20050906~
        SE*16*1001~
        ST*277*1002*005010X212~
        BHT*0010*08*ABC276XXX*20050915*1425*DG~
        HL*1**20*1~
        NM1*PR*2*ABC INSURANCE*****PI*12345~
        HL*2*1*21*1~
        NM1*41*2*XYZ SERVICE*****46*X67E~
        HL*3*2*19*1~
        NM1*1P*2*HOME HOSPITAL*****XX*1666666661~
        HL*4*3*22*0~
        NM1*IL*1*JONES*MARY****MI*234567890A~
        TRN*2*ABCXYZ2~
        STC*E0:21*20240927**7599*0*****E0:0~
        REF*BLT*111~
        REF*EJ*JO234567~
        DTP*472*RD8*20050731-20050809~
        SE*16*1002~
        ST*277*1003*005010X212~
        BHT*0010*08*ABC276XXX*20050915*1425*DG~
        HL*1**20*1~
        NM1*PR*2*ABC INSURANCE*****PI*12345~
        HL*2*1*21*1~
        NM1*41*2*XYZ SERVICE*****46*X67E~
        HL*3*2*19*1~
        NM1*1P*2*HOME HOSPITAL PHYSICIANS*****XX*1666666666~
        HL*4*3*22*1~
        NM1*IL*1*MANN*JOHN****MI*345678901~
        HL*5*4*23~
        NM1*QC*1*MANN*JOSEPH~
        TRN*2*ABCXYZ3~
        STC*F0:21*20240927**0*0*****E0:0~
        REF*1K*0~
        REF*EJ*MA345678~
        SE*17*1003~
        GE*3*156441~
        IEA*1*007205100~"""


parsed_277_data = X12Data277(
    interchange_control_header=InterchangeControlHeader(
        authorization_information_qualifier="00",
        authorization_information="",
        security_information_qualifier="00",
        security_information="",
        interchange_sender_id_qualifier="01",
        interchange_sender_id="030240928",
        interchange_receiver_id_qualifier="ZZ",
        interchange_receiver_id="AV09311993",
        interchange_date="240927",
        interchange_time="1300",
        repetition_separator="^",
        interchange_control_version_number="00501",
        interchange_control_number="007205100",
        acknowledgment_requested="0",
        interchange_usage_indicator="T",
        component_element_separator=":",
    ),
    transaction_set_header=TransactionSetHeader(
        transaction_set_identifier_code="277",
        transaction_set_control_number="1003",
        version_release_industry_identifier_code="005010X212",
    ),
    claims=[
        ClaimData(
            claim_status_tracking=ClaimStatusTrackingInformation(
                trace_type_code="2",
                referenced_transaction_trace_number="ABCXYZ1",
            ),
            claim_level_status=ClaimLevelStatusInformation(
                health_care_claim_status_category_code="A1",
                claim_status_code="21",
            ),
        ),
        ClaimData(
            claim_status_tracking=ClaimStatusTrackingInformation(
                trace_type_code="2",
                referenced_transaction_trace_number="ABCXYZ2",
            ),
            claim_level_status=ClaimLevelStatusInformation(
                health_care_claim_status_category_code="E0",
                claim_status_code="21",
            ),
        ),
        ClaimData(
            claim_status_tracking=ClaimStatusTrackingInformation(
                trace_type_code="2",
                referenced_transaction_trace_number="ABCXYZ3",
            ),
            claim_level_status=ClaimLevelStatusInformation(
                health_care_claim_status_category_code="F0",
                claim_status_code="21",
            ),
        ),
    ],
)

file_contents_277_missing_claim_status = """ISA*00*          *00*          *01*030240928      *ZZ*AV09311993     *240927*1300*^*00501*007205100*0*T*:~
        GS*HN*030240928*AV01101957*20240927*1300*156441*X*005010X212~
        ST*277*1001*005010X212~
        BHT*0010*08*ABC276XXX*20050915*1425*DG~
        HL*1**20*1~
        NM1*PR*2*ABC INSURANCE*****PI*12345~
        HL*2*1*21*1~
        NM1*41*2*XYZ SERVICE*****46*X67E~
        HL*3*2*19*1~
        NM1*1P*2*HOME HOSPITAL*****XX*1666666661~
        HL*4*3*22*0~
        NM1*IL*1*SMITH*FRED****MI*123456789A~
        TRN*2*ABCXYZ1~
        REF*BLT*111~
        REF*EJ*SM123456~
        DTP*472*RD8*20050831-20050906~
        SE*16*1001~
        ST*277*1002*005010X212~
        BHT*0010*08*ABC276XXX*20050915*1425*DG~
        HL*1**20*1~
        NM1*PR*2*ABC INSURANCE*****PI*12345~
        HL*2*1*21*1~
        NM1*41*2*XYZ SERVICE*****46*X67E~
        HL*3*2*19*1~
        NM1*1P*2*HOME HOSPITAL*****XX*1666666661~
        HL*4*3*22*0~
        NM1*IL*1*JONES*MARY****MI*234567890A~
        TRN*2*ABCXYZ2~
        STC*E0:21*20240927**7599*0*****E0:0~
        REF*BLT*111~
        REF*EJ*JO234567~
        DTP*472*RD8*20050731-20050809~
        SE*16*1002~
        ST*277*1003*005010X212~
        BHT*0010*08*ABC276XXX*20050915*1425*DG~
        HL*1**20*1~
        NM1*PR*2*ABC INSURANCE*****PI*12345~
        HL*2*1*21*1~
        NM1*41*2*XYZ SERVICE*****46*X67E~
        HL*3*2*19*1~
        NM1*1P*2*HOME HOSPITAL PHYSICIANS*****XX*1666666666~
        HL*4*3*22*1~
        NM1*IL*1*MANN*JOHN****MI*345678901~
        HL*5*4*23~
        NM1*QC*1*MANN*JOSEPH~
        TRN*2*ABCXYZ3~
        REF*1K*0~
        REF*EJ*MA345678~
        SE*17*1003~
        GE*3*156441~
        IEA*1*007205100~"""


parsed_277_data_missing_claim_status = X12Data277(
    interchange_control_header=InterchangeControlHeader(
        authorization_information_qualifier="00",
        authorization_information="",
        security_information_qualifier="00",
        security_information="",
        interchange_sender_id_qualifier="01",
        interchange_sender_id="030240928",
        interchange_receiver_id_qualifier="ZZ",
        interchange_receiver_id="AV09311993",
        interchange_date="240927",
        interchange_time="1300",
        repetition_separator="^",
        interchange_control_version_number="00501",
        interchange_control_number="007205100",
        acknowledgment_requested="0",
        interchange_usage_indicator="T",
        component_element_separator=":",
    ),
    transaction_set_header=TransactionSetHeader(
        transaction_set_identifier_code="277",
        transaction_set_control_number="1003",
        version_release_industry_identifier_code="005010X212",
    ),
    claims=[
        ClaimData(
            claim_status_tracking=ClaimStatusTrackingInformation(
                trace_type_code="2",
                referenced_transaction_trace_number="ABCXYZ1",
            ),
            claim_level_status=None,
        ),
        ClaimData(
            claim_status_tracking=ClaimStatusTrackingInformation(
                trace_type_code="2",
                referenced_transaction_trace_number="ABCXYZ2",
            ),
            claim_level_status=ClaimLevelStatusInformation(
                health_care_claim_status_category_code="E0",
                claim_status_code="21",
            ),
        ),
        ClaimData(
            claim_status_tracking=ClaimStatusTrackingInformation(
                trace_type_code="2",
                referenced_transaction_trace_number="ABCXYZ3",
            ),
            claim_level_status=None,
        ),
    ],
)
