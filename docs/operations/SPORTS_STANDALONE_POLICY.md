# Standalone Sports policy identity

NFL RedZone and other explicitly standalone channels have a persistent Atlas
channel identity instead of a provider event identity. Their policy claims use
`identity_kind: standalone` and `standalone_channel_id`. They do not invent a
provider or event ID. Existing event claims retain their exact seven-field wire
contract. Dispatcharr accepts either exact schema and rejects mixed or conflicting
identities for one channel.

Standalone claims retain the existing exact channel UUID, current catalog and
resource membership, enabled source, bounded account and configured capacity,
and explicit credential realm requirements. Classification still requires managed
channel history. Claims are metadata authority only; they do not observe provider
capacity or independently permit playback. A catalog's standalone field must be
an actual boolean.

The Braves and Rams test feeds identified during readiness review are retirement
candidates, not standalone production features. Production retirement must follow
the guarded writer deployment and v2 managed-history migration. Delete their live
catalog entries and bindings through native methods while retaining their UUIDs
in managed history. Retired UUIDs must remain unavailable rather than falling back
to unmanaged legacy playback. Preserve original registry snapshots and receipts.
The tests rehearse this on disposable copies; this source change retires no live
entry.

The changed claim client requires a newly verified Dispatcharr candidate image.
The previous candidate's validation remains evidence for its previous source.
Strict activation still requires dedicated policy credentials, verified credential
realm onboarding, backend drain and reservation cutover, accepted recovery and
rollback, and playback/capacity/sharing acceptance. This source change performs
none of those production actions and leaves verified-live mode off.
