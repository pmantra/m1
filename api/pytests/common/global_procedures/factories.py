import factory


class CoreProcedureFieldsFactory(factory.Factory):
    class Meta:
        model = dict

    id = factory.Faker("uuid4")
    name = factory.Faker("bs")
    cost_sharing_category = "generic_prescriptions"
    ndc_number = factory.Faker("bothify", text="####-####-##")
    hcpcs_code = factory.Faker("numerify", text="S####")
    type = "medical"
    annual_limit = None
    is_diagnostic = False
    credits = 0
    created_at = factory.Faker("iso8601")
    updated_at = factory.Faker("iso8601")
    start_date = factory.Faker("date")
    end_date = factory.Faker("date")


class PartialProcedureFactory(CoreProcedureFieldsFactory):
    class Meta:
        model = dict

    is_partial = True
    parent_procedure_ids = factory.List([factory.Faker("uuid4")])


PartialProcedureSubFactory = factory.SubFactory(
    PartialProcedureFactory,
    parent_procedure_ids=factory.List([factory.SelfAttribute("..id")]),
)


class GlobalProcedureFactory(CoreProcedureFieldsFactory):
    class Meta:
        model = dict

    name = factory.Faker("bs")
    ndc_number = factory.Faker("bothify", text="####-####-##")
    is_partial = False
    partial_procedures = factory.List(
        [
            PartialProcedureSubFactory,
            PartialProcedureSubFactory,
        ]
    )
