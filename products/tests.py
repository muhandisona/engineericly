import shutil
import tempfile
from datetime import timedelta

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from .models import PostLink
from .views import PAGE_SIZE, detect_platform

MEDIA_ROOT = tempfile.mkdtemp()


@override_settings(MEDIA_ROOT=MEDIA_ROOT)
class GalleryTestCase(TestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(MEDIA_ROOT, ignore_errors=True)

    def make_post(self, title, **kwargs):
        defaults = {
            'link': 'https://www.makerworld.com/en/models/1',
            'file': SimpleUploadedFile(f'{title}.png', b'img', content_type='image/png'),
        }
        defaults.update(kwargs)
        return PostLink.objects.create(title=title, **defaults)

    def fetch(self, **params):
        response = self.client.get(reverse('api_gallery'), params)
        self.assertEqual(response.status_code, 200)
        return response.json()

    def titles(self, **params):
        return [item['title'] for item in self.fetch(**params)['items']]


class ApiGalleryTests(GalleryTestCase):
    def setUp(self):
        self.make_post('Everywhere')
        self.make_post('Not on Instagram', show_for_instagram=False)
        self.make_post('Not on TikTok', show_for_tiktok=False)
        self.make_post('Not on YouTube', show_for_youtube=False)

    def test_platform_filters_by_its_flag(self):
        self.assertNotIn('Not on Instagram', self.titles(platform='instagram'))
        self.assertNotIn('Not on TikTok', self.titles(platform='tiktok'))
        self.assertNotIn('Not on YouTube', self.titles(platform='youtube'))
        self.assertEqual(len(self.titles(platform='instagram')), 3)

    def test_no_platform_shows_everything(self):
        self.assertEqual(len(self.titles()), 4)

    def test_unknown_platform_shows_everything(self):
        self.assertEqual(len(self.titles(platform='myspace')), 4)

    def test_legacy_domain_param_still_filters(self):
        self.assertNotIn('Not on TikTok', self.titles(domain='https://www.tiktok.com/@engineericly'))

    def test_scheduled_posts_are_hidden(self):
        self.make_post('Tomorrow', published_at=timezone.now() + timedelta(days=1))
        self.assertNotIn('Tomorrow', self.titles())

    def test_pinned_post_comes_first(self):
        self.make_post('Pinned', is_pinned=True)
        self.assertEqual(self.titles()[0], 'Pinned')

    def test_item_shape(self):
        item = self.fetch()['items'][0]
        self.assertEqual(item['host'], 'makerworld.com')
        self.assertTrue(item['image'].startswith('/media/post_links/'))
        self.assertIn('is_pinned', item)


class PaginationTests(GalleryTestCase):
    def test_pages_and_out_of_range(self):
        for i in range(PAGE_SIZE + 1):
            self.make_post(f'Post {i}')
        first = self.fetch(page=1)
        self.assertEqual(len(first['items']), PAGE_SIZE)
        self.assertTrue(first['has_next'])
        second = self.fetch(page=2)
        self.assertEqual(len(second['items']), 1)
        self.assertFalse(second['has_next'])
        # Past the end returns nothing instead of repeating the last page.
        beyond = self.fetch(page=3)
        self.assertEqual(beyond['items'], [])
        self.assertFalse(beyond['has_next'])

    def test_bad_page_falls_back_to_first(self):
        self.make_post('Only')
        self.assertEqual(self.fetch(page='abc')['page'], 1)


class FeedPageTests(TestCase):
    def test_platform_routes(self):
        for path, platform in (('/ig', 'instagram'), ('/tt', 'tiktok'), ('/yt', 'youtube'), ('/ig/', 'instagram')):
            response = self.client.get(path)
            self.assertEqual(response.status_code, 200, path)
            self.assertEqual(response.context['platform'], platform, path)

    def test_root_uses_referrer(self):
        response = self.client.get('/', HTTP_REFERER='https://l.instagram.com/?u=x')
        self.assertEqual(response.context['platform'], 'instagram')

    def test_root_without_referrer_shows_all(self):
        response = self.client.get('/')
        self.assertEqual(response.context['platform'], '')

    def test_about_back_link_returns_to_platform_grid(self):
        response = self.client.get(reverse('about'), {'from': 'tiktok'})
        self.assertEqual(response.context['back_url'], '/tt')
        response = self.client.get(reverse('about'), {'from': 'evil'})
        self.assertEqual(response.context['back_url'], '/')


class AdminTests(GalleryTestCase):
    def test_changelist_and_form_render(self):
        from django.contrib.auth import get_user_model
        admin_user = get_user_model().objects.create_superuser('admin', 'a@example.com', 'pw')
        self.client.force_login(admin_user)
        post = self.make_post('Shown in admin')
        response = self.client.get(reverse('admin:products_postlink_changelist'))
        self.assertContains(response, 'Shown in admin')
        response = self.client.get(reverse('admin:products_postlink_change', args=[post.pk]))
        self.assertContains(response, 'Show on')


class DetectPlatformTests(TestCase):
    def test_detect(self):
        self.assertEqual(detect_platform('https://m.youtube.com/shorts/x'), 'youtube')
        self.assertEqual(detect_platform('https://youtu.be/x'), 'youtube')
        self.assertEqual(detect_platform('https://www.tiktok.com/'), 'tiktok')
        self.assertEqual(detect_platform('instagram.com'), 'instagram')
        self.assertEqual(detect_platform(''), '')
        self.assertEqual(detect_platform('https://example.com/instagram'), '')
