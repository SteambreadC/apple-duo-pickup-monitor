# Apple Duo pickup monitor

Build a free, read-only monitor for US iPhone Duo 512GB in two finishes, scoped to eight explicitly named Apple Stores around Seattle and Portland. Do not interact with accounts, carts, purchases, orders, or existing ChatGPT monitoring.

Use Python 3.12 standard library, Apple's undocumented `/shop/retail/pickup-message`, two ZIP queries (98033, 97204), and exact store ID/name plus part/title matching. No shipping fields are considered. Query both colors in one request; confirm available candidates using a second network round. HTTP Date must be fresh and Age absent/zero. Unknown, missing, mismatched, rate-limited, and cached results never mean available or unavailable. Preserve the raw pickup quote and explicitly label the observation time; an alert is a signal, not a reserved slot.

Alternatives considered: adapting bilune/apple-pickup-monitor versus a small independent implementation. The latter is chosen by the implementer because persistent channel-level delivery state, strict freshness checks, and matching are central requirements; upstream is documented as research, not copied. Browser checkout automation is unnecessary and would introduce account/session dependence.

Persist deduplication and health state on a dedicated GitHub state branch, serialize runs, and retry failed channels only on freshly reconfirmed availability. Rearm only after two consecutive explicit unavailable observations; unknown breaks the consecutive miss sequence. State corruption is fatal. Provider delivery followed by process failure can duplicate a notification (at-least-once semantics).

Provide ntfy, Telegram, and SMTP email using environment secrets. Never use paid ntfy email forwarding. No default recipients; explicit test mode sends clearly labelled tests only after configuration. Test actual adapters with a local HTTP/SMTP server. Do not claim real phone delivery without user confirmation.

Public standard Ubuntu Actions runner: proposed 10-minute schedule. Private: proposed 30 minutes with a zero spending budget and shared-minute limits explained. User chooses visibility before publication. GitHub schedules can be late/dropped and public schedules disable after 60 days inactivity; this is not an instantaneous or guaranteed alert service. No proxy rotation or access-control bypass. Respect 429 Retry-After, apply persisted backoff to 403/541 and repeated errors, and alert on sustained monitoring failure.
