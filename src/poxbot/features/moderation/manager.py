import hashlib
import io
import re
from datetime import UTC, datetime
from typing import Any

import numpy as np
from PIL import Image, ImageOps, UnidentifiedImageError
from urlextract import URLExtract

from ...persistence.models.pydantic.blacklisted_item import (
    BlacklistItem,
    BlacklistReason,
)
from .models import (
    ModerationAction,
    ModerationEvidence,
    ModerationResult,
    ThreatCatalog,
    ThreatIndicator,
    indicator_is_active,
)
from .normalization import (
    domain_matches,
    extract_url_host,
    normalize_domain,
    normalize_text,
)

MAX_IMAGE_BYTES = 8 * 1024 * 1024
MAX_TOTAL_IMAGE_BYTES = 16 * 1024 * 1024
MAX_IMAGE_DIMENSION = 4096
MAX_IMAGE_PIXELS = MAX_IMAGE_DIMENSION**2
SUPPORTED_IMAGE_FORMATS = {'JPEG', 'PNG', 'WEBP'}
_INVITE_PATTERN = re.compile(
    r'(?:https?://)?(?:www\.)?(?:discord\.gg|discord(?:app)?\.com/invite)/[a-z0-9-]+',
)


class GlobalChatModerator:
    def __init__(
        self,
        url_extractor: URLExtract,
        blacklisted_domains: set[BlacklistItem] | None = None,
    ):
        self.url_extractor = url_extractor
        self.catalog = ThreatCatalog(schema_version=1)
        self.legacy_domains = self._get_legacy_malicious_domains(
            blacklisted_domains or set(),
        )

    def load_catalog(self, raw_data: Any) -> None:
        self.catalog = ThreatCatalog.model_validate(raw_data)

    def moderate_text(self, text: str) -> ModerationResult:
        normalized = normalize_text(text)
        evidence: list[ModerationEvidence] = []

        if _INVITE_PATTERN.search(normalized):
            evidence.append(
                ModerationEvidence(
                    reason_code='discord_invite',
                    description='Discord invite links are not allowed in global chat',
                ),
            )

        evidence.extend(
            self._evidence(phrase, 'text_phrase')
            for phrase in self._active_indicators('text_phrase')
            if phrase.value in normalized
        )

        extracted_urls = self.url_extractor.find_urls(
            normalized,
            only_unique=True,
            check_dns=False,
            with_schema_only=False,
        )
        for url in extracted_urls or ():
            if not isinstance(url, str):
                continue
            hostname = extract_url_host(url)
            if hostname is None:
                continue

            for domain, reason in self.legacy_domains.items():
                if domain_matches(hostname, domain):
                    evidence.append(
                        ModerationEvidence(
                            reason_code=reason[0],
                            description=reason[1],
                            match_type='legacy_domain',
                        ),
                    )

            evidence.extend(
                self._evidence(indicator, 'url_domain')
                for indicator in self._active_indicators('url_domain')
                if domain_matches(hostname, indicator.value)
            )

        return self._result_for_evidence(evidence)

    def moderate_images(self, image_data: list[bytes]) -> ModerationResult:
        evidence: list[ModerationEvidence] = []
        indicators = self._active_indicators('image_hash')

        for data in image_data:
            if len(data) > MAX_IMAGE_BYTES:
                return ModerationResult.review(
                    'attachment_size_limit',
                    'Image exceeds the moderation size limit',
                )

            try:
                sha256, phash = self._hash_image(data)
            except (UnidentifiedImageError, OSError, Image.DecompressionBombError):
                return ModerationResult.review(
                    'image_decode_failed',
                    'Image could not be safely decoded for moderation',
                )
            except ValueError as error:
                return ModerationResult.review(
                    'image_not_supported',
                    str(error),
                )

            for indicator in indicators:
                if indicator.algorithm == 'sha256' and sha256 == indicator.value:
                    evidence.append(self._evidence(indicator, 'sha256'))
                elif indicator.algorithm == 'phash':
                    distance = (int(phash, 16) ^ int(indicator.value, 16)).bit_count()
                    if (
                        indicator.max_distance is not None
                        and distance <= indicator.max_distance
                    ):
                        evidence.append(
                            self._evidence(indicator, 'phash', force_review=True),
                        )

        return self._result_for_evidence(evidence)

    @staticmethod
    def _hash_image(data: bytes) -> tuple[str, str]:
        with Image.open(io.BytesIO(data)) as source:
            if source.format not in SUPPORTED_IMAGE_FORMATS:
                raise ValueError('Image format is not supported for moderation')
            if getattr(source, 'n_frames', 1) != 1:
                raise ValueError('Animated images are held for manual review')
            if (
                source.width > MAX_IMAGE_DIMENSION
                or source.height > MAX_IMAGE_DIMENSION
            ):
                raise ValueError('Image dimensions exceed the moderation limit')
            if source.width * source.height > MAX_IMAGE_PIXELS:
                raise ValueError('Image pixel count exceeds the moderation limit')

            image = (
                ImageOps.exif_transpose(source)
                .convert('L')
                .resize(
                    (32, 32),
                    Image.Resampling.LANCZOS,
                )
            )

        pixels = np.asarray(image, dtype=np.float64)
        size = pixels.shape[0]
        positions = np.arange(size, dtype=np.float64)
        basis = np.cos(
            np.pi * (2 * positions[:, None] + 1) * positions[None, :] / (2 * size),
        )
        basis[0, :] *= 1 / np.sqrt(2)
        basis *= np.sqrt(2 / size)

        coefficients = basis @ pixels @ basis.T
        low_frequencies = coefficients[:8, :8]
        median = np.median(low_frequencies.flatten()[1:])
        bits = low_frequencies > median
        phash = f'{int("".join("1" if bit else "0" for bit in bits.flat), 2):016x}'
        return hashlib.sha256(data).hexdigest(), phash

    def _active_indicators(self, indicator_type: str) -> list[ThreatIndicator]:
        now = datetime.now(UTC)
        return [
            indicator
            for indicator in self.catalog.indicators
            if indicator.type == indicator_type and indicator_is_active(indicator, now)
        ]

    @staticmethod
    def _evidence(
        indicator: ThreatIndicator,
        match_type: str,
        *,
        force_review: bool = False,
    ) -> ModerationEvidence:
        return ModerationEvidence(
            reason_code=indicator.reason.category,
            description=indicator.reason.description,
            indicator_id=indicator.id,
            confidence=indicator.confidence,
            match_type=f'{match_type}:review' if force_review else match_type,
            action=(
                ModerationAction.BLOCK
                if indicator.status == 'confirmed' and not force_review
                else ModerationAction.REVIEW
            ),
        )

    @staticmethod
    def _result_for_evidence(
        evidence: list[ModerationEvidence],
    ) -> ModerationResult:
        if not evidence:
            return ModerationResult.allow()
        if any(item.action == ModerationAction.BLOCK for item in evidence):
            action = ModerationAction.BLOCK
        else:
            action = ModerationAction.REVIEW
        return ModerationResult(action=action, evidence=tuple(evidence))

    @staticmethod
    def _get_legacy_malicious_domains(
        items: set[BlacklistItem],
    ) -> dict[str, tuple[str, str]]:
        domains: dict[str, tuple[str, str]] = {}
        for item in items:
            reasons = [
                reason[0] if isinstance(reason, tuple) else reason
                for reason in item.reasons
            ]
            if reasons and all(
                reason == BlacklistReason.URL_SHORTENER for reason in reasons
            ):
                continue

            domain = normalize_domain(str(item.value))

            reason_codes = [
                reason.value
                if isinstance(reason, BlacklistReason)
                else 'blocked_domain'
                for reason in reasons
            ]
            description = ', '.join(reason_codes) or 'Known malicious domain'
            domains[domain] = (
                reason_codes[0] if reason_codes else 'blocked_domain',
                description,
            )
        return domains
