import logging
from django.core.management.base import BaseCommand
from datetime import datetime, timedelta
from filling_station.models import RailwayBatch

logger = logging.getLogger('filling_station')


class Command(BaseCommand):
    def handle(self, *args, **kwargs):

        railway_batch = RailwayBatch.objects.filter(is_active=True)
        if railway_batch:
            current_datetime = datetime.now()

            for batch in railway_batch:
                if batch.begin_date < current_datetime - timedelta(hours=1):
                    batch.is_active = False
                    batch.save()
