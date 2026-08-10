from django.core.exceptions import ValidationError
from django.test import TestCase

from .models import Carousel
from .services import (
    CarouselPostNotFoundError,
    UnsupportedCarouselRequestError,
    process_carousel_data,
)


class ProcessCarouselDataTests(TestCase):
    def test_request_0x7a_creates_carousel_record(self):
        carousel_post = process_carousel_data({
            'request_type': '0x7a',
            'carousel_number': 1,
            'post_number': 7,
            'is_empty': True,
            'empty_weight': 18.2,
            'nfc_tag': 'test-tag',
            'serial_number': '123',
            'size': 50,
            'netto': 18.0,
            'brutto': 39.0,
            'filling_status': True,
        })

        self.assertEqual(Carousel.objects.count(), 1)
        self.assertEqual(carousel_post.post_number, 7)
        self.assertEqual(carousel_post.nfc_tag, 'test-tag')
        self.assertTrue(carousel_post.is_empty)

    def test_request_0x70_updates_latest_post_record(self):
        old_post = Carousel.objects.create(
            post_number=3,
            is_empty=True,
            full_weight=None,
        )
        latest_post = Carousel.objects.create(
            post_number=3,
            is_empty=True,
            full_weight=None,
        )

        updated_post = process_carousel_data({
            'request_type': '0x70',
            'post_number': 3,
            'full_weight': 40.5,
        })

        old_post.refresh_from_db()
        latest_post.refresh_from_db()
        self.assertEqual(updated_post.pk, latest_post.pk)
        self.assertTrue(old_post.is_empty)
        self.assertFalse(latest_post.is_empty)
        self.assertEqual(latest_post.full_weight, 40.5)

    def test_request_0x70_raises_when_post_does_not_exist(self):
        with self.assertRaises(CarouselPostNotFoundError):
            process_carousel_data({
                'request_type': '0x70',
                'post_number': 20,
                'full_weight': 40.5,
            })

    def test_missing_request_type_is_invalid(self):
        with self.assertRaises(ValidationError):
            process_carousel_data({'post_number': 1})

    def test_unknown_request_type_is_invalid(self):
        with self.assertRaises(UnsupportedCarouselRequestError):
            process_carousel_data({
                'request_type': 'unknown',
                'post_number': 1,
            })
