# External network render comparison

The retained target rendering differed from the reviewed transformation at exactly
three paths: networks.atlas-backend.ipam, networks.atlas-identity.ipam and
networks.atlas-ingress.ipam. Their contents were withheld in the diagnostic.

The resumed comparator accepts an IPAM field only when the network is explicitly
external and the field is exactly an empty mapping. It rejects every nonempty
mapping, including driver/default or an empty config/options member. Null, lists,
false and numeric substitutes also refuse. All remaining settings compare exactly
using canonical JSON bytes. Missing create_host_path remains equivalent only to
boolean false; numeric false substitutes are rejected.

The prior 25 container tests and their hashes remain historical evidence. Six new
focused tests cover the comparison change. The earlier failed receipt, log,
rendering and tested source are retained unchanged. Both execution recipes are
prepared anew in a separate private folder. No container or service is changed.
