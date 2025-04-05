import logging
from django.core.management.base import BaseCommand
from datetime import datetime, timedelta, timezone
from filling_station.models import RailwayBatch

logger = logging.getLogger('filling_station')


class Command(BaseCommand):
    def handle(self, *args, **kwargs):

        railway_batch = RailwayBatch.objects.filter(is_active=True)
        if railway_batch:
            current_datetime = datetime.now(timezone.utc)

            for batch in railway_batch:
                logger.debug(f'Есть активная партия: {batch}')
                if batch.begin_date < current_datetime - timedelta(minutes=30):
                    batch.is_active = False
                    batch.end_date = current_datetime
                    batch.save()
