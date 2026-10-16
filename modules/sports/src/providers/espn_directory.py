"""ESPN team-directory parsing and route-scoped public discovery identities."""
from dataclasses import dataclass
from providers.espn_metadata import MetadataError, ROUTES, LEAGUE_UIDS, _identifier, _text


@dataclass(frozen=True)
class MetadataTeam:
    route: str
    team_id: str
    name: str
    abbreviation: str

    @property
    def identity(self):
        return ('espn', self.route, self.team_id)

    @property
    def public_id(self):
        return encode_entity_id(self.route, self.team_id)


def encode_entity_id(route, identifier):
    if route not in ROUTES:
        raise MetadataError('Unsupported source league')
    return route.replace('/', '-') + '-' + _identifier(identifier)


def decode_entity_id(value):
    if not isinstance(value, str):
        raise MetadataError('Invalid source identity')
    for route in ROUTES:
        prefix = route.replace('/', '-') + '-'
        if value.startswith(prefix):
            identifier = value[len(prefix):]
            if encode_entity_id(route, identifier) != value:
                raise MetadataError('Noncanonical source identity')
            return route, identifier
    raise MetadataError('Unsupported source identity')


def parse_team_directory(route, payload):
    if route not in ROUTES or ROUTES[route][2]:
        raise MetadataError('This source league has no team directory')
    if not isinstance(payload, dict):
        raise MetadataError('Invalid directory response')
    sports = payload.get('sports')
    if not isinstance(sports, list) or len(sports) != 1 or not isinstance(sports[0], dict):
        raise MetadataError('Missing directory sport identity')
    sport = sports[0]
    leagues = sport.get('leagues')
    if not isinstance(leagues, list) or len(leagues) != 1 or not isinstance(leagues[0], dict):
        raise MetadataError('Missing directory league identity')
    league = leagues[0]
    if league.get('uid') != LEAGUE_UIDS[route] or sport.get('uid') != LEAGUE_UIDS[route].split('~')[0]:
        raise MetadataError('Response directory does not match requested league')
    entries = league.get('teams')
    if not isinstance(entries, list) or not 1 <= len(entries) <= 500:
        raise MetadataError('Invalid directory team list')
    teams = {}
    for entry in entries:
        if not isinstance(entry, dict) or not isinstance(entry.get('team'), dict):
            raise MetadataError('Invalid directory team')
        raw = entry['team']
        identifier = _identifier(raw.get('id'))
        # Soccer IDs are sport-wide; the captured team UID omits its league.
        scope = 's:600' if route.startswith('soccer/') else LEAGUE_UIDS[route]
        if raw.get('uid') != scope + '~t:' + identifier:
            raise MetadataError('Directory team identity mismatch')
        abbreviation = raw.get('abbreviation', '')
        if not isinstance(abbreviation, str) or len(abbreviation) > 32:
            raise MetadataError('Invalid team abbreviation')
        team = MetadataTeam(route, identifier, _text(raw.get('displayName'), 'team name'), abbreviation.strip())
        if identifier in teams and teams[identifier] != team:
            raise MetadataError('Conflicting directory team identity')
        teams[identifier] = team
    return tuple(teams.values())


def search_directory(teams, query):
    if not isinstance(query, str) or len(query) > 200:
        raise ValueError('Invalid team query')
    terms = query.casefold().split()
    if not terms:
        return ()
    return tuple(team for team in teams if all(
        term in (team.name + ' ' + team.abbreviation).casefold() for term in terms))
