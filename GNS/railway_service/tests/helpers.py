from django.contrib.auth.models import User

from railway_service.models import RailwayBatch, RailwayTank, RailwayTankHistory


class RailwayFixturesMixin:
    def setUp(self):
        super().setUp()
        try:
            self.user = User.objects.get(pk=1)
        except User.DoesNotExist:
            self.user = User.objects.create_user(
                id=1,
                username='railway_operator',
                password='x',
            )

    def make_tank(self, registration_number: int, **history_kwargs) -> RailwayTank:
        tank = RailwayTank.objects.create(
            registration_number=registration_number,
            user=self.user,
        )
        if history_kwargs:
            RailwayTankHistory.objects.create(tank=tank, **history_kwargs)
        return tank

    def make_batch(self, tanks=(), **kwargs) -> RailwayBatch:
        defaults = {'user': self.user, 'is_active': False}
        defaults.update(kwargs)
        batch = RailwayBatch.objects.create(**defaults)
        if tanks:
            batch.railway_tank_list.set(tanks)
        return batch
