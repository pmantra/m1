from pytests import factories


class ProviderFactory(factories.PractitionerUserFactory):
    @classmethod
    def create(cls, **kwargs):
        """
        Override to get only the practitioner_profile, not the User
        """
        result = super().create(**kwargs)
        return result.practitioner_profile
