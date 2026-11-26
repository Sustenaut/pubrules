"""pubrules' library surface: the names a package that uses pubrules as a
library may import, and the only module it imports them from.

Nothing is defined here: each name lives in its own module, which keeps its
own name for it, and nothing inside pubrules imports this module. Moving or
renaming an internal therefore changes nothing such a package sees, as long as the
name below still points at it. tests/features/api.feature holds this surface
to tests/fixtures/api.txt, the names with their signatures, so any change to
it fails the suite until the fixture is updated and the change recorded.
"""

from . import __version__ as version
from .conform import run as conform
from .freshness import PIN as PUBRULES_LOCK_PIN
from .freshness import pinned as pinned_pubrules
from .hosting import SEP as HOSTING_SEP
from .hosting import dnskey
from .hosting import settings as hosting_settings
from .nightly import PUBREL_VERSION as PUBREL_VERSION_INPUT
from .paths import confined
from .protect import Api, ApiError, gh, gh_set, on_default_branch, on_release_tags, remote_config, ruleset, tag_ruleset
from .protect import differences as ruleset_differences
from .protect import entry as protection_entry
from .protect import remote as remote_protection_entry
from .refs import ANY_OWNER, AT, RELEASE_PIN, VERSION
from .repos import entries as repo_entries
from .repos import read as read_repos
from .variables import BLOCK as VARIABLES_BLOCK
from .variables import block_problems as variables_problems
from .variables import defaults as variable_defaults
from .variables import name_problem as variable_name_problem

__all__ = [
    # The version installed.
    "version",
    # The standard's protection: a repository's entry and the rulesets it implies.
    "protection_entry", "remote_protection_entry", "ruleset", "tag_ruleset", "ruleset_differences",
    "on_default_branch", "on_release_tags",
    # The GitHub calls pubrules makes.
    "Api", "ApiError", "gh", "gh_set", "remote_config",
    # The repos file.
    "read_repos", "repo_entries",
    # The variables block's shape and defaults.
    "VARIABLES_BLOCK", "variables_problems", "variable_name_problem", "variable_defaults",
    # The pins a repository's files carry.
    "ANY_OWNER", "AT", "VERSION", "RELEASE_PIN", "PUBRULES_LOCK_PIN", "pinned_pubrules", "PUBREL_VERSION_INPUT",
    # The standard a repository is judged by.
    "conform",
    # A path a command is given, kept inside the repository.
    "confined",
    # The hosting block's shape.
    "HOSTING_SEP", "dnskey", "hosting_settings",
]
