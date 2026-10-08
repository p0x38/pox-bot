import hashlib
import io
import json
from pathlib import Path

import pytest
from PIL import Image, ImageDraw
from urlextract import URLExtract

from poxbot.features.moderation import (
    GlobalChatModerator,
    ModerationAction,
    ThreatCatalog,
)
from poxbot.features.moderation.manager import GlobalChatModerator as Moderator
from poxbot.persistence.models.pydantic.blacklisted_item import (
    BlacklistItem,
    BlacklistReason,
)


def _indicator(
    indicator_type: str,
    value: str,
    *,
    indicator_id: str = 'test-indicator',
    algorithm: str | None = None,
    max_distance: int | None = None,
    status: str = 'confirmed',
) -> dict:
    return {
        'id': indicator_id,
        'type': indicator_type,
        'algorithm': algorithm,
        'value': value,
        'reason': {
            'category': 'giveaway_scam',
            'description': 'Confirmed fraudulent giveaway',
        },
        'confidence': 0.99,
        'status': status,
        'source': 'moderator_report',
        'created_at': '2026-10-09T00:00:00Z',
        'reviewed_at': '2026-10-09T00:00:00Z' if status == 'confirmed' else None,
        'max_distance': max_distance,
    }


def _moderator(indicators: list[dict] | None = None) -> GlobalChatModerator:
    moderator = GlobalChatModerator(URLExtract())
    moderator.load_catalog(
        {
            'schema_version': 1,
            'indicators': indicators or [],
        },
    )
    return moderator


def _image_bytes() -> bytes:
    image = Image.new('RGB', (128, 128), color='white')
    draw = ImageDraw.Draw(image)
    draw.rectangle((20, 20, 80, 80), fill='black')
    draw.ellipse((50, 55, 110, 115), fill='red')
    stream = io.BytesIO()
    image.save(stream, format='PNG')
    return stream.getvalue()


def _reencoded_image_bytes() -> bytes:
    image = Image.open(io.BytesIO(_image_bytes()))
    image = image.resize((96, 96), Image.Resampling.LANCZOS)
    stream = io.BytesIO()
    image.save(stream, format='JPEG', quality=72)
    return stream.getvalue()


def test_empty_catalog_validates_and_clean_content_is_allowed():
    catalog = ThreatCatalog.model_validate({'schema_version': 1, 'indicators': []})
    moderator = _moderator()

    assert catalog.indicators == ()
    assert (
        moderator.moderate_text('Hello global chat!').action == ModerationAction.ALLOW
    )
    assert moderator.moderate_images([]).action == ModerationAction.ALLOW


def test_packaged_threat_catalog_is_valid_json():
    catalog_path = (
        Path(__file__).parents[2]
        / 'src'
        / 'poxbot'
        / 'assets'
        / 'global_chat_threats.json'
    )

    ThreatCatalog.model_validate(json.loads(catalog_path.read_text(encoding='utf-8')))


def test_known_url_domain_blocks_subdomains():
    moderator = _moderator(
        [
            _indicator('url_domain', 'evil.example.com'),
        ]
    )

    result = moderator.moderate_text(
        'Claim the prize at https://offers.evil.example.com/winner',
    )

    assert result.action == ModerationAction.BLOCK
    assert result.reason_codes == ('giveaway_scam',)


def test_bare_url_domain_is_detected():
    moderator = _moderator(
        [
            _indicator('url_domain', 'evil.example.com'),
        ]
    )

    result = moderator.moderate_text('Offers at offers.evil.example.com are real')

    assert result.action == ModerationAction.BLOCK


def test_legacy_ip_logger_domain_blocks_but_shortener_does_not():
    moderator = Moderator(
        URLExtract(),
        {
            BlacklistItem(
                value='iplogger.org',
                reasons=((BlacklistReason.IP_LOGGER, 'IP logger'),),
            ),
            BlacklistItem(
                value='bit.ly',
                reasons=((BlacklistReason.URL_SHORTENER, 'URL shortener'),),
            ),
        },
    )

    assert (
        moderator.moderate_text('https://sub.iplogger.org/path').action
        == ModerationAction.BLOCK
    )
    assert (
        moderator.moderate_text('https://bit.ly/abc').action == ModerationAction.ALLOW
    )


def test_text_phrase_is_normalized_and_unreviewed_match_goes_to_review():
    moderator = _moderator(
        [
            _indicator(
                'text_phrase',
                'Claim your prize now',
                status='pending',
            ),
        ]
    )

    result = moderator.moderate_text('CLAIM\u200b your PRIZE now')

    assert result.action == ModerationAction.REVIEW


def test_discord_invite_is_blocked():
    result = _moderator().moderate_text('Join us at discord.com/invite/abc123')

    assert result.action == ModerationAction.BLOCK
    assert result.reason_codes == ('discord_invite',)


def test_exact_image_hash_blocks_confirmed_indicator():
    image_data = _image_bytes()
    image_hash = hashlib.sha256(image_data).hexdigest()
    moderator = _moderator(
        [
            _indicator(
                'image_hash',
                image_hash,
                algorithm='sha256',
            ),
        ]
    )

    result = moderator.moderate_images([image_data])

    assert result.action == ModerationAction.BLOCK
    assert result.evidence[0].match_type == 'sha256'


def test_perceptual_image_match_requires_review():
    image_data = _image_bytes()
    _, perceptual_hash = Moderator._hash_image(image_data)
    moderator = _moderator(
        [
            _indicator(
                'image_hash',
                perceptual_hash,
                algorithm='phash',
                max_distance=4,
            ),
        ]
    )

    result = moderator.moderate_images([image_data])

    assert result.action == ModerationAction.REVIEW
    assert result.evidence[0].match_type == 'phash:review'


def test_perceptual_hash_matches_resized_recompressed_image():
    original = _image_bytes()
    changed = _reencoded_image_bytes()
    _, perceptual_hash = Moderator._hash_image(original)
    moderator = _moderator(
        [
            _indicator(
                'image_hash',
                perceptual_hash,
                algorithm='phash',
                max_distance=8,
            ),
        ]
    )

    result = moderator.moderate_images([changed])

    assert result.action == ModerationAction.REVIEW
    assert result.evidence[0].match_type == 'phash:review'


def test_unreadable_image_requires_review():
    result = _moderator().moderate_images([b'not an image'])

    assert result.action == ModerationAction.REVIEW
    assert result.reason_codes == ('image_decode_failed',)


def test_catalog_rejects_unreviewed_confirmed_indicator():
    raw_indicator = _indicator('url_domain', 'evil.example.com')
    raw_indicator['reviewed_at'] = None

    with pytest.raises(ValueError, match='reviewed_at'):
        _moderator([raw_indicator])


def test_expired_indicator_does_not_match():
    indicator = _indicator('url_domain', 'evil.example.com')
    indicator['created_at'] = '2026-10-08T00:00:00Z'
    indicator['reviewed_at'] = '2026-10-08T00:00:00Z'
    indicator['expires_at'] = '2026-10-08T12:00:00Z'
    moderator = _moderator([indicator])

    result = moderator.moderate_text('https://evil.example.com')

    assert result.action == ModerationAction.ALLOW
