import json
import os
import shutil
import subprocess
import tempfile
from datetime import timedelta
from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from .models import PostLink, PublishState
from .publisher import is_due, publish
from .site_builder import build_site
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

    def test_root_goes_to_admin(self):
        response = self.client.get('/')
        self.assertRedirects(response, '/admin/', fetch_redirect_response=False)

    def test_all_preview_uses_referrer(self):
        response = self.client.get('/all/', HTTP_REFERER='https://l.instagram.com/?u=x')
        self.assertEqual(response.context['platform'], 'instagram')

    def test_all_preview_without_referrer_shows_all(self):
        response = self.client.get('/all/')
        self.assertEqual(response.context['platform'], '')

    def test_about_back_link_returns_to_platform_grid(self):
        response = self.client.get(reverse('about'), {'from': 'tiktok'})
        self.assertEqual(response.context['back_url'], '/tt')
        response = self.client.get(reverse('about'), {'from': 'evil'})
        self.assertEqual(response.context['back_url'], '/all/')


class AdminTests(GalleryTestCase):
    def setUp(self):
        self.admin_user = get_user_model().objects.create_superuser('admin', 'a@example.com', 'pw')
        self.client.force_login(self.admin_user)

    def test_changelist_and_form_render(self):
        post = self.make_post('Shown in admin')
        response = self.client.get(reverse('admin:products_postlink_changelist'))
        self.assertContains(response, 'Shown in admin')
        response = self.client.get(reverse('admin:products_postlink_change', args=[post.pk]))
        self.assertContains(response, 'Show on')

    def test_publish_now_action(self):
        response = self.client.get(reverse('admin:products_postlink_publish_now'), follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Publishing - the site updates in about a minute.')
        state = PublishState.get()
        self.assertTrue(state.needs_publish)
        # changed_at must be in the past to skip debounce
        self.assertTrue(state.changed_at <= timezone.now() - timedelta(seconds=10))

    def test_changelist_status_message_error(self):
        state = PublishState.get()
        state.last_status = 'error'
        state.last_error = 'Deployment failed with code 1\nStack trace line 2'
        state.save()
        response = self.client.get(reverse('admin:products_postlink_changelist'))
        self.assertContains(response, 'Deployment failed with code 1')

    def test_changelist_status_message_waiting(self):
        state = PublishState.get()
        state.last_status = ''
        state.needs_publish = True
        state.save()
        response = self.client.get(reverse('admin:products_postlink_changelist'))
        self.assertContains(response, 'Changes waiting to publish')

    def test_changelist_status_message_published(self):
        state = PublishState.get()
        state.last_status = 'ok'
        state.needs_publish = False
        state.last_published_at = timezone.now()
        state.save()
        response = self.client.get(reverse('admin:products_postlink_changelist'))
        self.assertContains(response, 'Last published:')


class DetectPlatformTests(TestCase):
    def test_detect(self):
        self.assertEqual(detect_platform('https://m.youtube.com/shorts/x'), 'youtube')
        self.assertEqual(detect_platform('https://youtu.be/x'), 'youtube')
        self.assertEqual(detect_platform('https://www.tiktok.com/'), 'tiktok')
        self.assertEqual(detect_platform('instagram.com'), 'instagram')
        self.assertEqual(detect_platform(''), '')
        self.assertEqual(detect_platform('https://example.com/instagram'), '')


class BuildSiteTests(GalleryTestCase):
    @override_settings(
        ALLOWED_HOSTS=['admin.engineericly.com'],
        PUBLIC_SITE_URL='https://links.engineericly.com',
    )
    def test_build_works_when_public_host_is_not_allowed(self):
        # The admin server only allows its own host; the build renders for the public one.
        self.make_post('Model')
        with tempfile.TemporaryDirectory() as out_dir:
            build_site(out_dir)
            with open(os.path.join(out_dir, 'ig.html'), encoding='utf-8') as f:
                self.assertIn('https://links.engineericly.com/static/images/logo.jpg', f.read())
        from django.conf import settings
        self.assertEqual(settings.ALLOWED_HOSTS, ['admin.engineericly.com'])

    def test_build_site_files_and_structure(self):
        published = self.make_post('Published Model')
        scheduled = self.make_post('Scheduled Model', published_at=timezone.now() + timedelta(days=2))

        # Create an orphan file that is not referenced by any post
        orphan_dir = os.path.join(MEDIA_ROOT, 'post_links')
        os.makedirs(orphan_dir, exist_ok=True)
        orphan_file = os.path.join(orphan_dir, 'orphan.png')
        with open(orphan_file, 'wb') as f:
            f.write(b'orphan')

        with tempfile.TemporaryDirectory() as out_dir:
            build_site(out_dir)

            # Check core files exist
            expected_files = [
                'index.html',
                'ig.html',
                'tt.html',
                'yt.html',
                'about/index.html',
                'data/all/1.json',
                'data/instagram/1.json',
                'data/tiktok/1.json',
                'data/youtube/1.json',
                '_headers',
                'static/css/styles.css',
            ]
            for f in expected_files:
                self.assertTrue(os.path.exists(os.path.join(out_dir, f)), f"Missing file: {f}")

            # 404.html must NOT exist
            self.assertFalse(os.path.exists(os.path.join(out_dir, '404.html')))

            # Check referenced media only
            self.assertTrue(os.path.exists(os.path.join(out_dir, 'media', published.file.name)))
            self.assertFalse(os.path.exists(os.path.join(out_dir, 'media', scheduled.file.name)))
            self.assertFalse(os.path.exists(os.path.join(out_dir, 'media', 'post_links', 'orphan.png')))

            # Check _headers content
            with open(os.path.join(out_dir, '_headers'), 'r', encoding='utf-8') as f:
                headers = f.read()
            self.assertIn('/static/*', headers)
            self.assertIn('Cache-Control: public, max-age=86400', headers)
            self.assertIn('/media/*', headers)
            self.assertIn('Cache-Control: public, max-age=604800', headers)
            self.assertIn('/data/*', headers)
            self.assertIn('Cache-Control: public, max-age=60', headers)

            # Check static HTML contents
            with open(os.path.join(out_dir, 'index.html'), 'r', encoding='utf-8') as f:
                index_html = f.read()
            self.assertIn('window.GALLERY_PAGES = "/data/all/";', index_html)
            self.assertNotIn('window.GALLERY_API', index_html)
            self.assertIn('https://links.engineericly.com/static/images/logo.jpg', index_html)

            with open(os.path.join(out_dir, 'ig.html'), 'r', encoding='utf-8') as f:
                ig_html = f.read()
            self.assertIn('window.GALLERY_PAGES = "/data/instagram/";', ig_html)

            # Check about.html
            with open(os.path.join(out_dir, 'about', 'index.html'), 'r', encoding='utf-8') as f:
                about_html = f.read()
            self.assertIn('<a href="/" class="text-link" id="back-link">', about_html)
            self.assertIn('new URLSearchParams(window.location.search)', about_html)

    def test_per_platform_json_filtering(self):
        self.make_post('Everywhere')
        self.make_post('Only Instagram', show_for_tiktok=False, show_for_youtube=False)
        self.make_post('Only TikTok', show_for_instagram=False, show_for_youtube=False)
        self.make_post('Only YouTube', show_for_instagram=False, show_for_tiktok=False)

        with tempfile.TemporaryDirectory() as out_dir:
            build_site(out_dir)

            def get_titles(platform_dir):
                with open(os.path.join(out_dir, 'data', platform_dir, '1.json'), 'r', encoding='utf-8') as f:
                    data = json.load(f)
                return [item['title'] for item in data['items']]

            ig_titles = get_titles('instagram')
            self.assertIn('Everywhere', ig_titles)
            self.assertIn('Only Instagram', ig_titles)
            self.assertNotIn('Only TikTok', ig_titles)
            self.assertNotIn('Only YouTube', ig_titles)

            tt_titles = get_titles('tiktok')
            self.assertIn('Everywhere', tt_titles)
            self.assertIn('Only TikTok', tt_titles)
            self.assertNotIn('Only Instagram', tt_titles)
            self.assertNotIn('Only YouTube', tt_titles)

            yt_titles = get_titles('youtube')
            self.assertIn('Everywhere', yt_titles)
            self.assertIn('Only YouTube', yt_titles)
            self.assertNotIn('Only Instagram', yt_titles)
            self.assertNotIn('Only TikTok', yt_titles)

            all_titles = get_titles('all')
            self.assertEqual(len(all_titles), 4)

    def test_empty_platform_has_1_json(self):
        with tempfile.TemporaryDirectory() as out_dir:
            build_site(out_dir)
            json_file = os.path.join(out_dir, 'data', 'instagram', '1.json')
            self.assertTrue(os.path.exists(json_file))
            with open(json_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            self.assertEqual(data['items'], [])
            self.assertEqual(data['page'], 1)
            self.assertEqual(data['total_items'], 0)
            self.assertEqual(data['total_pages'], 1)
            self.assertFalse(data['has_next'])

    def test_scheduled_posts_excluded(self):
        self.make_post('Visible Post')
        self.make_post('Future Post', published_at=timezone.now() + timedelta(days=2))

        with tempfile.TemporaryDirectory() as out_dir:
            build_site(out_dir)
            with open(os.path.join(out_dir, 'data', 'all', '1.json'), 'r', encoding='utf-8') as f:
                data = json.load(f)
            titles = [i['title'] for i in data['items']]
            self.assertIn('Visible Post', titles)
            self.assertNotIn('Future Post', titles)

    def test_pagination_files(self):
        for i in range(19):
            self.make_post(f'Item {i:02d}')

        with tempfile.TemporaryDirectory() as out_dir:
            build_site(out_dir)
            p1_path = os.path.join(out_dir, 'data', 'all', '1.json')
            p2_path = os.path.join(out_dir, 'data', 'all', '2.json')
            self.assertTrue(os.path.exists(p1_path))
            self.assertTrue(os.path.exists(p2_path))

            with open(p1_path, 'r', encoding='utf-8') as f:
                p1 = json.load(f)
            with open(p2_path, 'r', encoding='utf-8') as f:
                p2 = json.load(f)

            self.assertEqual(len(p1['items']), 18)
            self.assertEqual(p1['page'], 1)
            self.assertTrue(p1['has_next'])
            self.assertEqual(p1['total_pages'], 2)
            self.assertEqual(p1['total_items'], 19)

            self.assertEqual(len(p2['items']), 1)
            self.assertEqual(p2['page'], 2)
            self.assertFalse(p2['has_next'])
            self.assertEqual(p2['total_pages'], 2)
            self.assertEqual(p2['total_items'], 19)


class SignalTests(GalleryTestCase):
    def test_signals_set_needs_publish(self):
        state = PublishState.get()
        state.needs_publish = False
        state.changed_at = None
        state.save()

        post = self.make_post('New Post')
        state.refresh_from_db()
        self.assertTrue(state.needs_publish)
        self.assertIsNotNone(state.changed_at)

        state.needs_publish = False
        state.changed_at = None
        state.save()

        post.delete()
        state.refresh_from_db()
        self.assertTrue(state.needs_publish)
        self.assertIsNotNone(state.changed_at)


class PublisherTests(GalleryTestCase):
    @override_settings(CLOUDFLARE_API_TOKEN='dummy-token', CLOUDFLARE_ACCOUNT_ID='dummy-acc')
    @patch('products.publisher.subprocess.run')
    def test_publish_success(self, mock_run):
        mock_run.return_value = subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout="Deployment complete! https://abc-123.pages.dev",
            stderr="",
        )
        state = PublishState.get()
        state.needs_publish = True
        state.changed_at = timezone.now() - timedelta(seconds=20)
        state.save()

        result = publish()
        self.assertTrue(result)

        state.refresh_from_db()
        self.assertEqual(state.last_status, 'ok')
        self.assertFalse(state.needs_publish)
        self.assertEqual(state.last_url, 'https://abc-123.pages.dev')
        self.assertIsNotNone(state.last_published_at)
        self.assertEqual(state.last_error, '')

    @override_settings(CLOUDFLARE_API_TOKEN='dummy-token')
    @patch('products.publisher.subprocess.run')
    def test_publish_failure(self, mock_run):
        mock_run.return_value = subprocess.CompletedProcess(
            args=[],
            returncode=1,
            stdout="",
            stderr="Error: deploy failed due to network timeout",
        )
        state = PublishState.get()
        state.needs_publish = True
        state.save()

        result = publish()
        self.assertFalse(result)

        state.refresh_from_db()
        self.assertEqual(state.last_status, 'error')
        self.assertTrue(state.needs_publish)
        self.assertIn('Error: deploy failed', state.last_error)

    @override_settings(CLOUDFLARE_API_TOKEN='dummy-token')
    @patch('products.publisher.subprocess.run')
    def test_edit_during_deploy_keeps_needs_publish(self, mock_run):
        def fake_deploy(*args, **kwargs):
            # Simulate a post change during deploy
            self.make_post('Created during deploy')
            return subprocess.CompletedProcess(
                args=[],
                returncode=0,
                stdout="https://abc-123.pages.dev",
                stderr="",
            )

        mock_run.side_effect = fake_deploy
        state = PublishState.get()
        state.needs_publish = True
        state.changed_at = timezone.now() - timedelta(seconds=20)
        state.save()

        result = publish()
        self.assertTrue(result)

        state.refresh_from_db()
        self.assertEqual(state.last_status, 'ok')
        # needs_publish must remain True because changed_at updated during deployment
        self.assertTrue(state.needs_publish)

    @override_settings(CLOUDFLARE_API_TOKEN='')
    @patch('products.publisher.subprocess.run')
    def test_missing_token_records_error_without_subprocess(self, mock_run):
        result = publish()
        self.assertFalse(result)
        mock_run.assert_not_called()

        state = PublishState.get()
        self.assertEqual(state.last_status, 'error')
        self.assertEqual(state.last_error, 'Cloudflare is not configured')


class IsDueTests(GalleryTestCase):
    def test_debounce(self):
        state = PublishState.get()
        state.needs_publish = True
        state.last_published_at = timezone.now() - timedelta(hours=1)
        # Just changed (within 10s debounce)
        state.changed_at = timezone.now() - timedelta(seconds=2)
        state.save()
        self.assertFalse(is_due(timezone.now()))

        # Changed earlier than 10s ago
        state.changed_at = timezone.now() - timedelta(seconds=15)
        state.save()
        self.assertTrue(is_due(timezone.now()))

    def test_scheduled_post_becoming_due(self):
        state = PublishState.get()
        state.needs_publish = False
        state.last_published_at = timezone.now() - timedelta(hours=1)
        state.save()

        # Create scheduled post with published_at 10 minutes ago
        self.make_post('Scheduled Now Due', published_at=timezone.now() - timedelta(minutes=10))
        state.refresh_from_db()
        # Reset needs_publish to specifically test the scheduled post condition
        state.needs_publish = False
        state.save()

        self.assertTrue(is_due(timezone.now()))

    def test_first_publish_when_posts_exist(self):
        state = PublishState.get()
        state.needs_publish = False
        state.last_published_at = None
        state.save()

        self.make_post('First Post')
        state.refresh_from_db()
        state.needs_publish = False
        state.save()

        self.assertTrue(is_due(timezone.now()))


class PublisherCommandTests(GalleryTestCase):
    @patch('products.management.commands.run_publisher.is_due')
    @patch('products.management.commands.run_publisher.publish')
    def test_run_publisher_once(self, mock_publish, mock_is_due):
        mock_is_due.return_value = True
        mock_publish.return_value = True

        call_command('run_publisher', once=True)
        mock_is_due.assert_called_once()
        mock_publish.assert_called_once()

    @override_settings(CLOUDFLARE_API_TOKEN='dummy')
    @patch('products.publisher.subprocess.run')
    def test_publish_command_success(self, mock_run):
        mock_run.return_value = subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout="https://test.pages.dev",
            stderr="",
        )
        call_command('publish')
        state = PublishState.get()
        self.assertEqual(state.last_status, 'ok')
