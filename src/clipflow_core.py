"""ClipFlow safety-critical core. Pure functions, no external credentials.

Runtime features in this folder are P0 contracts, not a deployed API.
"""
from __future__ import annotations
from dataclasses import dataclass
import hashlib
import hmac
import re
from uuid import UUID
from datetime import datetime, timezone
from urllib.parse import urlencode

VIDEO_FILE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,125}\.(?:mp4|mov|mkv|webm)$", re.I)
REGIONS = frozenset(("PH", "US", "GB", "CA", "AU"))
CATEGORIES = {"all": None, "gaming": "20", "education": "27", "tech": "28",
              "music": "10", "sports": "17", "entertainment": "24", "news": "25"}

@dataclass(frozen=True)
class Command:
    name: str
    args: tuple[str, ...]

class RejectedCommand(ValueError):
    pass


def parse_command(raw: str) -> Command:
    if not isinstance(raw, str) or len(raw) > 256 or '\n' in raw or '\r' in raw:
        raise RejectedCommand("Command exceeds size limit")
    # Natural-language operator alias. The prefix must be explicit: no ambient
    # Telegram chat message should accidentally trigger a YouTube API call.
    natural = re.fullmatch(
        r"\s*CF\s+(?:look\s+for|find|search)\s+(?:(?:the|some)\s+)?"
        r"(?:(?:trending|popular|recent)\s+)?(.+?)\s*",
        raw, re.IGNORECASE | re.DOTALL)
    if natural:
        return Command('topic_search', (normalize_topic(natural.group(1)).raw_topic, 'PH'))
    parts = raw.strip().split()
    if not parts or not parts[0].startswith('/'):
        raise RejectedCommand("Expected a slash command or 'CF look for trending <topic> videos'")
    verb = parts[0].partition('@')[0].lower()
    args = tuple(parts[1:])
    if verb == '/find':
        if not args:
            raise RejectedCommand('Use /find <topic>')
        return Command('topic_search', (normalize_topic(' '.join(args)).raw_topic, 'PH'))
    if verb == '/trending':
        if len(args) > 2:
            raise RejectedCommand("Use /trending [PH|US|GB|CA|AU] [category]")
        region = args[0].upper() if args else "PH"
        niche = args[1].lower() if len(args) > 1 else "all"
        if region not in REGIONS or niche not in CATEGORIES:
            raise RejectedCommand("Unsupported region or category")
        return Command('trending', (region, niche))
    if verb == '/source':
        if len(args) != 2 or not VIDEO_FILE.fullmatch(args[0]) or args[1].lower() not in ('owned', 'licensed') or '..' in args[0]:
            raise RejectedCommand("Use /source filename.mp4 owned|licensed (file already in your private Drive Sources folder)")
        return Command('source', (args[0], args[1].lower()))
    if verb in ('/clip','/retry'):
        if len(args) != 1:
            raise RejectedCommand(f"Use {verb} <id>")
        try:
            identifier = str(UUID(args[0]))
        except ValueError as exc:
            raise RejectedCommand("Expected a valid UUID") from exc
        return Command(verb[1:], (identifier,))
    if verb in ('/help','/status') and not args:
        return Command(verb[1:], ())
    raise RejectedCommand("Unknown command, use /help")


def signed_update(secret: str, update_id: int, chat_id: int, user_id: int, raw: str) -> str:
    canonical = f"{update_id}:{chat_id}:{user_id}:{raw}".encode('utf-8')
    return hmac.new(secret.encode('utf-8'), canonical, hashlib.sha256).hexdigest()


def authorize_update(secret: str, expected_chat: int, expected_sender: int, payload: dict) -> bool:
    try:
        uid, chat, sender = (int(payload[k]) for k in ('update_id','chat_id','sender_id'))
        raw = payload['text']
        sig = payload['signature']
        if uid < 0 or chat != expected_chat or sender != expected_sender:
            return False
        return isinstance(raw, str) and isinstance(sig,str) and hmac.compare_digest(
            signed_update(secret,uid,chat,sender,raw),sig)
    except (TypeError, ValueError, KeyError):
        return False


def chart_rows(youtube_payload: dict, region: str, category: str) -> list[dict]:
    """Public discovery metadata only. Never equate chart order with rising velocity."""
    records = []
    for position, item in enumerate(youtube_payload.get('items', [])[:50], 1):
        snippet = item.get('snippet') or {}
        stats = item.get('statistics') or {}
        video_id = item.get('id')
        if not isinstance(video_id, str) or not re.fullmatch(r'[A-Za-z0-9_-]{11}',video_id):
            continue
        try:
            views = max(0,int(stats.get('viewCount',0)))
        except (ValueError,TypeError):
            views = 0
        records.append({'video_id':video_id,'url':'https://www.youtube.com/watch?v='+video_id,
            'title':str(snippet.get('title',''))[:250], 'channel':str(snippet.get('channelTitle',''))[:200],
            'published_at':snippet.get('publishedAt'),'views':views,
            'chart_position':position,'region':region,'category':category,
            'signal':'regional_popularity_chart_not_verified_viral'})
    return records


def trend_velocity(current_views: int, old_views: int, elapsed_hours: float) -> float | None:
    if elapsed_hours < 1 or current_views < old_views:
        return None
    return round((current_views-old_views)/elapsed_hours,2)


def validate_clip_window(start: float, end: float, video_duration: float,
                         min_seconds: float = 15, max_seconds: float = 60) -> None:
    if not (0 <= start < end <= video_duration):
        raise ValueError('Clip window must be within source bounds')
    if not min_seconds <= (end-start) <= max_seconds:
        raise ValueError('Clip window outside configured length')


# CF-P0-003: Topic-scoped discovery contracts. Runtime must still call the
# official YouTube API, store the query and verify results before returning.
TOPIC_ALIASES = {
    'gta_6': re.compile(r"\b(?:gta[\s-]*(?:6|vi)|grand[\s-]+theft[\s-]+auto[\s-]*(?:6|vi))\b", re.I),
}
TOPIC_STOPWORDS = frozenset({'the', 'a', 'an', 'of', 'and', 'about', 'for'})
TRAILING_VIDEO_WORDS = re.compile(r"(?:\s+(?:youtube\s+)?videos?|\s+on\s+youtube|\s+please)+\s*[.!?]*$", re.I)
MAX_TELEGRAM_VIDEO_BYTES = 50_000_000  # conservative decimal MB limit, NOT MiB
TELEGRAM_UPLOAD_TOO_LARGE = frozenset(('FILE_TOO_BIG', 'REQUEST_ENTITY_TOO_LARGE', 'HTTP_413'))

@dataclass(frozen=True)
class TopicScope:
    raw_topic: str
    canonical_topic: str
    youtube_query: str
    scope_key: str
    required_tokens: tuple[str, ...]

@dataclass(frozen=True)
class DeliveryDecision:
    mode: str  # 'telegram_video' | 'drive_link_only'
    reason: str

class DeliveryHold(ValueError):
    pass


def normalize_topic(raw_topic: str) -> TopicScope:
    if not isinstance(raw_topic, str):
        raise RejectedCommand('Invalid topic')
    topic = raw_topic.strip()
    topic = re.sub(r"^(?:trending|popular|recent)\s+", "", topic, flags=re.I)
    topic = TRAILING_VIDEO_WORDS.sub('', topic)
    if topic.lower() in {'video','videos'}:
        raise RejectedCommand('A subject is required for targeted search')
    topic = re.sub(r'\s+', ' ', topic).strip(' .!?')
    # The topic goes to third-party search. Keep it short and free of operators
    # or URL metacharacters that would change the operator's search intent.
    if not 2 <= len(topic) <= 80 or not re.fullmatch(r"[\w\s+&.'()\-]+", topic, re.UNICODE):
        raise RejectedCommand('Topic must be 2-80 plain-text characters')
    gta = TOPIC_ALIASES['gta_6']
    if gta.search(topic):
        modifiers = gta.sub(' ', topic)
        tokens = tuple(token for token in re.findall(r"[a-z0-9]+", modifiers.lower())
                       if token not in TOPIC_STOPWORDS)
        canonical = 'GTA 6' + (' ' + ' '.join(tokens) if tokens else '')
        query = 'GTA 6' + (' ' + ' '.join(tokens) if tokens else '') + '|' + \
                'Grand Theft Auto VI' + (' ' + ' '.join(tokens) if tokens else '')
        return TopicScope(topic, canonical, query, 'gta_6', tokens)
    tokens = tuple(token for token in re.findall(r"[a-z0-9]+", topic.lower())
                   if token not in TOPIC_STOPWORDS)
    if not tokens:
        raise RejectedCommand('Topic has no searchable keywords')
    return TopicScope(topic, topic, topic, 'literal_topic', tokens)


def matches_topic(title: str, scope: TopicScope) -> bool:
    # Strict matching gives precision over recall. Never broaden to global
    # gaming or any other category when a focused query returns zero matches.
    if not isinstance(title, str):
        return False
    if scope.scope_key == 'gta_6' and not TOPIC_ALIASES['gta_6'].search(title):
        return False
    return all(re.search(r'(?<!\w)' + re.escape(token) + r'(?!\w)', title, re.I)
               for token in scope.required_tokens)


def topic_search_parameters(scope: TopicScope, published_after: str,
                            region: str = 'PH') -> dict:
    if region not in REGIONS:
        raise RejectedCommand('Unsupported region')
    if not isinstance(published_after, str) or not re.fullmatch(
            r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z', published_after):
        raise RejectedCommand('Expected UTC publishedAfter timestamp')
    return {'part':'snippet','type':'video','q':scope.youtube_query,
            'maxResults':50, 'order':'viewCount','publishedAfter':published_after,
            'regionCode':region, 'safeSearch':'moderate'}


def topic_video_candidates(search_payload: dict, video_payload: dict,
                           scope: TopicScope, observed_at: datetime) -> list[dict]:
    if observed_at.tzinfo is None:
        raise ValueError('observed_at must have timezone')
    details = {v.get('id'):v for v in video_payload.get('items', [])}
    kept=[]
    seen=set()
    for entry in search_payload.get('items', []):
        vid = (entry.get('id') or {}).get('videoId')
        if not isinstance(vid,str) or not re.fullmatch(r'[A-Za-z0-9_-]{11}',vid) or vid in seen:
            continue
        v=details.get(vid)
        if not v:
            continue
        sn=v.get('snippet') or entry.get('snippet') or {}
        title=str(sn.get('title',''))
        if not matches_topic(title,scope):
            continue
        try:
            views=int((v.get('statistics') or {}).get('viewCount',0))
            published=datetime.fromisoformat(str(sn['publishedAt']).replace('Z','+00:00'))
            age_seconds=(observed_at-published).total_seconds()
        except (TypeError,ValueError,KeyError):
            continue
        if views<0 or age_seconds<0:
            continue
        seen.add(vid)
        approx_vph=round(views/max(age_seconds/3600,1),2)
        kept.append({'video_id':vid,'title':title[:250],
                     'url':'https://www.youtube.com/watch?v='+vid,
                     'view_count':views,'published_at':published.isoformat(),
                     'approx_views_per_hour':approx_vph,
                     'topic':scope.canonical_topic,'scope_pass':True,
                     'signal':'age_normalized_view_proxy_not_verified_velocity'})
    return sorted(kept,key=lambda row: (-row['approx_views_per_hour'],-row['view_count'],row['video_id']))


def decide_delivery(file_size_bytes: int, *, drive_uploaded_and_verified: bool,
                    recipient_drive_access_verified: bool,
                    telegram_error: str | None = None) -> DeliveryDecision:
    if not isinstance(file_size_bytes,int) or isinstance(file_size_bytes,bool) or file_size_bytes <= 0:
        raise DeliveryHold('Invalid or unknown media size; do not send')
    if not drive_uploaded_and_verified or not recipient_drive_access_verified:
        raise DeliveryHold('Cannot deliver before Drive upload and recipient access verification')
    if telegram_error and telegram_error not in TELEGRAM_UPLOAD_TOO_LARGE:
        raise DeliveryHold('Telegram send failed or ambiguous; do not resend automatically')
    if file_size_bytes > MAX_TELEGRAM_VIDEO_BYTES:
        return DeliveryDecision('drive_link_only','file_exceeds_50_decimal_MB')
    if telegram_error in TELEGRAM_UPLOAD_TOO_LARGE:
        return DeliveryDecision('drive_link_only','telegram_explicit_size_rejection')
    return DeliveryDecision('telegram_video','within_50_decimal_MB')


def private_drive_link_only(view_url: str, decision: DeliveryDecision) -> str:
    # Text contains *only* URL. Runtime must separately check permission for
    # the actual recipient and never set anyone/reader sharing automatically.
    if decision.mode != 'drive_link_only':
        raise DeliveryHold('Link-only formatter requires Drive-link delivery mode')
    if not isinstance(view_url,str) or not re.fullmatch(
            r'https://drive\.google\.com/file/d/[A-Za-z0-9_-]+/view(?:\?[^\s#]*)?',view_url):
        raise DeliveryHold('Expected a verified Drive viewer URL')
    return view_url
