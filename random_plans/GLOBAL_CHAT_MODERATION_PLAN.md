# Global Chat Moderation Plan

## Goal

Moderate text and image attachments before a message is relayed to other servers.
Use inexpensive, explainable checks for clear threats and send uncertain cases to
moderators rather than relying on one machine-learning model.

## Current behavior

The global chat listener currently rate-limits messages and checks message text
for profanity and Discord invite links. `censor_urls()` replaces some recognized
URLs with placeholders and looks up domains against configured allowlists and
blocklists, but a blocklisted URL does not currently prevent a broadcast. URL
extraction is configured for URLs with a scheme. Image and video attachments can
be forwarded without moderation analysis.

The moderation checks should run before the broadcast fan-out in
`src/poxbot/platforms/discord/extensions/global_chat.py`.

## Proposed message pipeline

1. **Apply existing checks.** Preserve the current anti-spam and profanity
   behavior.
2. **Normalize text.** Normalize Unicode and remove or canonicalize common
   zero-width and formatting characters before matching. Keep the original text
   for display; use normalized text only for analysis.
3. **Inspect message text and URLs.**
   - Extract both schemed and common bare URLs; normalize hosts, subdomains, and
     internationalized domain names.
   - Check Discord invite formats and known malicious domains/URLs.
   - Match explicit scam phrases and patterns, then optionally compare text to a
     small, moderator-confirmed scam-message set.
   - Treat URL-reputation lookups as an external signal with caching and
     timeouts. Never fetch arbitrary user-supplied URLs from the bot host.
4. **Inspect attachments safely.**
   - Restrict analysis to supported image types and enforce file-size and
     dimension limits.
   - Compare exact SHA-256 hashes to identify identical files.
   - Compare perceptual hashes (pHash/dHash) to detect resized, recompressed, or
     mildly edited copies of known scam images.
   - Run OCR on images to extract visible text and URLs. Send the extracted text
     through the same normalization, phrase, and URL checks as message text.
   - Consider image embeddings only if perceptual hashes and OCR miss meaningful
     variants. Compare embeddings to a curated set of known scam examples, not
     an unrestricted general similarity threshold.
5. **Combine evidence once per message.** Produce a moderation result such as
   `allow`, `block`, or `review`, with reason codes and confidence/evidence.
   Apply clear deterministic rules first. Do not ban users based only on a fuzzy
   text or image similarity score.
6. **Gate the broadcast.** Only relay messages allowed by the moderation
   decision. Block or hold confirmed threats; route uncertain results to a
   moderator review queue if one is available.
7. **Record minimal moderation telemetry.** Count outcomes and reasons without
   logging message contents, full URLs, OCR output, or attachment data by
   default. Provide a controlled review path if human review requires evidence.

## Recommended implementation phases

### Phase 1: Deterministic text and link checks

- Extract and normalize URLs, including bare links.
- Make confirmed blocklist matches stop the broadcast instead of only replacing
  the displayed URL.
- Add tested patterns for Discord invite variants and common scam wording.
- Keep allowlist behavior explicit and ensure it cannot accidentally override
  high-confidence threat indicators.
- Add tests for Unicode obfuscation, punctuation, casing, bare URLs, subdomains,
  allowlisted domains, and blocklisted domains.

### Phase 2: Lightweight image duplicate detection

- Validate and decode supported images with strict size/dimension limits.
- Store SHA-256 and perceptual hashes for moderator-confirmed scam images.
- Compare new attachments against this set and measure Hamming distance for
  perceptual hashes.
- Tune thresholds on known scam examples and ordinary global-chat images.
- Add tests for exact copies, resizing/recompression, modest edits, unrelated
  images, and malformed/oversized files.

### Phase 3: OCR and shared text analysis

- Add OCR behind a bounded worker or asynchronous job so it does not block the
  Discord event loop.
- Extract text and URLs from images and pass them through the same checks used
  for message text.
- Benchmark startup time, per-image latency, resident memory, and behavior on
  the deployment host before choosing an OCR engine.
- Keep OCR failure explicit in logs/metrics and define whether the message is
  allowed or held when analysis is unavailable.

### Phase 4: Optional semantic models

- If testing shows important misses, evaluate text embeddings/classifiers for
  scam-message similarity and image embeddings for scam-image variants.
- Use only task-appropriate models with a clear license and model card.
- Do not use sentiment classification as scam classification.
- Do not use generic ImageNet MobileNetV2 classes as a scam detector without
  scam-specific training and evaluation.
- Compare smaller candidates such as MobileCLIP against a baseline on a
  representative, labeled dataset. CLIP-style similarity indicates resemblance,
  not malicious intent.
- Keep model predictions advisory until precision and false-positive rates are
  acceptable.

## Model and dependency notes

- SHA-256 and perceptual hashing are inexpensive and should be the first image
  similarity checks.
- Pillow can decode and resize images but does not classify malicious content.
- EasyOCR can extract text, but it uses PyTorch and loads model weights into
  memory. Measure the complete runtime cost rather than judging by package name
  or model-file size.
- An NSFW detector detects sexual-content categories, not scams.
- `lxyuan/distilbert-base-multilingual-cased-sentiments-student` predicts
  sentiment classes, not scam/phishing risk.
- MobileNetV2's common pretrained checkpoint is for ImageNet object classes,
  not scam detection.
- Standard CLIP ViT-B/32 is comparatively heavyweight and its model card warns
  against untested deployment. A smaller image-text model may be evaluated later,
  but it still needs task-specific validation.

## Threat indicator catalog

Keep known malicious indicators in a versioned JSON file, for example
`src/poxbot/assets/global_chat_threats.json`, loaded and validated by
`GlobalChatModerator` in `src/poxbot/features/moderation/`. JSON is a natural fit for this
Python project and easy to validate at startup; XML is also viable if the
existing configuration tooling or maintainers prefer it. Use one authoritative
format rather than maintaining both.

Each record should include:

- A stable record ID and indicator type, such as `sha256`, `phash`, `url_domain`,
  or `text_pattern`.
- The hash algorithm and value where applicable. Store exact hashes separately
  from perceptual hashes; a perceptual match is approximate and must not be
  treated as cryptographic proof.
- A reason category and a short explanation of why it is considered malicious.
- Confidence, source/provenance, and review status so unverified reports are not
  treated as confirmed matches.
- Creation, review, and optional expiration timestamps.
- Optional safe metadata such as a moderator-only evidence reference. Avoid
  storing original images, full message contents, or personal data in the
  catalog.

Example:

```json
{
  "schema_version": 1,
  "indicators": [
    {
      "id": "scam-image-0001",
      "type": "image_hash",
      "algorithm": "phash",
      "value": "9f172786e71f1e00",
      "max_distance": 4,
      "reason": {
        "category": "giveaway_scam",
        "description": "Confirmed fake prize giveaway image impersonating a creator"
      },
      "confidence": 0.98,
      "status": "confirmed",
      "source": "moderator_report",
      "created_at": "2026-10-09T00:00:00Z",
      "reviewed_at": "2026-10-09T00:00:00Z",
      "expires_at": null,
      "metadata": {
        "evidence_ref": "moderation-case-0001",
        "notes": "Compare using a tuned Hamming-distance threshold; review near matches"
      }
    }
  ]
}
```

Validate the schema and reject malformed records rather than silently ignoring
them. Restrict edits to trusted maintainers/moderators, review contributions
before setting `status` to `confirmed`, and periodically expire or re-check stale
indicators. Do not let `confidence` alone trigger punitive action; combine it
with the indicator type, match distance, and moderation policy.

For the initial implementation, confirmed exact SHA-256, URL-domain, and text
phrase matches block relaying. pHash matches and unreviewed indicators are held
for review. Oversized, animated, unsupported, or undecodable images are also
held rather than broadcast. Static JPEG, PNG, and WebP images are analyzed,
with an 8 MiB per-image cap, a 16 MiB total-image cap, and a 10-second total
attachment-read timeout. The starter catalog is intentionally empty; add
reviewed indicators through the JSON file.

## Operational safeguards

- Do not download or open user-provided URLs from the bot process; this creates
  SSRF and malicious-redirect risk.
- Use bounded image sizes, timeouts, concurrency limits, and a cache for repeated
  content.
- Avoid sending private message/image content to third-party APIs unless users
  are informed and the data handling is acceptable.
- Make third-party reputation feeds optional and account for rate limits,
  outages, data freshness, and terms of use.
- Do not auto-punish users based on unverified similarity alone. Provide
  moderator review and a way to correct false positives.
- Keep blocklist/hash-set maintenance attributable to trusted moderators and
  review entries periodically.

## Evaluation criteria

Before enabling enforcement, build a labeled test set containing confirmed scam
text/images, benign global-chat content, edited and recompressed scam images,
multilingual examples, and obfuscated URLs. Measure:

- Precision and recall for each detector and for the combined decision.
- False-positive rate on benign content.
- CPU and memory at startup and under realistic message volume.
- Median and high-percentile per-message latency.
- Failure behavior when OCR, local models, or reputation services are unavailable.

Start in log-only or review-only mode where practical, inspect false positives,
then enable blocking for high-confidence deterministic matches.
